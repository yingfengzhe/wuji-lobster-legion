#!/usr/bin/env python3
"""
ComicMaster — Export Module

Export composed comic pages as PDF, CBZ, or individual PNGs.
"""

import os
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from PIL import Image


def export_pdf(
    page_images: list[Image.Image],
    output_path: str,
    title: str = "Comic",
    dpi: int = 300,
) -> str:
    """Export pages as a single PDF file.

    Uses Pillow's built-in PDF writer. All pages are converted to RGB.

    Args:
        page_images: List of PIL Images (one per page).
        output_path: Destination file path (should end in .pdf).
        title: PDF title metadata.
        dpi: Resolution metadata embedded in the PDF.

    Returns:
        The output_path string.

    Raises:
        ValueError: If page_images is empty.
    """
    if not page_images:
        raise ValueError("No page images provided for PDF export.")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Ensure all images are RGB (Pillow PDF doesn't support RGBA)
    rgb_pages = [_ensure_rgb(img) for img in page_images]

    first = rgb_pages[0]
    rest = rgb_pages[1:]

    save_kwargs: dict = {
        "format": "PDF",
        "resolution": dpi,
        "title": title,
    }
    if rest:
        save_kwargs["save_all"] = True
        save_kwargs["append_images"] = rest

    first.save(str(out), **save_kwargs)
    return str(out)


def export_cbz(
    page_image_paths: list[str],
    output_path: str,
    title: str = "Comic",
    metadata: dict | None = None,
    story_plan: dict | None = None,
) -> str:
    """Export as CBZ (Comic Book ZIP).

    Creates a .cbz file containing numbered page images and a
    ComicInfo.xml metadata file (ComicRack standard).

    When *story_plan* is provided, a richer ComicInfo.xml is generated
    with title, summary, manga flag, etc.  Otherwise falls back to
    the simpler builder using *title* and *metadata*.

    Args:
        page_image_paths: List of paths to page image files.
        output_path: Destination file path (should end in .cbz).
        title: Comic title for ComicInfo.xml (fallback if no story_plan).
        metadata: Optional dict of extra ComicInfo fields, e.g.
            {"Series": "My Comic", "Writer": "Author", "Year": "2025"}.
        story_plan: Full story plan dict (as produced by story_planner).
            When given, ComicInfo.xml is built from it automatically.

    Returns:
        The output_path string.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    page_count = len(page_image_paths)

    with zipfile.ZipFile(str(out), "w", zipfile.ZIP_STORED) as zf:
        for i, img_path in enumerate(page_image_paths):
            p = Path(img_path)
            arcname = f"{i + 1:04d}{p.suffix}"
            zf.write(img_path, arcname)

        # Build ComicInfo.xml — prefer rich version from story_plan
        if story_plan:
            comic_info = _build_comic_info_from_plan(story_plan, page_count)
        else:
            comic_info = _build_comic_info(title, page_count, metadata)

        zf.writestr("ComicInfo.xml", comic_info)

    return str(out)


def export_pages_png(
    page_images: list[Image.Image],
    output_dir: str,
    prefix: str = "page",
) -> list[str]:
    """Save page images as individual PNG files.

    Args:
        page_images: List of PIL Images.
        output_dir: Directory to save PNGs into.
        prefix: Filename prefix (pages are named {prefix}_001.png, etc.).

    Returns:
        List of saved file paths.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: list[str] = []
    for i, img in enumerate(page_images):
        fname = f"{prefix}_{i + 1:03d}.png"
        fpath = out_dir / fname
        img.save(str(fpath), "PNG")
        paths.append(str(fpath))

    return paths


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_rgb(img: Image.Image) -> Image.Image:
    """Convert an image to RGB if it isn't already."""
    if img.mode == "RGB":
        return img
    return img.convert("RGB")


def _build_comic_info_from_plan(story_plan: dict, page_count: int) -> str:
    """Build a rich ComicInfo.xml from a story plan dict.

    Follows the ComicRack / Anansi ComicInfo standard. Extracts title,
    summary (from panel narrations/dialogues), manga flag from
    reading_direction, and character names.

    Args:
        story_plan: Story plan dictionary with keys like title, style,
            reading_direction, characters, panels, etc.
        page_count: Number of pages in the archive.

    Returns:
        XML string with declaration.
    """
    import html as html_mod

    title = html_mod.escape(story_plan.get("title", "Untitled"))
    style = story_plan.get("style", "western")
    reading_dir = story_plan.get("reading_direction", "ltr")

    # Manga flag: "Yes" if rtl reading direction, else "No"
    manga_flag = "Yes" if reading_dir == "rtl" else "No"

    # Build summary from panel narrations and first dialogue lines
    summary_parts = []
    for panel in story_plan.get("panels", []):
        if panel.get("narration"):
            summary_parts.append(panel["narration"])
        for dlg in panel.get("dialogue", []):
            summary_parts.append(f'{dlg.get("character", "?")}: "{dlg.get("text", "")}"')
    summary = html_mod.escape(" | ".join(summary_parts[:6]))  # first few for brevity

    # Characters → Writer / Penciller stand-in
    char_names = ", ".join(
        c.get("name", "Unknown") for c in story_plan.get("characters", [])
    )

    xml = f'''<?xml version="1.0" encoding="utf-8"?>
<ComicInfo xmlns:xsd="http://www.w3.org/2001/XMLSchema"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Title>{title}</Title>
  <Summary>{summary}</Summary>
  <PageCount>{page_count}</PageCount>
  <Manga>{manga_flag}</Manga>
  <LanguageISO>en</LanguageISO>
  <Genre>AI-Generated Comic</Genre>
  <Writer>ComicMaster AI</Writer>
  <Characters>{html_mod.escape(char_names)}</Characters>
  <Notes>Generated by ComicMaster (OpenClaw Skill). Style: {html_mod.escape(style)}.</Notes>
</ComicInfo>'''
    return xml


def _build_comic_info(
    title: str, page_count: int, metadata: dict | None = None
) -> str:
    """Build a ComicInfo.xml string for CBZ archives.

    See: https://anansi-project.github.io/docs/comicinfo/documentation

    Args:
        title: Comic title.
        page_count: Number of pages.
        metadata: Optional extra fields.

    Returns:
        XML string.
    """
    root = ET.Element("ComicInfo")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xmlns:xsd", "http://www.w3.org/2001/XMLSchema")

    ET.SubElement(root, "Title").text = title
    ET.SubElement(root, "PageCount").text = str(page_count)

    if metadata:
        for key, value in metadata.items():
            ET.SubElement(root, key).text = str(value)

    # Pretty-print
    ET.indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from PIL import ImageDraw, ImageFont

    print("=== export.py standalone test ===")

    output_dir = Path("/home/mcmuff/clawd/output/comicmaster")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create a simple test page image
    def _make_test_page(label: str, color: str = "#2c3e50") -> Image.Image:
        img = Image.new("RGB", (2480, 3508), "white")
        d = ImageDraw.Draw(img)
        d.rectangle([60, 60, 2420, 3448], outline=color, width=4)
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72
            )
        except (OSError, IOError):
            font = ImageFont.load_default()
        bbox = d.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(
            ((2480 - tw) // 2, (3508 - th) // 2),
            label,
            fill=color,
            font=font,
        )
        return img

    page1 = _make_test_page("Page 1")
    page2 = _make_test_page("Page 2", "#e74c3c")

    # --- PDF ---
    pdf_path = export_pdf(
        [page1, page2],
        str(output_dir / "test_export.pdf"),
        title="Test Comic",
    )
    print(f"PDF exported: {pdf_path}  ({os.path.getsize(pdf_path)} bytes)")

    # --- PNGs (needed for CBZ) ---
    png_paths = export_pages_png(
        [page1, page2],
        str(output_dir / "test_pages"),
        prefix="test",
    )
    print(f"PNGs exported: {png_paths}")

    # --- CBZ ---
    cbz_path = export_cbz(
        png_paths,
        str(output_dir / "test_export.cbz"),
        title="Test Comic",
        metadata={"Series": "ComicMaster Test", "Writer": "Bot", "Year": "2026"},
    )
    print(f"CBZ exported: {cbz_path}  ({os.path.getsize(cbz_path)} bytes)")

    # Verify CBZ contents
    with zipfile.ZipFile(cbz_path, "r") as zf:
        print(f"CBZ contents: {zf.namelist()}")

    print("✅ All export tests passed.")
