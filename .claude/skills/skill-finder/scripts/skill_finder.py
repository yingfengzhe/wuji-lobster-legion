#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skill Finder - Discover and recommend skills based on user needs.

Usage:
    python skill_finder.py analyze --query "user's request"
"""

import argparse
import json
import math
import os
import re
import shutil
import sys
import tempfile
import time
import traceback
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

# Configure UTF-8 encoding for console output (Windows compatibility)
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

API_BASE_URL = os.environ.get(
    "APP_SKILL_FINDER_BASE_URL", "http://skill-finder.mulerun.com/api/v1"
)
if API_BASE_URL is None:
    print("Error: Skill finder API endpoint is not set", file=sys.stderr)
    sys.exit(1)

SESSION_ID = os.environ.get("MULE_SESSION_ID", None)

# Debug mode: set to True to print full stack traces on errors
DEBUG_MODE = os.environ.get("SKILL_FINDER_DEBUG", "").lower() in ("1", "true", "yes")


# HTTP wrapper functions for easy library switching
class HTTPPostRedirectHandler(HTTPRedirectHandler):
    """Custom handler to allow POST redirects (307/308)"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Return a Request or None in response to a redirect."""
        m = req.get_method()
        if code in (307, 308) and m == "POST":
            # Preserve POST data and method on 307/308 redirects
            return Request(
                newurl,
                data=req.data,
                headers=req.headers,
                origin_req_host=req.origin_req_host,
                unverifiable=req.unverifiable,
            )
        else:
            # Default behavior for other codes
            return HTTPRedirectHandler.redirect_request(
                self, req, fp, code, msg, headers, newurl
            )


def http_get(url, timeout=30):
    """
    Perform HTTP GET request.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        dict with keys: status_code, headers, content (bytes)

    Raises:
        HTTPError: For HTTP errors
        URLError: For connection errors
    """
    req = Request(url)
    req.add_header("User-Agent", "skill-finder/1.0")
    if SESSION_ID is not None:
        req.add_header("X-Session-Id", SESSION_ID)

    with urlopen(req, timeout=timeout) as response:
        return {
            "status_code": response.status,
            "headers": dict(response.headers),
            "content": response.read(),
        }


def http_post_json(url, data, timeout=30):
    """
    Perform HTTP POST request with JSON data.

    Args:
        url: URL to post to
        data: Dictionary to send as JSON
        timeout: Request timeout in seconds

    Returns:
        dict with keys: status_code, headers, content (bytes)

    Raises:
        HTTPError: For HTTP errors
        URLError: For connection errors
    """
    json_data = json.dumps(data).encode("utf-8")
    req = Request(url, data=json_data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "skill-finder/1.0")
    if SESSION_ID is not None:
        req.add_header("X-Session-Id", SESSION_ID)

    # Use custom opener that handles POST redirects
    opener = build_opener(HTTPPostRedirectHandler)
    with opener.open(req, timeout=timeout) as response:
        return {
            "status_code": response.status,
            "headers": dict(response.headers),
            "content": response.read(),
        }


def _sanitize_filename(filename):
    """
    Sanitize filename for Windows compatibility by removing invalid characters.

    Windows disallows: < > : " / \\ | ? *
    Also removes control characters and handles reserved names.
    """
    # Remove or replace invalid Windows filename characters
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename)

    # Remove leading/trailing spaces and periods
    sanitized = sanitized.strip(". ")

    # Handle reserved Windows names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
    name_without_ext = Path(sanitized).stem.upper()
    if name_without_ext in reserved_names:
        sanitized = f"_{sanitized}"

    # Ensure we have a valid filename
    if not sanitized or sanitized == ".":
        sanitized = "unnamed_skill"

    return sanitized


def _safe_extract_zip(zip_ref, extract_path, max_size=100 * 1024 * 1024):
    """
    Safely extract zip file with path traversal and zip bomb protection.

    Args:
        zip_ref: ZipFile object
        extract_path: Target extraction directory
        max_size: Maximum allowed total uncompressed size (default 100MB)

    Raises:
        ValueError: If path traversal detected or size limit exceeded
    """
    extract_path = Path(extract_path).resolve()
    total_size = 0

    for member in zip_ref.namelist():
        # Validate path - prevent path traversal (zip slip)
        member_path = (extract_path / member).resolve()
        try:
            member_path.relative_to(extract_path)
        except ValueError:
            raise ValueError(f"Path traversal attempt detected: {member}")

        # Check size - prevent zip bombs
        info = zip_ref.getinfo(member)
        total_size += info.file_size
        if total_size > max_size:
            raise ValueError(
                f"Extracted size exceeds limit ({max_size} bytes): {total_size} bytes"
            )

        # Extract individual member
        zip_ref.extract(member, extract_path)


