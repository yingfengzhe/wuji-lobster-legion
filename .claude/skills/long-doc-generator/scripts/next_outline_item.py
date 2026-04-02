#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path

PENDING_RE = re.compile(r"^(?P<indent>\s*)- \[ \] (?P<title>.+)$")
IN_PROGRESS_RE = re.compile(r"^(?P<indent>\s*)- \[>\] (?P<title>.+)$")


def read_lines(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Temp file not found: {path}", file=sys.stderr)
        sys.exit(1)
    has_trailing_newline = text.endswith("\n")
    lines = text.splitlines()
    if lines and lines[0].startswith("\ufeff"):
        lines[0] = lines[0].lstrip("\ufeff")
    return lines, has_trailing_newline


def write_lines(path: Path, lines, has_trailing_newline: bool):
    text = "\n".join(lines)
    if has_trailing_newline:
        text += "\n"
    path.write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Return next outline entry and update status markers."
    )
    parser.add_argument("--tmp", required=True, help="Path to the outline temp file.")
    args = parser.parse_args()

    path = Path(args.tmp)
    lines, has_trailing_newline = read_lines(path)

    # If a section is already in progress, return it as-is.
    for line in lines:
        match = IN_PROGRESS_RE.match(line)
        if match:
            indent = match.group("indent")
            title = match.group("title").rstrip()
            print(f"{indent}{title}")
            return

    changed = False
    next_entry = None
    for idx, line in enumerate(lines):
        match = PENDING_RE.match(line)
        if match:
            indent = match.group("indent")
            title = match.group("title").rstrip()
            lines[idx] = f"{indent}- [>] {title}"
            next_entry = f"{indent}{title}"
            changed = True
            break

    if changed:
        write_lines(path, lines, has_trailing_newline)

    print(next_entry if next_entry else "over")


if __name__ == "__main__":
    main()
