#!/usr/bin/env python3
import argparse
import re
import sys
import time
from pathlib import Path


IN_PROGRESS_RE = re.compile(r"^(?P<indent>\s*)- \[>\] (?P<title>.+)$")


def read_body(arg: str) -> str:
    if arg == "-":
        text = sys.stdin.read()
        return text.lstrip("\ufeff")
    path = Path(arg)
    if path.exists() and path.is_file():
        text = path.read_text(encoding="utf-8")
        return text.lstrip("\ufeff")
    return arg


def infer_level(indent: str) -> int:
    if "\t" in indent:
        return indent.count("\t")
    spaces = len(indent)
    if spaces == 0:
        return 0
    if spaces % 4 == 0:
        return spaces // 4
    return spaces // 2


def ensure_parent(path: Path) -> None:
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def needs_newline(path: Path) -> bool:
    if not path.exists():
        return False
    size = path.stat().st_size
    if size == 0:
        return False
    with path.open("rb") as handle:
        handle.seek(-1, 2)
        last = handle.read(1)
    return last != b"\n"


def normalize_title(text: str) -> str:
    return " ".join(text.strip().split())


def mark_outline_done(tmp_path: Path, outline_title: str) -> None:
    try:
        text = tmp_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Temp file not found: {tmp_path}", file=sys.stderr)
        sys.exit(1)

    has_trailing_newline = text.endswith("\n")
    lines = text.splitlines()
    if lines and lines[0].startswith("\ufeff"):
        lines[0] = lines[0].lstrip("\ufeff")

    target = normalize_title(outline_title)
    updated = False

    for idx, line in enumerate(lines):
        match = IN_PROGRESS_RE.match(line)
        if not match:
            continue
        title = match.group("title")
        if normalize_title(title) != target:
            print(
                "Outline mismatch: in-progress entry does not match current section.",
                file=sys.stderr,
            )
            sys.exit(1)
        indent = match.group("indent")
        lines[idx] = f"{indent}- [x] {title}"
        updated = True
        break

    if not updated:
        print("No in-progress outline entry found to mark done.", file=sys.stderr)
        sys.exit(1)

    output = "\n".join(lines)
    if has_trailing_newline:
        output += "\n"
    tmp_path.write_text(output, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Append a heading and body section to a Markdown document."
    )
    parser.add_argument("doc_path", help="Target Markdown document path.")
    parser.add_argument("outline_entry", help="Outline entry text (may include indentation).")
    parser.add_argument(
        "body",
        help="Body text or a file path. Use '-' to read from stdin.",
    )
    parser.add_argument(
        "--tmp",
        help="Optional outline temp file path. Marks the in-progress entry as done.",
    )
    parser.add_argument(
        "--sleep-ms",
        type=int,
        default=0,
        help="Sleep N milliseconds after appending (for observing incremental file growth).",
    )
    args = parser.parse_args()

    doc_path = Path(args.doc_path)
    ensure_parent(doc_path)

    entry = args.outline_entry.rstrip()
    indent_len = len(entry) - len(entry.lstrip())
    indent = entry[:indent_len]
    title = entry.lstrip()
    level = min(6, 1 + infer_level(indent))
    heading = f"{'#' * level} {title}"

    body_text = read_body(args.body).rstrip()

    prefix = "\n" if needs_newline(doc_path) else ""
    block = f"{heading}\n\n"
    if body_text:
        block += f"{body_text}\n\n"
    else:
        block += "\n"

    with doc_path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(prefix)
        handle.write(block)

    if args.tmp:
        mark_outline_done(Path(args.tmp), title)

    if args.sleep_ms and args.sleep_ms > 0:
        time.sleep(args.sleep_ms / 1000.0)


if __name__ == "__main__":
    main()