def _get_cache_dir():
    """
    Get the cache directory for tracking installation attempts.
    Returns None if SESSION_ID is not set.

    Returns:
        Path object or None
    """
    if SESSION_ID is None:
        return None

    cache_dir = Path(tempfile.gettempdir()) / f"skill_finder_cache_{SESSION_ID}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _read_failed_cache():
    """
    Read failed installation cache from disk (no locking, best effort).

    Returns:
        dict mapping skill_name to {"timestamp": str, "attempts": int, "error": str}
    """
    cache_dir = _get_cache_dir()
    if cache_dir is None:
        return {}

    cache_file = cache_dir / "failed_installs.json"
    if not cache_file.exists():
        return {}

    # No locking on read - just read what's there
    try:
        with cache_file.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}  # Fail silently on read errors


def _write_failed_cache(cache_data):
    """
    Write failed installation cache to disk with write locking only.

    Args:
        cache_data: dict mapping skill_name to failure info
    """
    cache_dir = _get_cache_dir()
    if cache_dir is None:
        return

    cache_file = cache_dir / "failed_installs.json"
    lock_file = cache_dir / "failed_installs.lock"

    # Retry logic for write lock conflicts only
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Simple lock mechanism using lock file
            lock_file.touch()

            # Read existing data to merge (no retry, best effort)
            existing_data = {}
            if cache_file.exists():
                try:
                    with cache_file.open("r", encoding="utf-8") as f:
                        existing_data = json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass  # If read fails, start fresh

            # Merge new data
            existing_data.update(cache_data)

            # Write atomically using temp file + rename
            temp_file = cache_file.with_suffix(".tmp")
            with temp_file.open("w", encoding="utf-8") as f:
                json.dump(existing_data, f, indent=2)

            # Atomic rename
            temp_file.replace(cache_file)

            # Remove lock
            try:
                lock_file.unlink()
            except Exception:
                pass

            return
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(0.05 * (attempt + 1))  # Short backoff
            else:
                # Clean up lock file on final failure
                try:
                    lock_file.unlink()
                except Exception:
                    pass
                return  # Fail silently


def _track_failed_installs_batch(failures):
    """
    Track multiple failed skill installation attempts in a single write.

    Args:
        failures: dict mapping skill_name to error_msg
    """
    if not failures:
        return

    cache = _read_failed_cache()
    timestamp = datetime.now(timezone.utc).isoformat()

    updates = {}
    for skill_name, error_msg in failures.items():
        # Get existing entry or create new one
        entry = cache.get(skill_name, {"attempts": 0})
        entry["timestamp"] = timestamp
        entry["attempts"] = entry.get("attempts", 0) + 1
        entry["error"] = error_msg
        updates[skill_name] = entry

    # Single write for all failures
    _write_failed_cache(updates)


def _download_skill_from_api(skill_id, temp_dir):
    """
    Download a single skill from API.

    Args:
        skill_id: ID of the skill to download
        temp_dir: Temporary directory for downloads

    Returns:
        Dict with keys: skill_id, skill_name, status, temp_path/error
    """
    # Initialize variables at the top to avoid fragile locals() checks
    metadata = None
    skill_name = skill_id  # Default fallback

    try:
        # Step 1: Get skill metadata (download_url, skill_name) from API
        # Classify: ref_key starts with '@', otherwise treat as hash_aggregation_id
        if skill_id.startswith("@"):
            query_params = urlencode({"ref_key": skill_id})
        else:
            query_params = urlencode({"hash_aggregation_id": skill_id})
        metadata_url = f"{API_BASE_URL}/skills/download?{query_params}"
        metadata_response = http_get(metadata_url, timeout=30)
        metadata = json.loads(metadata_response["content"].decode("utf-8"))

        download_url = metadata.get("download_url")
        skill_name = _sanitize_filename(metadata.get("skill_name") or skill_id)

        if not download_url or not skill_name:
            return {
                "skill_id": skill_id,
                "skill_name": skill_name or skill_id,
                "status": "failed",
                "error": "Missing download_url or skill_name in API response",
            }

        # Step 2: Download the skill package from the download_url
        download_response = http_get(download_url, timeout=60)

        # Save to temporary location with sanitized filename
        filename = f"{_sanitize_filename(skill_name)}.zip"
        temp_file = temp_dir / f"{_sanitize_filename(skill_id)}_{filename}"
        temp_file.write_bytes(download_response["content"])

        return {
            "skill_id": skill_id,
            "skill_name": skill_name,
            "status": "success",
            "temp_path": temp_file,
            "filename": filename,
        }
    except (HTTPError, URLError) as e:
        return {
            "skill_id": skill_id,
            "skill_name": skill_name,  # Already initialized at function start
            "status": "failed",
            "error": str(e),
        }
    except Exception as e:
        return {
            "skill_id": skill_id,
            "skill_name": skill_name,  # Already initialized at function start
            "status": "failed",
            "error": f"Unexpected error: {str(e)}",
        }


