#!/usr/bin/env python3
"""
ComicMaster Quality Gates — Post-Processing Quality Checks & Auto-Retry.

Provides:
    HandQualityChecker   — MediaPipe-based hand/finger detection & validation
    FaceConsistencyChecker — Face embedding comparison across panels (SSIM fallback)
    TextArtifactChecker  — Detect unwanted AI text artifacts in generated panels
    QualityGateRunner    — Orchestrate all checks with auto-retry logic

Integration:
    Called by comic_pipeline.py after panel generation.
    Uses quality_tracker.py for composition scoring.

Dependencies:
    Required: PIL/Pillow, numpy
    Optional: mediapipe (hand/face detection — fallback to PIL heuristics)
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageFilter, ImageStat

# ---------------------------------------------------------------------------
# Setup paths — match existing codebase pattern
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).parent
SKILL_DIR = SCRIPTS_DIR.parent
MODELS_DIR = SKILL_DIR / "models"

# Add our scripts to path
sys.path.insert(0, str(SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("comicmaster.quality_gates")

# ---------------------------------------------------------------------------
# MediaPipe availability check
# ---------------------------------------------------------------------------
_MEDIAPIPE_AVAILABLE = False
_mp_vision = None
_mp_base = None

try:
    from mediapipe.tasks.python import vision as _mp_vision_mod
    from mediapipe.tasks.python import BaseOptions as _mp_base_cls
    _mp_vision = _mp_vision_mod
    _mp_base = _mp_base_cls
    import mediapipe as mp
    _MEDIAPIPE_AVAILABLE = True
except ImportError:
    pass


# ===================================================================
# 1. HandQualityChecker
# ===================================================================

class HandQualityChecker:
    """Detect and validate hands in generated comic panels.

    Method 1 (preferred): MediaPipe Hand Landmark Detection
        - Detects up to 4 hands
        - Counts fingers via landmark geometry
        - Flags implausible joint angles

    Method 2 (fallback): PIL-based skin-color heuristic
        - Skin-color blob detection
        - Aspect-ratio and shape analysis
    """

    # Joint angle thresholds (degrees) — outside these → anatomically wrong
    MIN_FINGER_ANGLE = 5.0     # fingers shouldn't be perfectly straight stacks
    MAX_FINGER_ANGLE = 185.0   # hyperextension limit

    # Finger tip → MCP landmark indices for each finger (mediapipe convention)
    # Index: [TIP, DIP, PIP, MCP] for each finger
    FINGER_LANDMARKS = {
        "thumb":  [4, 3, 2, 1],
        "index":  [8, 7, 6, 5],
        "middle": [12, 11, 10, 9],
        "ring":   [16, 15, 14, 13],
        "pinky":  [20, 19, 18, 17],
    }

    # Expected: 5 fingers per hand
    EXPECTED_FINGERS_PER_HAND = 5

    def __init__(self, model_path: str | None = None):
        """Initialize hand checker.

        Args:
            model_path: Path to mediapipe hand_landmarker.task model.
                        Defaults to models/hand_landmarker.task.
        """
        self._detector = None
        self._use_mediapipe = _MEDIAPIPE_AVAILABLE

        if self._use_mediapipe:
            mp_model = model_path or str(MODELS_DIR / "hand_landmarker.task")
            if os.path.exists(mp_model):
                try:
                    options = _mp_vision.HandLandmarkerOptions(
                        base_options=_mp_base(model_asset_path=mp_model),
                        running_mode=_mp_vision.RunningMode.IMAGE,
                        num_hands=4,
                        min_hand_detection_confidence=0.4,
                        min_hand_presence_confidence=0.4,
                        min_tracking_confidence=0.4,
                    )
                    self._detector = _mp_vision.HandLandmarker.create_from_options(options)
                except Exception as e:
                    logger.warning(f"MediaPipe hand detector init failed: {e}")
                    self._use_mediapipe = False
            else:
                logger.warning(f"Hand model not found at {mp_model}, using fallback")
                self._use_mediapipe = False

    def check(self, image: Image.Image | str) -> dict:
        """Run hand quality check on an image.

        Args:
            image: PIL Image or path to image file.

        Returns:
            {
                "hands_detected": int,
                "issues": [str, ...],
                "confidence": float (0-1),
                "pass": bool,
                "details": {...},  # per-hand details
                "method": "mediapipe" | "heuristic"
            }
        """
        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")

        if self._use_mediapipe and self._detector is not None:
            return self._check_mediapipe(image)
        else:
            return self._check_heuristic(image)

    def _check_mediapipe(self, img: Image.Image) -> dict:
        """MediaPipe-based hand detection and validation."""
        # Convert PIL → MediaPipe Image
        img_array = np.array(img)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_array)

        result = self._detector.detect(mp_image)

        issues = []
        hand_details = []
        total_confidence = 0.0

        num_hands = len(result.hand_landmarks)

        if num_hands == 0:
            # No hands detected — might be fine (wide shot, no visible hands)
            return {
                "hands_detected": 0,
                "issues": [],
                "confidence": 0.8,  # No hands = probably OK (wide shot)
                "pass": True,
                "details": [],
                "method": "mediapipe",
            }

        for hand_idx, landmarks in enumerate(result.hand_landmarks):
            hand_info = {"hand_index": hand_idx, "finger_issues": []}

            # Count extended fingers
            extended = self._count_extended_fingers(landmarks)
            hand_info["fingers_extended"] = extended
            hand_info["total_fingers"] = self.EXPECTED_FINGERS_PER_HAND

            if extended > self.EXPECTED_FINGERS_PER_HAND:
                issues.append(f"Hand {hand_idx}: {extended} fingers detected (expected ≤5)")
                hand_info["finger_issues"].append("extra_fingers")

            # Check joint angles for each finger
            angle_issues = self._check_joint_angles(landmarks)
            if angle_issues:
                hand_info["finger_issues"].extend(angle_issues)
                for ai in angle_issues:
                    issues.append(f"Hand {hand_idx}: {ai}")

            # Check overall hand proportions
            proportion_ok = self._check_hand_proportions(landmarks)
            hand_info["proportions_ok"] = proportion_ok
            if not proportion_ok:
                issues.append(f"Hand {hand_idx}: unusual proportions")
                hand_info["finger_issues"].append("bad_proportions")

            # Per-hand confidence
            hand_score = result.handedness[hand_idx][0].score if result.handedness else 0.5
            hand_confidence = hand_score
            if hand_info["finger_issues"]:
                hand_confidence *= 0.5  # Penalize if issues found
            hand_info["confidence"] = round(hand_confidence, 3)
            total_confidence += hand_confidence

            # Store landmark data for potential inpainting mask generation
            hand_info["landmarks"] = [
                {"x": lm.x, "y": lm.y, "z": lm.z}
                for lm in landmarks
            ]

            hand_details.append(hand_info)

        # Aggregate confidence
        avg_confidence = total_confidence / num_hands if num_hands > 0 else 0.5
        # Penalize for many issues
        issue_penalty = min(0.4, len(issues) * 0.1)
        final_confidence = max(0.0, min(1.0, avg_confidence - issue_penalty))

        return {
            "hands_detected": num_hands,
            "issues": issues,
            "confidence": round(final_confidence, 3),
            "pass": final_confidence >= 0.5,
            "details": hand_details,
            "method": "mediapipe",
        }

    def _count_extended_fingers(self, landmarks) -> int:
        """Count extended fingers using landmark positions.

        A finger is considered extended if its TIP is farther from the
        wrist than its PIP joint (in the direction of the finger).
        """
        extended = 0

        # Wrist landmark (index 0)
        wrist = landmarks[0]

        # Thumb: special case — compare x-distance based on handedness
        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        thumb_mcp = landmarks[2]
        # Thumb is extended if TIP is farther from palm center than IP
        thumb_dist_tip = math.sqrt(
            (thumb_tip.x - thumb_mcp.x) ** 2 + (thumb_tip.y - thumb_mcp.y) ** 2
        )
        thumb_dist_ip = math.sqrt(
            (thumb_ip.x - thumb_mcp.x) ** 2 + (thumb_ip.y - thumb_mcp.y) ** 2
        )
        if thumb_dist_tip > thumb_dist_ip * 0.8:
            extended += 1

        # Other fingers: TIP y < PIP y means extended (in image coords, y increases downward)
        # But this is unreliable for rotated hands. Better: compare distances from wrist.
        for finger_name in ["index", "middle", "ring", "pinky"]:
            tip_idx = self.FINGER_LANDMARKS[finger_name][0]
            pip_idx = self.FINGER_LANDMARKS[finger_name][2]

            tip = landmarks[tip_idx]
            pip_joint = landmarks[pip_idx]

            # Distance from wrist
            tip_dist = math.sqrt(
                (tip.x - wrist.x) ** 2 + (tip.y - wrist.y) ** 2
            )
            pip_dist = math.sqrt(
                (pip_joint.x - wrist.x) ** 2 + (pip_joint.y - wrist.y) ** 2
            )

            if tip_dist > pip_dist:
                extended += 1

        return extended

    def _check_joint_angles(self, landmarks) -> list[str]:
        """Check finger joint angles for anatomical plausibility."""
        issues = []

        for finger_name, indices in self.FINGER_LANDMARKS.items():
            if finger_name == "thumb":
                continue  # Thumb has different geometry

            # Check PIP joint angle (the middle knuckle)
            tip = landmarks[indices[0]]
            dip = landmarks[indices[1]]
            pip_j = landmarks[indices[2]]
            mcp = landmarks[indices[3]]

            # Angle at DIP joint
            angle_dip = self._compute_angle(
                (pip_j.x, pip_j.y), (dip.x, dip.y), (tip.x, tip.y)
            )

            # Angle at PIP joint
            angle_pip = self._compute_angle(
                (mcp.x, mcp.y), (pip_j.x, pip_j.y), (dip.x, dip.y)
            )

            for joint_name, angle in [("DIP", angle_dip), ("PIP", angle_pip)]:
                if angle < self.MIN_FINGER_ANGLE:
                    issues.append(f"{finger_name} {joint_name} angle too small ({angle:.0f}°)")
                elif angle > self.MAX_FINGER_ANGLE:
                    issues.append(f"{finger_name} {joint_name} hyperextended ({angle:.0f}°)")

        return issues

    def _check_hand_proportions(self, landmarks) -> bool:
        """Check if hand proportions are roughly anatomically correct.

        Compares finger lengths relative to palm size.
        """
        wrist = landmarks[0]
        middle_mcp = landmarks[9]

        # Palm length: wrist to middle MCP
        palm_len = math.sqrt(
            (middle_mcp.x - wrist.x) ** 2 + (middle_mcp.y - wrist.y) ** 2
        )
        if palm_len < 1e-6:
            return False

        # Middle finger length: MCP to TIP
        middle_tip = landmarks[12]
        finger_len = math.sqrt(
            (middle_tip.x - middle_mcp.x) ** 2 + (middle_tip.y - middle_mcp.y) ** 2
        )

        # Normal ratio: finger/palm ≈ 0.8-1.3
        ratio = finger_len / palm_len
        return 0.4 < ratio < 2.0  # generous range for AI art

    @staticmethod
    def _compute_angle(a: tuple, b: tuple, c: tuple) -> float:
        """Compute angle at point b given three 2D points a-b-c.

        Returns angle in degrees.
        """
        ba = (a[0] - b[0], a[1] - b[1])
        bc = (c[0] - b[0], c[1] - b[1])

        dot = ba[0] * bc[0] + ba[1] * bc[1]
        mag_ba = math.sqrt(ba[0] ** 2 + ba[1] ** 2)
        mag_bc = math.sqrt(bc[0] ** 2 + bc[1] ** 2)

        if mag_ba < 1e-8 or mag_bc < 1e-8:
            return 180.0

        cos_angle = max(-1.0, min(1.0, dot / (mag_ba * mag_bc)))
        return math.degrees(math.acos(cos_angle))

    # --- Heuristic Fallback (PIL-based) ---

    def _check_heuristic(self, img: Image.Image) -> dict:
        """PIL-based heuristic hand quality check.

        Uses skin-color detection and blob analysis.
        Less accurate than MediaPipe but works without model files.
        """
        arr = np.array(img.convert("RGB"), dtype=np.float64)
        h, w, _ = arr.shape

        # Skin color detection in YCrCb-like space
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

        # Simple skin color mask (works for a range of skin tones)
        skin_mask = (
            (r > 60) & (g > 40) & (b > 20) &
            (r > g) & (r > b) &
            (np.abs(r - g) > 15) &
            (r - b > 15) &
            (r < 250) & (g < 230) & (b < 230)
        )

        skin_ratio = float(skin_mask.mean())
        issues = []

        # Very high skin ratio in non-close-up might indicate skin-tone artifacts
        if skin_ratio > 0.6:
            issues.append("Very high skin-color ratio (possible artifact)")

        # Analyze skin blobs (connected regions)
        # Simple flood-fill-like blob counting using downsampled mask
        small_mask = Image.fromarray(skin_mask.astype(np.uint8) * 255).resize(
            (w // 4, h // 4), Image.NEAREST
        )
        small_arr = np.array(small_mask) > 127
        blob_count = self._count_blobs(small_arr)

        # Many small skin blobs might indicate fragmented hands
        if blob_count > 10 and skin_ratio > 0.05:
            issues.append(f"Fragmented skin regions ({blob_count} blobs)")

        # Check aspect ratios of larger skin blobs
        # (hands are elongated, fist-like blobs are roughly square)
        # This is a rough heuristic and can't catch extra fingers

        confidence = 0.7  # Lower confidence for heuristic method
        if issues:
            confidence -= len(issues) * 0.15
        confidence = max(0.1, min(1.0, confidence))

        return {
            "hands_detected": -1,  # Unknown — heuristic can't count precisely
            "issues": issues,
            "confidence": round(confidence, 3),
            "pass": confidence >= 0.5,
            "details": {
                "skin_ratio": round(skin_ratio, 4),
                "blob_count": blob_count,
            },
            "method": "heuristic",
        }

    @staticmethod
    def _count_blobs(mask: np.ndarray) -> int:
        """Simple blob counting via flood-fill on a boolean mask."""
        visited = np.zeros_like(mask, dtype=bool)
        h, w = mask.shape
        count = 0
        min_blob_size = 4  # Minimum pixels to count as blob

        for y in range(h):
            for x in range(w):
                if mask[y, x] and not visited[y, x]:
                    # Flood fill
                    blob_size = 0
                    stack = [(y, x)]
                    while stack:
                        cy, cx = stack.pop()
                        if cy < 0 or cy >= h or cx < 0 or cx >= w:
                            continue
                        if visited[cy, cx] or not mask[cy, cx]:
                            continue
                        visited[cy, cx] = True
                        blob_size += 1
                        stack.extend([
                            (cy - 1, cx), (cy + 1, cx),
                            (cy, cx - 1), (cy, cx + 1),
                        ])
                    if blob_size >= min_blob_size:
                        count += 1

        return count

    def close(self):
        """Release detector resources."""
        if self._detector is not None:
            self._detector.close()
            self._detector = None


# ===================================================================
# 2. FaceConsistencyChecker
# ===================================================================

class FaceConsistencyChecker:
    """Compare face consistency across panels using the same character.

    Primary: MediaPipe Face Landmarker + cropped face SSIM comparison.
    Fallback: PIL-based face region SSIM using center crop assumption.

    The checker stores a reference embedding per character, then compares
    each new panel's detected face against the reference.
    """

    # Cosine similarity thresholds
    THRESHOLD_WARNING = 0.65    # face_drift
    THRESHOLD_ERROR = 0.50      # face_mismatch

    def __init__(self, model_path: str | None = None):
        """Initialize face consistency checker.

        Args:
            model_path: Path to mediapipe face_landmarker.task model.
        """
        self._face_detector = None
        self._use_mediapipe = _MEDIAPIPE_AVAILABLE

        if self._use_mediapipe:
            face_model = model_path or str(MODELS_DIR / "face_landmarker.task")
            if os.path.exists(face_model):
                try:
                    options = _mp_vision.FaceLandmarkerOptions(
                        base_options=_mp_base(model_asset_path=face_model),
                        running_mode=_mp_vision.RunningMode.IMAGE,
                        num_faces=4,
                        min_face_detection_confidence=0.4,
                        min_face_presence_confidence=0.4,
                        output_face_blendshapes=False,
                        output_facial_transformation_matrixes=False,
                    )
                    self._face_detector = _mp_vision.FaceLandmarker.create_from_options(options)
                except Exception as e:
                    logger.warning(f"MediaPipe face landmarker init failed: {e}")
                    self._use_mediapipe = False
            else:
                logger.warning(f"Face model not found at {face_model}, using fallback")
                self._use_mediapipe = False

        # Reference face crops per character_id
        self._references: dict[str, np.ndarray] = {}

    def set_reference(self, character_id: str, image: Image.Image | str):
        """Extract and store a face crop from a reference image.

        Args:
            character_id: Character identifier.
            image: Reference image (PIL Image or path).
        """
        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")

        face_crop = self._extract_face(image)
        if face_crop is not None:
            # Normalize to 128x128 for comparison
            face_resized = face_crop.resize((128, 128), Image.LANCZOS)
            self._references[character_id] = np.array(face_resized, dtype=np.float64)
            logger.info(f"Face reference set for character '{character_id}'")
        else:
            logger.warning(f"No face found in reference for '{character_id}'")

    def check_panel(self, image: Image.Image | str,
                    character_id: str | None = None) -> dict:
        """Check face consistency of a panel against reference.

        Args:
            image: Panel image to check.
            character_id: Which character to compare against (if None, check all).

        Returns:
            {
                "faces_detected": int,
                "scores": [{"character_id": str, "similarity": float, "status": str}],
                "issues": [str],
                "confidence": float,
                "pass": bool,
            }
        """
        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")

        faces = self._extract_all_faces(image)

        if not faces:
            return {
                "faces_detected": 0,
                "scores": [],
                "issues": [],
                "confidence": 0.8,  # No faces might be OK (action shot, etc)
                "pass": True,
            }

        scores = []
        issues = []

        # Compare each detected face against reference(s)
        chars_to_check = [character_id] if character_id else list(self._references.keys())

        for face_crop in faces:
            face_resized = face_crop.resize((128, 128), Image.LANCZOS)
            face_arr = np.array(face_resized, dtype=np.float64)

            best_match = None
            best_sim = -1.0

            for char_id in chars_to_check:
                if char_id not in self._references:
                    continue

                ref_arr = self._references[char_id]
                sim = self._ssim_similarity(ref_arr, face_arr)

                if sim > best_sim:
                    best_sim = sim
                    best_match = char_id

            if best_match is not None:
                status = "ok"
                if best_sim < self.THRESHOLD_ERROR:
                    status = "face_mismatch"
                    issues.append(f"Face mismatch for '{best_match}' (sim={best_sim:.3f})")
                elif best_sim < self.THRESHOLD_WARNING:
                    status = "face_drift"
                    issues.append(f"Face drift for '{best_match}' (sim={best_sim:.3f})")

                scores.append({
                    "character_id": best_match,
                    "similarity": round(best_sim, 4),
                    "status": status,
                })

        # Aggregate confidence
        if scores:
            avg_sim = sum(s["similarity"] for s in scores) / len(scores)
            confidence = avg_sim
        else:
            confidence = 0.6  # Can't compare — medium confidence

        return {
            "faces_detected": len(faces),
            "scores": scores,
            "issues": issues,
            "confidence": round(max(0.0, min(1.0, confidence)), 3),
            "pass": all(s["status"] != "face_mismatch" for s in scores),
        }

    def check_all_panels(self, panels: list[dict], panels_dir: str,
                         characters: list[dict] = None) -> dict:
        """Check face consistency across all panels.

        Args:
            panels: List of panel dicts from story plan.
            panels_dir: Directory containing generated panel images.
            characters: Character list (for setting references from char refs).

        Returns:
            Aggregated face consistency report.
        """
        per_panel = {}
        all_issues = []

        for panel in panels:
            pid = panel.get("id", "")
            # Find panel image
            panel_path = None
            for ext in [".png", ".jpg", ".jpeg"]:
                candidate = Path(panels_dir) / f"{pid}{ext}"
                if candidate.exists():
                    panel_path = str(candidate)
                    break
                # Also check comfyui-style names
                candidates = list(Path(panels_dir).glob(f"*{pid}*{ext}"))
                if candidates:
                    panel_path = str(candidates[0])
                    break

            if not panel_path:
                continue

            # Check against characters present in this panel
            chars_present = panel.get("characters_present", [])
            result = self.check_panel(panel_path)

            per_panel[pid] = result
            all_issues.extend(result.get("issues", []))

        # Aggregate stats
        all_scores = []
        for r in per_panel.values():
            all_scores.extend(s["similarity"] for s in r.get("scores", []))

        return {
            "panels_checked": len(per_panel),
            "total_faces": sum(r["faces_detected"] for r in per_panel.values()),
            "avg_similarity": round(sum(all_scores) / len(all_scores), 4) if all_scores else None,
            "min_similarity": round(min(all_scores), 4) if all_scores else None,
            "issues": all_issues,
            "per_panel": per_panel,
        }

    def _extract_face(self, image: Image.Image) -> Image.Image | None:
        """Extract the largest face crop from an image."""
        faces = self._extract_all_faces(image)
        if faces:
            # Return largest face (by pixel count)
            return max(faces, key=lambda f: f.size[0] * f.size[1])
        return None

    def _extract_all_faces(self, image: Image.Image) -> list[Image.Image]:
        """Extract all face crops from an image."""
        if self._use_mediapipe and self._face_detector is not None:
            return self._extract_faces_mediapipe(image)
        else:
            return self._extract_faces_heuristic(image)

    def _extract_faces_mediapipe(self, image: Image.Image) -> list[Image.Image]:
        """Extract face bounding boxes using MediaPipe Face Landmarker."""
        img_array = np.array(image)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_array)

        result = self._face_detector.detect(mp_image)

        faces = []
        w, h = image.size

        for face_landmarks in result.face_landmarks:
            # Compute bounding box from landmarks
            xs = [lm.x for lm in face_landmarks]
            ys = [lm.y for lm in face_landmarks]

            x_min = max(0, int(min(xs) * w) - 10)
            x_max = min(w, int(max(xs) * w) + 10)
            y_min = max(0, int(min(ys) * h) - 10)
            y_max = min(h, int(max(ys) * h) + 10)

            # Expand by 20% for context
            pad_x = int((x_max - x_min) * 0.2)
            pad_y = int((y_max - y_min) * 0.2)
            x_min = max(0, x_min - pad_x)
            x_max = min(w, x_max + pad_x)
            y_min = max(0, y_min - pad_y)
            y_max = min(h, y_max + pad_y)

            if (x_max - x_min) > 20 and (y_max - y_min) > 20:
                face_crop = image.crop((x_min, y_min, x_max, y_max))
                faces.append(face_crop)

        return faces

    def _extract_faces_heuristic(self, image: Image.Image) -> list[Image.Image]:
        """Heuristic face extraction — center crop of upper portion.

        In comic panels, faces are typically in the upper-center area.
        This is a rough fallback when MediaPipe is unavailable.
        """
        w, h = image.size

        # Assume face is in upper-center third
        face_w = w // 3
        face_h = h // 3
        x_center = w // 2
        y_upper = h // 4

        x1 = max(0, x_center - face_w // 2)
        x2 = min(w, x_center + face_w // 2)
        y1 = max(0, y_upper - face_h // 2)
        y2 = min(h, y_upper + face_h // 2)

        if (x2 - x1) > 20 and (y2 - y1) > 20:
            return [image.crop((x1, y1, x2, y2))]
        return []

    @staticmethod
    def _ssim_similarity(ref: np.ndarray, test: np.ndarray) -> float:
        """Compute structural similarity (SSIM) between two face crops.

        Simplified SSIM implementation — no external dependencies.
        Returns value in [0, 1] range.
        """
        # Convert to grayscale if RGB
        if ref.ndim == 3:
            ref_gray = 0.299 * ref[:, :, 0] + 0.587 * ref[:, :, 1] + 0.114 * ref[:, :, 2]
        else:
            ref_gray = ref.astype(np.float64)

        if test.ndim == 3:
            test_gray = 0.299 * test[:, :, 0] + 0.587 * test[:, :, 1] + 0.114 * test[:, :, 2]
        else:
            test_gray = test.astype(np.float64)

        # Ensure same shape
        if ref_gray.shape != test_gray.shape:
            # Resize test to match ref
            from PIL import Image as _Image
            test_pil = _Image.fromarray(test_gray.astype(np.uint8))
            test_pil = test_pil.resize((ref_gray.shape[1], ref_gray.shape[0]), _Image.LANCZOS)
            test_gray = np.array(test_pil, dtype=np.float64)

        C1 = (0.01 * 255) ** 2
        C2 = (0.03 * 255) ** 2

        mu_x = ref_gray.mean()
        mu_y = test_gray.mean()
        sigma_x_sq = ref_gray.var()
        sigma_y_sq = test_gray.var()
        sigma_xy = ((ref_gray - mu_x) * (test_gray - mu_y)).mean()

        ssim = ((2 * mu_x * mu_y + C1) * (2 * sigma_xy + C2)) / \
               ((mu_x ** 2 + mu_y ** 2 + C1) * (sigma_x_sq + sigma_y_sq + C2))

        # Normalize to [0, 1] range (SSIM can be negative)
        return max(0.0, float(ssim))

    def close(self):
        """Release detector resources."""
        if self._face_detector is not None:
            self._face_detector.close()
            self._face_detector = None


# ===================================================================
# 3. TextArtifactChecker
# ===================================================================

class TextArtifactChecker:
    """Detect unwanted text artifacts in AI-generated images.

    AI image generators often produce garbled text-like artifacts.
    This checker uses edge and frequency analysis to detect such patterns.

    No OCR dependency — uses PIL-based heuristics:
    - High-frequency horizontal patterns (text-like)
    - Small high-contrast rectangular regions
    - Regular spacing patterns typical of text
    """

    # Minimum confidence to flag text artifacts
    THRESHOLD = 0.4

    def check(self, image: Image.Image | str) -> dict:
        """Check for unwanted text artifacts.

        Returns:
            {
                "text_regions_suspected": int,
                "issues": [str],
                "confidence": float (0-1),
                "pass": bool,
            }
        """
        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")

        gray = np.array(image.convert("L"), dtype=np.float64)
        h, w = gray.shape
        issues = []

        # 1. Horizontal edge density analysis
        # Text produces strong horizontal edges with regular spacing
        h_edges = np.abs(np.diff(gray, axis=1))  # horizontal gradients
        v_edges = np.abs(np.diff(gray, axis=0))  # vertical gradients

        # Text has high h-edge to v-edge ratio in text regions
        h_mean = float(h_edges.mean())
        v_mean = float(v_edges.mean())

        # 2. Scan for "text-like" regions using sliding window
        text_regions = 0
        window_h = max(16, h // 20)
        window_w = max(32, w // 10)
        step = max(8, min(window_h, window_w) // 2)

        for y in range(0, h - window_h, step):
            for x in range(0, w - window_w, step):
                region = gray[y:y + window_h, x:x + window_w]

                # Check for text-like characteristics:
                # - High local contrast
                # - Regular horizontal patterns
                # - Many thin horizontal/vertical edges

                local_std = float(region.std())
                if local_std < 15:  # Too uniform — no text
                    continue

                # Horizontal frequency analysis (text has regular vertical strokes)
                row_means = region.mean(axis=1)
                row_std = float(row_means.std())

                col_means = region.mean(axis=0)
                col_std = float(col_means.std())

                # Text regions have high column variance (vertical strokes)
                # and moderate row variance (line spacing)
                if col_std > 20 and row_std > 10:
                    # Check for regular spacing (text-like periodicity)
                    # Simple: count zero-crossings of detrended row means
                    detrended = row_means - row_means.mean()
                    zero_crossings = np.sum(np.abs(np.diff(np.sign(detrended))) > 0)
                    periodicity = zero_crossings / len(row_means)

                    # Text typically has 0.3-0.7 zero-crossing rate
                    if 0.2 < periodicity < 0.8:
                        text_regions += 1

        # Score based on number of text-like regions
        total_windows = max(1, ((h - window_h) // step) * ((w - window_w) // step))
        text_ratio = text_regions / total_windows

        if text_ratio > 0.15:
            issues.append(f"High text artifact density ({text_ratio:.2%} of regions)")
        elif text_ratio > 0.05:
            issues.append(f"Moderate text artifact presence ({text_ratio:.2%})")

        # Confidence: high if we're sure about presence/absence
        if text_ratio > 0.15:
            confidence = 0.3  # Low confidence in image quality (likely has text)
        elif text_ratio > 0.05:
            confidence = 0.5
        elif text_ratio < 0.02:
            confidence = 0.9  # Confident: no text
        else:
            confidence = 0.7

        return {
            "text_regions_suspected": text_regions,
            "text_ratio": round(text_ratio, 4),
            "issues": issues,
            "confidence": round(confidence, 3),
            "pass": confidence >= self.THRESHOLD,
        }


# ===================================================================
# 4. QualityGateRunner — Orchestrator
# ===================================================================

@dataclass
class QualityCheckResult:
    """Result from a single quality check."""
    check_name: str
    passed: bool
    confidence: float
    issues: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


@dataclass
class PanelQualityReport:
    """Aggregated quality report for a panel."""
    panel_id: str
    image_path: str
    overall_score: float
    passed: bool
    checks: list[QualityCheckResult] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    retry_count: int = 0
    flagged_for_review: bool = False
    inpaint_suggestions: list[dict] = field(default_factory=list)


class QualityGateRunner:
    """Orchestrate all quality checks per panel with auto-retry logic.

    Checks:
        1. Hand quality (MediaPipe or heuristic)
        2. Face consistency (SSIM-based comparison)
        3. Composition (delegates to quality_tracker.py)
        4. Text artifact detection

    Scoring:
        Weighted average of all check confidences.
        If overall < threshold → auto-retry with modified params.

    Integration:
        Called by comic_pipeline.py after panel generation.
    """

    # Check weights for overall scoring
    WEIGHTS = {
        "hand_quality": 0.25,
        "face_consistency": 0.25,
        "composition": 0.25,
        "text_artifacts": 0.25,
    }

    def __init__(self, threshold: float = 0.6, max_retries: int = 2,
                 cfg_bump: float = 0.05):
        """Initialize the quality gate runner.

        Args:
            threshold: Minimum overall score to pass (0-1).
            max_retries: Max auto-retry attempts.
            cfg_bump: CFG scale increase per retry (+5% default).
        """
        self.threshold = threshold
        self.max_retries = max_retries
        self.cfg_bump = cfg_bump

        self._hand_checker = HandQualityChecker()
        self._face_checker = FaceConsistencyChecker()
        self._text_checker = TextArtifactChecker()

        # Optional: import quality_tracker for composition scoring
        self._composition_scorer = None
        try:
            from quality_tracker import score_panel as _score_panel
            self._composition_scorer = _score_panel
        except ImportError:
            logger.warning("quality_tracker.py not available for composition scoring")

    def set_face_reference(self, character_id: str, image: Image.Image | str):
        """Set a face reference for a character.

        Args:
            character_id: Character ID.
            image: Reference image.
        """
        self._face_checker.set_reference(character_id, image)

    def check_panel(self, image_path: str, panel_id: str = "",
                    character_id: str | None = None) -> PanelQualityReport:
        """Run all quality checks on a single panel.

        Args:
            image_path: Path to generated panel image.
            panel_id: Panel identifier.
            character_id: Character to check face against.

        Returns:
            PanelQualityReport with all check results.
        """
        if not panel_id:
            panel_id = Path(image_path).stem

        img = Image.open(image_path).convert("RGB")
        checks = []
        all_issues = []
        inpaint_suggestions = []

        # --- 1. Hand Quality ---
        hand_result = self._hand_checker.check(img)
        hand_check = QualityCheckResult(
            check_name="hand_quality",
            passed=hand_result["pass"],
            confidence=hand_result["confidence"],
            issues=hand_result["issues"],
            details=hand_result.get("details", {}),
        )
        checks.append(hand_check)
        all_issues.extend(hand_result["issues"])

        # Generate inpaint suggestion for hand issues
        if not hand_result["pass"] and hand_result.get("details"):
            details = hand_result["details"]
            if isinstance(details, list):
                for hand_detail in details:
                    if hand_detail.get("landmarks"):
                        inpaint_suggestions.append({
                            "type": "hand",
                            "landmarks": hand_detail["landmarks"],
                            "reason": "; ".join(hand_detail.get("finger_issues", [])),
                        })

        # --- 2. Face Consistency ---
        face_result = self._face_checker.check_panel(img, character_id)
        face_check = QualityCheckResult(
            check_name="face_consistency",
            passed=face_result["pass"],
            confidence=face_result["confidence"],
            issues=face_result["issues"],
            details={
                "faces_detected": face_result["faces_detected"],
                "scores": face_result["scores"],
            },
        )
        checks.append(face_check)
        all_issues.extend(face_result["issues"])

        # --- 3. Composition Score (from quality_tracker) ---
        if self._composition_scorer:
            try:
                panel_score = self._composition_scorer(image_path, panel_id,
                                                       composition=True)
                comp_confidence = panel_score.overall_score / 100.0
                comp_passed = comp_confidence >= 0.5
                comp_check = QualityCheckResult(
                    check_name="composition",
                    passed=comp_passed,
                    confidence=comp_confidence,
                    issues=[] if comp_passed else [
                        f"Low composition score: {panel_score.overall_score:.1f}/100"
                    ],
                    details={
                        "technical_score": panel_score.technical_score,
                        "composition_score": panel_score.composition_score,
                        "overall_score": panel_score.overall_score,
                    },
                )
                checks.append(comp_check)
                if not comp_passed:
                    all_issues.append(f"Low composition score: {panel_score.overall_score:.1f}")
            except Exception as e:
                logger.warning(f"Composition scoring failed: {e}")
                checks.append(QualityCheckResult(
                    check_name="composition",
                    passed=True,
                    confidence=0.5,
                    issues=[f"Composition check error: {str(e)}"],
                ))
        else:
            # No composition scorer available — skip with neutral score
            checks.append(QualityCheckResult(
                check_name="composition",
                passed=True,
                confidence=0.6,
                issues=[],
            ))

        # --- 4. Text Artifact Check ---
        text_result = self._text_checker.check(img)
        text_check = QualityCheckResult(
            check_name="text_artifacts",
            passed=text_result["pass"],
            confidence=text_result["confidence"],
            issues=text_result["issues"],
            details={
                "text_regions_suspected": text_result["text_regions_suspected"],
                "text_ratio": text_result.get("text_ratio", 0),
            },
        )
        checks.append(text_check)
        all_issues.extend(text_result["issues"])

        # --- Compute overall score ---
        weighted_sum = 0.0
        weight_total = 0.0
        for check in checks:
            w = self.WEIGHTS.get(check.check_name, 0.25)
            weighted_sum += check.confidence * w
            weight_total += w

        overall_score = weighted_sum / weight_total if weight_total > 0 else 0.5
        passed = overall_score >= self.threshold

        return PanelQualityReport(
            panel_id=panel_id,
            image_path=image_path,
            overall_score=round(overall_score, 4),
            passed=passed,
            checks=checks,
            issues=all_issues,
            inpaint_suggestions=inpaint_suggestions,
        )

    def run_with_retry(self, panel: dict, characters: list, style: str,
                       preset_name: str, output_dir: str,
                       initial_result: dict,
                       char_refs: dict | None = None,
                       all_panels: list | None = None) -> tuple[dict, PanelQualityReport]:
        """Run quality gate with auto-retry on failure.

        If the panel fails quality checks, re-generates with:
        - Slightly higher CFG scale
        - Different seed
        - Same prompt

        Args:
            panel: Panel definition dict.
            characters: Character list.
            style: Art style.
            preset_name: ComfyUI preset.
            output_dir: Output directory.
            initial_result: Generation result from first attempt.
            char_refs: Character references for IPAdapter.
            all_panels: Full panel list for context.

        Returns:
            Tuple of (best generation result, quality report).
        """
        best_result = initial_result
        best_report = self.check_panel(
            initial_result["path"],
            panel.get("id", ""),
        )

        if best_report.passed:
            return best_result, best_report

        # Import panel_generator for re-generation
        try:
            from panel_generator import generate_panel, load_presets
        except ImportError:
            logger.warning("Cannot import panel_generator for retry")
            best_report.flagged_for_review = True
            return best_result, best_report

        presets = load_presets()
        preset_config = presets.get(preset_name, {})
        original_cfg = preset_config.get("cfg", 2.0)

        for retry in range(1, self.max_retries + 1):
            logger.info(
                f"Quality gate retry {retry}/{self.max_retries} for "
                f"panel {panel.get('id', '?')} (score={best_report.overall_score:.3f})"
            )

            # Modify generation parameters
            import random
            new_seed = random.randint(0, 2**32 - 1)

            # Temporarily bump CFG in preset
            bumped_cfg = original_cfg * (1 + self.cfg_bump * retry)
            preset_config["cfg"] = bumped_cfg

            try:
                retry_result = generate_panel(
                    panel=panel,
                    characters=characters,
                    style=style,
                    preset_name=preset_name,
                    output_dir=output_dir,
                    char_refs=char_refs,
                    seed=new_seed,
                    all_panels=all_panels,
                )

                retry_report = self.check_panel(
                    retry_result["path"],
                    panel.get("id", ""),
                )
                retry_report.retry_count = retry

                if retry_report.overall_score > best_report.overall_score:
                    best_result = retry_result
                    best_report = retry_report

                if retry_report.passed:
                    logger.info(f"Retry {retry} passed (score={retry_report.overall_score:.3f})")
                    break

            except Exception as e:
                logger.warning(f"Retry {retry} failed: {e}")

        # Restore original CFG
        preset_config["cfg"] = original_cfg

        if not best_report.passed:
            best_report.flagged_for_review = True
            logger.warning(
                f"Panel {panel.get('id', '?')} failed all retries "
                f"(best score={best_report.overall_score:.3f}), flagged for review"
            )

        return best_result, best_report

    def run_batch(self, panels: list[dict], panels_dir: str,
                  panel_results: dict) -> dict:
        """Run quality gates on all panels (post-generation batch check).

        Args:
            panels: List of panel dicts from story plan.
            panels_dir: Directory containing panel images.
            panel_results: Dict mapping panel_id → generation result dict.

        Returns:
            Batch quality report.
        """
        reports = {}
        total_passed = 0
        total_failed = 0
        all_issues = []

        for panel in panels:
            pid = panel.get("id", "")
            if pid not in panel_results:
                continue

            result = panel_results[pid]
            image_path = result.get("path", "")
            if not image_path or not os.path.exists(image_path):
                continue

            report = self.check_panel(image_path, pid)
            reports[pid] = report

            if report.passed:
                total_passed += 1
            else:
                total_failed += 1
                all_issues.extend(report.issues)

        return {
            "total_panels": len(reports),
            "passed": total_passed,
            "failed": total_failed,
            "pass_rate": round(total_passed / max(1, len(reports)), 3),
            "issues": all_issues,
            "reports": {pid: asdict(r) for pid, r in reports.items()},
        }

    def close(self):
        """Release all resources."""
        self._hand_checker.close()
        self._face_checker.close()


# ===================================================================
# CLI — standalone usage
# ===================================================================

def main():
    """CLI entry point for quality gate checking."""
    import argparse

    parser = argparse.ArgumentParser(
        description="ComicMaster Quality Gates — check generated panels"
    )
    parser.add_argument("images", nargs="+", help="Panel image(s) to check")
    parser.add_argument("--threshold", type=float, default=0.6,
                        help="Pass/fail threshold (default: 0.6)")
    parser.add_argument("--reference", "-r", default=None,
                        help="Face reference image for consistency check")
    parser.add_argument("--character", "-c", default="default",
                        help="Character ID for face reference")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    runner = QualityGateRunner(threshold=args.threshold)

    # Set face reference if provided
    if args.reference:
        runner.set_face_reference(args.character, args.reference)

    results = []

    for image_path in args.images:
        if not os.path.exists(image_path):
            print(f"⚠️  File not found: {image_path}")
            continue

        report = runner.check_panel(image_path)

        if args.json:
            results.append(asdict(report))
        else:
            status = "✅ PASS" if report.passed else "❌ FAIL"
            print(f"\n{status} [{report.overall_score:.3f}] {report.panel_id}")
            for check in report.checks:
                c_status = "✅" if check.passed else "❌"
                print(f"  {c_status} {check.check_name}: "
                      f"conf={check.confidence:.3f} "
                      f"{'| ' + '; '.join(check.issues) if check.issues else ''}")
            if report.issues:
                print(f"  Issues: {len(report.issues)}")
                for issue in report.issues:
                    print(f"    - {issue}")
            if report.inpaint_suggestions:
                print(f"  Inpaint suggestions: {len(report.inpaint_suggestions)}")

    if args.json:
        print(json.dumps(results, indent=2, default=str))

    runner.close()


if __name__ == "__main__":
    main()
