#!/usr/bin/env python3
"""
Face Validator for ComicMaster.

Validates character face consistency across panels by comparing face embeddings
from generated panels against reference images.

Supports three backends (in preference order):
1. insightface + onnxruntime — best quality embeddings
2. face_recognition — simpler but effective
3. PIL-based fallback — color histogram heuristic (no ML dependency)

Usage:
    validator = FaceValidator()
    score = validator.compare(ref_image_path, panel_image_path)
    if score < SIMILARITY_THRESHOLD:
        # Retry generation
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger("comicmaster.face_validator")

# --- Configuration ---
SIMILARITY_THRESHOLD = 0.7  # Cosine similarity threshold
MAX_RETRIES = 2  # Max retry attempts when face similarity is below threshold
MIN_FACE_SIZE = 40  # Minimum face bounding box size in pixels


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    a = a.flatten().astype(np.float64)
    b = b.flatten().astype(np.float64)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


# ── Backend: InsightFace ──────────────────────────────────────────────────

class InsightFaceBackend:
    """Face embedding extraction using InsightFace (ArcFace)."""

    def __init__(self):
        try:
            from insightface.app import FaceAnalysis
            self.app = FaceAnalysis(
                name="buffalo_l",
                providers=["CPUExecutionProvider"],
            )
            self.app.prepare(ctx_id=-1, det_size=(640, 640))
            self.available = True
            logger.info("InsightFace backend initialized")
        except Exception as e:
            self.available = False
            self.app = None
            logger.debug(f"InsightFace not available: {e}")

    def get_embedding(self, image_path: str) -> Optional[np.ndarray]:
        """Extract face embedding from image. Returns None if no face found."""
        if not self.available:
            return None
        img = np.array(Image.open(image_path).convert("RGB"))
        # InsightFace expects BGR
        img_bgr = img[:, :, ::-1]
        faces = self.app.get(img_bgr)
        if not faces:
            logger.debug(f"No face detected in {image_path}")
            return None
        # Use the largest face (by bounding box area)
        largest = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        return largest.embedding

    def compare(self, ref_path: str, panel_path: str) -> Optional[float]:
        """Compare face embeddings. Returns cosine similarity or None."""
        emb_ref = self.get_embedding(ref_path)
        emb_panel = self.get_embedding(panel_path)
        if emb_ref is None or emb_panel is None:
            return None
        return _cosine_similarity(emb_ref, emb_panel)


# ── Backend: face_recognition ─────────────────────────────────────────────

class FaceRecognitionBackend:
    """Face embedding extraction using the face_recognition package."""

    def __init__(self):
        try:
            import face_recognition  # noqa: F401
            self._fr = face_recognition
            self.available = True
            logger.info("face_recognition backend initialized")
        except Exception as e:
            self.available = False
            self._fr = None
            logger.debug(f"face_recognition not available: {e}")

    def get_embedding(self, image_path: str) -> Optional[np.ndarray]:
        """Extract face encoding. Returns None if no face found."""
        if not self.available:
            return None
        img = self._fr.load_image_file(image_path)
        encodings = self._fr.face_encodings(img)
        if not encodings:
            logger.debug(f"No face detected in {image_path}")
            return None
        return np.array(encodings[0])

    def compare(self, ref_path: str, panel_path: str) -> Optional[float]:
        """Compare face encodings. Returns cosine similarity or None."""
        emb_ref = self.get_embedding(ref_path)
        emb_panel = self.get_embedding(panel_path)
        if emb_ref is None or emb_panel is None:
            return None
        return _cosine_similarity(emb_ref, emb_panel)


# ── Backend: PIL Histogram Fallback ───────────────────────────────────────

class PILHistogramBackend:
    """Fallback face comparison using color histogram of the upper-center region.

    This is a heuristic — it compares the color distribution of the face region
    (upper-center crop of the image) rather than true face embeddings. Useful
    when no ML face detection package is available.
    """

    def __init__(self):
        self.available = True
        logger.info("PIL histogram fallback backend initialized")

    def _extract_face_region(self, image_path: str) -> Optional[Image.Image]:
        """Crop the upper-center region (likely face area) from an image."""
        try:
            img = Image.open(image_path).convert("RGB")
        except Exception:
            return None

        w, h = img.size
        # Assume face is in upper-center third of the image
        crop_w = w // 3
        crop_h = h // 3
        left = (w - crop_w) // 2
        top = h // 8  # slightly below top edge
        right = left + crop_w
        bottom = top + crop_h

        face_crop = img.crop((left, top, right, bottom))
        # Resize to standard size for histogram comparison
        face_crop = face_crop.resize((128, 128), Image.LANCZOS)
        return face_crop

    def _histogram_vector(self, img: Image.Image) -> np.ndarray:
        """Get normalized color histogram as a vector."""
        hist_r = img.histogram()[:256]
        hist_g = img.histogram()[256:512]
        hist_b = img.histogram()[512:768]
        hist = np.array(hist_r + hist_g + hist_b, dtype=np.float64)
        total = hist.sum()
        if total > 0:
            hist /= total
        return hist

    def compare(self, ref_path: str, panel_path: str) -> Optional[float]:
        """Compare face regions using color histogram cosine similarity."""
        face_ref = self._extract_face_region(ref_path)
        face_panel = self._extract_face_region(panel_path)
        if face_ref is None or face_panel is None:
            return None
        hist_ref = self._histogram_vector(face_ref)
        hist_panel = self._histogram_vector(face_panel)
        return _cosine_similarity(hist_ref, hist_panel)


# ── Main Validator Class ──────────────────────────────────────────────────

class FaceValidator:
    """Multi-backend face validator.

    Tries backends in order of quality:
    1. InsightFace (ArcFace embeddings)
    2. face_recognition (dlib-based)
    3. PIL histogram fallback

    Usage:
        validator = FaceValidator()
        result = validator.validate_panel(ref_image_path, panel_image_path)
        # result = {"similarity": 0.85, "passed": True, "backend": "insightface"}
    """

    def __init__(self, threshold: float = SIMILARITY_THRESHOLD):
        self.threshold = threshold
        self.backend = None
        self.backend_name = "none"

        # Try backends in preference order
        insightface = InsightFaceBackend()
        if insightface.available:
            self.backend = insightface
            self.backend_name = "insightface"
            return

        face_rec = FaceRecognitionBackend()
        if face_rec.available:
            self.backend = face_rec
            self.backend_name = "face_recognition"
            return

        # Fallback
        pil = PILHistogramBackend()
        self.backend = pil
        self.backend_name = "pil_histogram"
        logger.warning(
            "Using PIL histogram fallback for face validation. "
            "Install insightface or face_recognition for better accuracy."
        )

    def validate_panel(
        self,
        ref_image_path: str,
        panel_image_path: str,
        character_id: str = "",
    ) -> dict:
        """Validate a panel's face against the reference.

        Args:
            ref_image_path: Path to the character reference image.
            panel_image_path: Path to the generated panel image.
            character_id: Character ID for logging purposes.

        Returns:
            Dict with keys:
            - similarity: float (0.0-1.0) or None if no face detected
            - passed: bool (True if similarity >= threshold or no face detected)
            - backend: str (backend name used)
            - character_id: str
            - error: str or None
        """
        result = {
            "similarity": None,
            "passed": True,  # default to passed (no face = pass)
            "backend": self.backend_name,
            "character_id": character_id,
            "error": None,
        }

        if self.backend is None:
            result["error"] = "No face validation backend available"
            return result

        try:
            similarity = self.backend.compare(ref_image_path, panel_image_path)
        except Exception as e:
            result["error"] = str(e)
            logger.warning(f"Face validation error for {character_id}: {e}")
            return result

        if similarity is None:
            # No face detected in one or both images — can't validate
            result["error"] = "No face detected in reference or panel"
            logger.debug(f"No face detected for {character_id}")
            return result

        result["similarity"] = round(similarity, 4)
        result["passed"] = similarity >= self.threshold
        log_fn = logger.info if result["passed"] else logger.warning
        log_fn(
            f"Face validation [{character_id}]: "
            f"similarity={similarity:.4f} "
            f"{'✅ PASS' if result['passed'] else '❌ FAIL'} "
            f"(threshold={self.threshold}, backend={self.backend_name})"
        )
        return result

    def validate_panel_batch(
        self,
        ref_paths: dict[str, str],
        panel_image_path: str,
        characters_present: list[str],
    ) -> list[dict]:
        """Validate all characters present in a panel.

        Args:
            ref_paths: Dict mapping character_id → reference image path.
            panel_image_path: Path to the generated panel image.
            characters_present: List of character IDs present in the panel.

        Returns:
            List of validation result dicts (one per character).
        """
        results = []
        for char_id in characters_present:
            ref_path = ref_paths.get(char_id)
            if not ref_path or not os.path.exists(ref_path):
                results.append({
                    "similarity": None,
                    "passed": True,
                    "backend": self.backend_name,
                    "character_id": char_id,
                    "error": f"No reference image for {char_id}",
                })
                continue
            result = self.validate_panel(ref_path, panel_image_path, char_id)
            results.append(result)
        return results


def generate_quality_report(all_validations: list[dict]) -> str:
    """Generate a human-readable quality report from face validation results.

    Args:
        all_validations: List of validation result dicts from validate_panel calls.

    Returns:
        Formatted report string.
    """
    if not all_validations:
        return "📊 Face Validation Report: No validations performed."

    lines = ["📊 Face Validation Quality Report", "=" * 45]

    # Aggregate stats
    total = len(all_validations)
    with_scores = [v for v in all_validations if v.get("similarity") is not None]
    passed = [v for v in with_scores if v.get("passed")]
    failed = [v for v in with_scores if not v.get("passed")]
    no_face = [v for v in all_validations if v.get("similarity") is None]

    if with_scores:
        scores = [v["similarity"] for v in with_scores]
        avg_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)
        lines.append(f"  Total validations:   {total}")
        lines.append(f"  With face detected:  {len(with_scores)}")
        lines.append(f"  Passed (≥{SIMILARITY_THRESHOLD}):     {len(passed)}")
        lines.append(f"  Failed (<{SIMILARITY_THRESHOLD}):     {len(failed)}")
        lines.append(f"  No face detected:    {len(no_face)}")
        lines.append(f"  Average similarity:  {avg_score:.4f}")
        lines.append(f"  Min similarity:      {min_score:.4f}")
        lines.append(f"  Max similarity:      {max_score:.4f}")
        lines.append(f"  Backend:             {with_scores[0].get('backend', '?')}")
    else:
        lines.append(f"  Total validations: {total}")
        lines.append(f"  No faces detected in any panel.")

    # Per-character breakdown
    char_scores: dict[str, list[float]] = {}
    for v in with_scores:
        cid = v.get("character_id", "unknown")
        char_scores.setdefault(cid, []).append(v["similarity"])

    if char_scores:
        lines.append("")
        lines.append("  Per-Character Breakdown:")
        lines.append("  " + "-" * 40)
        for cid, scores in sorted(char_scores.items()):
            avg = sum(scores) / len(scores)
            mn = min(scores)
            mx = max(scores)
            status = "✅" if avg >= SIMILARITY_THRESHOLD else "⚠️"
            lines.append(
                f"  {status} {cid}: avg={avg:.4f} min={mn:.4f} max={mx:.4f} ({len(scores)} panels)"
            )

    # Failed panels detail
    if failed:
        lines.append("")
        lines.append("  ❌ Failed Panels:")
        for v in failed:
            lines.append(
                f"    - {v.get('character_id', '?')}: {v.get('similarity', 0):.4f}"
            )

    return "\n".join(lines)


# ── CLI Test ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    validator = FaceValidator()
    print(f"Backend: {validator.backend_name}")

    if len(sys.argv) >= 3:
        ref_path = sys.argv[1]
        panel_path = sys.argv[2]
        result = validator.validate_panel(ref_path, panel_path, "test_char")
        print(f"Result: {result}")
    else:
        print("Usage: python face_validator.py <ref_image> <panel_image>")
        print("  Or import FaceValidator in your code.")