def _download_skills_concurrently(skill_ids, temp_dir, status_dict, failed_installs):
    """
    Download multiple skills concurrently.

    Args:
        skill_ids: List of skill IDs to download
        temp_dir: Temporary directory for downloads
        status_dict: Dict to track skill status
        failed_installs: Dict to track failures by skill_name

    Returns:
        List of download results
    """
    download_results = []
    print("Downloading skills...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_skill = {
            executor.submit(_download_skill_from_api, skill_id, temp_dir): skill_id
            for skill_id in skill_ids
        }

        for future in as_completed(future_to_skill):
            result = future.result()
            download_results.append(result)

            if result["status"] == "success":
                print(f"[OK] Downloaded {result['skill_id']}")
            else:
                print(
                    f"[FAIL] Failed to download {result['skill_id']}: {result['error']}",
                    file=sys.stderr,
                )
                status_dict[result["skill_id"]] = "failed"
                failed_installs[result["skill_name"]] = result["error"]

    return download_results


def _deduplicate_downloads(download_results, status_dict):
    """
    Deduplicate download results by skill_name.

    Args:
        download_results: List of download results
        status_dict: Dict to track skill status

    Returns:
        List of unique download results
    """
    seen_skill_names = {}
    unique_downloads = []
    for result in download_results:
        if result["status"] == "success":
            skill_name = result["skill_name"]
            if skill_name not in seen_skill_names:
                seen_skill_names[skill_name] = result
                unique_downloads.append(result)
            else:
                print(
                    f"[SKIP] Skipping duplicate {result['skill_id']} (same skill_name as {seen_skill_names[skill_name]['skill_id']})"
                )
                status_dict[result["skill_id"]] = "skipped"

    return unique_downloads


def _extract_and_install_skills(
    unique_downloads, skills_dir, temp_dir, status_dict, failed_installs
):
    """
    Extract and install skills from downloaded zip files.

    Args:
        unique_downloads: List of unique download results
        skills_dir: Target directory for skill installation
        temp_dir: Temporary directory for extraction
        status_dict: Dict to track skill status
        failed_installs: Dict to track failures by skill_name

    Returns:
        List of installation results
    """
    print("\nExtracting and installing skills...")
    install_results = []
    for result in unique_downloads:
        skill_name = result["skill_name"]

        try:
            temp_zip = result["temp_path"]

            # Check if skill already exists
            final_path = skills_dir / skill_name
            if final_path.exists():
                print(f"[SKIP] Skill already installed: {skill_name}")
                status_dict[result["skill_id"]] = "skipped"
                continue

            # Create temporary extraction directory
            extract_temp = temp_dir / f"extract_{skill_name}"
            extract_temp.mkdir(exist_ok=True)

            # Extract zip file safely (with path traversal and zip bomb protection)
            with zipfile.ZipFile(temp_zip, "r") as zip_ref:
                _safe_extract_zip(zip_ref, extract_temp)

            # Give Windows a moment to release file handles
            time.sleep(0.1)

            # Move extracted directory to final location
            shutil.move(str(extract_temp), str(final_path))

            install_results.append(
                {
                    "skill_id": result["skill_id"],
                    "status": "success",
                    "path": str(final_path),
                }
            )
            status_dict[result["skill_id"]] = "installed"
            print(f"[OK] Installed {result['skill_id']} to {final_path}")

        except zipfile.BadZipFile as e:
            error_msg = f"Invalid zip file: {str(e)}"
            install_results.append(
                {"skill_id": result["skill_id"], "status": "failed", "error": error_msg}
            )
            status_dict[result["skill_id"]] = "failed"
            failed_installs[skill_name] = error_msg
            print(
                f"[FAIL] Failed to install {result['skill_id']}: {error_msg}",
                file=sys.stderr,
            )
        except Exception as e:
            error_msg = f"Installation error: {str(e)}"
            install_results.append(
                {"skill_id": result["skill_id"], "status": "failed", "error": error_msg}
            )
            status_dict[result["skill_id"]] = "failed"
            failed_installs[skill_name] = error_msg
            print(
                f"[FAIL] Failed to install {result['skill_id']}: {error_msg}",
                file=sys.stderr,
            )

    return install_results


def _install_skills(skill_ids):
    """
    Utility function to download and install skills from a list of skill IDs.

    Args:
        skill_ids: List of skill IDs to install

    Returns:
        Tuple of (success_count, failed_count, skipped_count, status_dict)
        status_dict maps skill_id to status: "installed", "failed", or "skipped"
    """
    # Create skills directory if it doesn't exist
    skills_dir = Path(".claude/skills")
    skills_dir.mkdir(parents=True, exist_ok=True)

    # Create temporary directory for downloads
    temp_dir = Path(tempfile.mkdtemp(prefix="skill_install_"))

    status_dict = {}
    failed_installs = {}  # Track failures by skill_name for batch write

    # Download skills concurrently
    download_results = _download_skills_concurrently(
        skill_ids, temp_dir, status_dict, failed_installs
    )

    # Deduplicate by skill_name
    unique_downloads = _deduplicate_downloads(download_results, status_dict)

    # Extract and install unique zip files
    install_results = _extract_and_install_skills(
        unique_downloads, skills_dir, temp_dir, status_dict, failed_installs
    )

    # Cleanup temporary directory
    try:
        # Give Windows extra time to release all file handles
        time.sleep(0.2)
        shutil.rmtree(temp_dir)
    except Exception as e:
        print(
            f"Warning: Failed to cleanup temporary directory {temp_dir}: {e}",
            file=sys.stderr,
        )
        print("You may need to manually delete it later.", file=sys.stderr)

    # Calculate summary
    success_count = sum(1 for r in install_results if r["status"] == "success")
    failed_count = len(install_results) - success_count
    skipped_count = sum(1 for s in status_dict.values() if s == "skipped")

    # Track all failed installations in a single batch write
    _track_failed_installs_batch(failed_installs)

    return success_count, failed_count, skipped_count, status_dict


def recall_handler(args):
    url = f"{API_BASE_URL}/recall"
    if not args.query.strip():
        print("Error: Query cannot be empty", file=sys.stderr)
        sys.exit(1)

    # Build exclusion list from both failed and installed skills (unless disabled)
    exclude_skills = []

    if not args.no_filter:
        # Read failed installations cache
        failed_cache = _read_failed_cache()
        if failed_cache:
            exclude_skills.extend(failed_cache.keys())

        # Read installed skills from .claude/skills directory
        skills_dir = Path(".claude/skills")
        if skills_dir.exists() and skills_dir.is_dir():
            installed_skills = [
                item.name for item in skills_dir.iterdir() if item.is_dir()
            ]
            exclude_skills.extend(installed_skills)

    # Remove duplicates
    exclude_skills = list(set(exclude_skills)) if exclude_skills else None

    request_data = {
        "query": args.query,
        "topk": args.topk,
        "sort_topk": args.sort_topk,
        "constraints": args.constraints,
        "fields": args.fields,
    }

    # Add exclude parameter if we have skills to exclude
    if exclude_skills:
        request_data["exclude"] = exclude_skills

    try:
        response = http_post_json(url, request_data)
        results = json.loads(response["content"].decode("utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse API response as JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except (HTTPError, URLError) as e:
        print(f"Error: API request failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Format output for better readability
    if "results" in results and isinstance(results["results"], list):
        skills = results["results"]
        print(f"\nRecalled Skills ({len(skills)} candidates):\n")

        for idx, skill in enumerate(skills, 1):
            skill_id = skill.get("skill_id", "unknown")
            skill_name = skill.get("skill_name", "Unknown")
            description = skill.get("description", "No description available")

            # Format with number, name, and ID
            print(f"{idx}. {skill_name} ({skill_id})")

            # Wrap description to ~80 characters for readability
            desc_lines = []
            words = description.split()
            current_line = "   "
            for word in words:
                if len(current_line) + len(word) + 1 <= 83:
                    current_line += word + " "
                else:
                    desc_lines.append(current_line.rstrip())
                    current_line = "   " + word + " "
            if current_line.strip():
                desc_lines.append(current_line.rstrip())

            print("\n".join(desc_lines))
            print()  # Blank line between entries
    else:
        # Fallback to JSON if structure is unexpected
        print(json.dumps(results, indent=2))


def _parse_and_validate_skills(skill_strings):
    """
    Parse and validate skill JSON strings with score normalization.

    Args:
        skill_strings: List of skill JSON strings

    Returns:
        List of parsed skill dicts with normalized scores

    Raises:
        SystemExit: If no valid skills provided
    """
    skills = []
    for skill_str in skill_strings:
        try:
            skill = json.loads(skill_str)

            # Validate and normalize score
            if "score" in skill:
                score = skill["score"]
                # Convert to int and clamp to 0-100 range
                score = int(round(float(score)))
                score = max(0, min(100, score))
                skill["score"] = score

            skills.append(skill)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            print(f"Warning: Failed to parse skill JSON: {skill_str}", file=sys.stderr)
            print(f"  Error: {e}", file=sys.stderr)
            continue

    if not skills:
        print("Error: No valid skills provided", file=sys.stderr)
        sys.exit(1)

    return skills


def _deduplicate_skills_for_install(skills_list):
    """
    Deduplicate recommended skills based on skill_name, keeping highest scored.

    Args:
        skills_list: List of skill dicts from recommend API

    Returns:
        List of skill_ids to install
    """
    skill_map = {}
    for skill in skills_list:
        if not isinstance(skill, dict):
            continue
        skill_name = skill.get("skill_name")
        skill_id = skill.get("skill_id")
        recommend_score = skill.get("recommend_score", 0)
        if not skill_name or not skill_id:
            continue
        if (
            skill_name not in skill_map
            or recommend_score > skill_map[skill_name]["recommend_score"]
        ):
            skill_map[skill_name] = {
                "skill_id": skill_id,
                "skill_name": skill_name,
                "recommend_score": recommend_score,
            }

    return [skill["skill_id"] for skill in skill_map.values()]


def _safe_float(value, default=0.0):
    """
    Safely convert a value to float, handling None, NaN, and invalid values.

    Args:
        value: Value to convert
        default: Default value if conversion fails or value is NaN/None

    Returns:
        Float value or default
    """
    if value is None:
        return default
    try:
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except (ValueError, TypeError):
        return default


def _safe_string(value, default=""):
    """
    Safely get a string value, handling None, NaN, and invalid values.

    Args:
        value: Value to convert
        default: Default value if conversion fails or value is invalid

    Returns:
        String value or default
    """
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    if isinstance(value, str):
        return value
    # Convert other types to string
    try:
        return str(value)
    except (ValueError, TypeError):
        return default


def _safe_list(value, default=None):
    """
    Safely get a list value, handling None, NaN, and invalid values.

    Args:
        value: Value to convert
        default: Default value if conversion fails or value is invalid

    Returns:
        List value or default
    """
    if default is None:
        default = []
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return value
    return default


def _safe_dict(value, default=None):
    """
    Safely get a dict value, handling None, NaN, and invalid values.

    Args:
        value: Value to convert
        default: Default value if conversion fails or value is invalid

    Returns:
        Dict value or default
    """
    if default is None:
        default = {}
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    if isinstance(value, dict):
        return value
    return default


def _print_recommended_skills(skills_list, install_status):
    """
    Format and print recommended skills with install status.

    Args:
        skills_list: List of skill dicts from recommend API
        install_status: Dict mapping skill_id to install status
    """
    print(f"Recommended Skills ({len(skills_list)}):\n")

    for idx, skill in enumerate(skills_list, 1):
        skill_name = _safe_string(skill.get("skill_name"), "Unknown")
        skill_id = _safe_string(skill.get("skill_id"), "unknown")
        score = _safe_float(skill.get("recommend_score"), 0.0)
        breakdown = _safe_dict(skill.get("breakdown"))
        strengths = _safe_list(skill.get("eval_strengths"))
        weaknesses = _safe_list(skill.get("eval_weaknesses"))

        # Header with install status
        status = install_status.get(skill_id)
        status_icon = {"installed": "✓", "failed": "✗", "skipped": "⊘"}.get(status, "")
        status_text = f" [{status_icon} {status}]" if status else ""
        print(f"{idx}. {skill_name} (Score: {score:.3f}){status_text}")
        print(f"   ID: {skill_id}")

        # Breakdown
        if breakdown:
            q = _safe_float(breakdown.get("quality_score"), 0.0)
            r = _safe_float(breakdown.get("relevance_score"), 0.0)
            print(f"   Quality: {q:.3f} | Relevance: {r:.3f}")

        # Strengths/Weaknesses
        if strengths:
            print("   Strengths:")
            for strength in strengths:
                print(f"     + {strength}")
        if weaknesses:
            print("   Weaknesses:")
            for weakness in weaknesses:
                print(f"     - {weakness}")
        print()


def recommend_handler(args):
    url = f"{API_BASE_URL}/recommend"

    # Parse and validate skill inputs
    skills = _parse_and_validate_skills(args.skills)

    # Call recommend API
    try:
        response = http_post_json(url, {"skills": skills})
        results = json.loads(response["content"].decode("utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse API response as JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except (HTTPError, URLError) as e:
        print(f"Error: API request failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Handle installation if requested
    install_status = {}
    if args.install:
        skills_list = results.get("results", [])
        if not isinstance(skills_list, list):
            print("Error: Expected results to be a list", file=sys.stderr)
            sys.exit(1)

        # Deduplicate and get skill IDs to install
        skills_to_install = _deduplicate_skills_for_install(skills_list)
        if skills_to_install:
            print("\n")
            _, _, _, install_status = _install_skills(skills_to_install)
            print()

    # Format and print output
    if "results" in results and isinstance(results["results"], list):
        skills_list = results["results"]
        _print_recommended_skills(skills_list, install_status)
    else:
        print(json.dumps(results, indent=2))

    # Summary
    if install_status:
        installed = sum(1 for s in install_status.values() if s == "installed")
        failed = sum(1 for s in install_status.values() if s == "failed")
        skipped = sum(1 for s in install_status.values() if s == "skipped")
        print(f"Summary: {installed} installed, {failed} failed, {skipped} skipped\n")
        if failed > 0:
            sys.exit(1)


def install_handler(args):
    """Handler for the install command"""
    success_count, failed_count, skipped_count, _ = _install_skills(args.skills)
    print(
        f"\nSummary: {success_count} installed, {failed_count} failed, {skipped_count} skipped\n"
    )
    if failed_count > 0:
        sys.exit(1)


def main():
    try:
        _main_impl()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: An unexpected error occurred: {e}", file=sys.stderr)
        if DEBUG_MODE:
            print("\n--- Debug Stack Trace ---", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            print("--- End Stack Trace ---\n", file=sys.stderr)
        else:
            print(
                "Hint: Set SKILL_FINDER_DEBUG=1 for detailed error information.",
                file=sys.stderr,
            )
        sys.exit(1)


def _main_impl():
    """Main implementation - separated for clean exception handling."""
    parser = argparse.ArgumentParser(
        description="Skill Finder - Discover and recommend skills based on user needs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Analyze command
    recall_parser = subparsers.add_parser(
        "recall", help="Recall skills based on user requirements"
    )
    recall_parser.add_argument(
        "--query", required=True, help="Search query for skill recall"
    )
    recall_parser.add_argument(
        "--topk", type=int, default=20, help="Number of skills to recall (default: 20)"
    )
    recall_parser.add_argument(
        "--sort-topk", type=int, help="Number of top results to sort using LLM"
    )
    recall_parser.add_argument(
        "--constraints",
        type=str,
        help="Additional constraints for filtering (JSON string)",
    )
    recall_parser.add_argument(
        "--fields",
        type=str,
        nargs="*",
        default=["skill_id", "skill_name", "description"],
        help="Fields to include in response (default: skill_id skill_name description)",
    )
    recall_parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Disable filtering of already installed or failed skills",
    )

    recommend_parser = subparsers.add_parser(
        "recommend", help="Recommend skills based on user requirements"
    )
    recommend_parser.add_argument(
        "--skills",
        type=str,
        nargs="+",
        required=True,
        help="List of skills with their relevance scores (JSON string)",
    )
    recommend_parser.add_argument(
        "--install-all",
        action="store_true",
        dest="install",
        help="Install all recommended skills",
    )
    recommend_parser.add_argument(
        "--no-install",
        action="store_false",
        dest="install",
        help="Do not install recommended skills (default)",
    )
    recommend_parser.set_defaults(install=False)

    install_parser = subparsers.add_parser(
        "install", help="Install skills based on user requirements"
    )
    install_parser.add_argument(
        "--skills",
        type=str,
        nargs="+",
        required=True,
        help="List of skills to install (JSON string)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    handlers = {
        "recall": recall_handler,
        "recommend": recommend_handler,
        "install": install_handler,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)
    handler(args)


if __name__ == "__main__":
    main()
