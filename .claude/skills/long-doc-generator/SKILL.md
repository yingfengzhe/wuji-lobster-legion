---
name: long-doc-generator
description: "Generate long-form Markdown documents from a summary and writing requirements, using template-guided outlines + temp file iteration and helper scripts. Use for 长文档/长文章/多章节/目录/大纲 generation, reports, or long-form bid technical proposals."
---

# Long Doc Generator

## Overview

Generate a long-form Markdown document by selecting a document-type template, creating a filename, building an outline checklist, persisting it to a temp file, then iteratively drafting sections until the helper script returns `over`. Use a separate append script to add each section to the document.

## Required Inputs

- Document summary (2-6 sentences)
- Writing requirements (audience, tone, length, style, must-include points)
- If the user provides a requirement list, treat it as the primary input to analyze and expand into functional points and implementation.
- If the document type is not explicit, infer it from the summary/requirements and confirm if ambiguous.

If either input is missing, ask for it before starting.

## Workflow

1. Determine the document type and load the matching template from `references/`.
   - Supported types: technical document, work report.
   - If unclear, ask the user to choose.
2. Create the target Markdown file in the current directory and store the path for reuse.
   - Derive a concise filename from the summary and requirements.
   - Use `.md`; avoid special characters; do not overwrite existing files (add a suffix if needed).
3. Generate a document outline from the summary and requirements by referencing the template outline.
   - Replace placeholders like `xxxx功能` with concrete module names.
   - Keep the template's major sections unless the user explicitly removes them.
4. Save the outline to a temp file named `tmp-YYYY-MM-DD-HH-MM-SS.txt` in the current directory.
5. Call the script to get the next outline entry:
   - `python scripts/next_outline_item.py --tmp <temp-file>`
   - If the script prints `over`, stop.
   - Otherwise, draft the section corresponding to the returned entry.
6. Append the drafted section to the Markdown file via the append script (this marks the entry as done in the temp file):
   - `python scripts/append_section.py <doc-path> "<outline-entry>" "<section-body>" --tmp <temp-file>`
   - If the body is large, pass a file path as the third argument instead of inline text.
7. Call the outline script again to retrieve the next entry.
8. Repeat steps 5-7 until the script returns `over`.
9. Delete the temporary outline file once the script returns `over` and the document is complete.

## Iteration Guardrails

- One loop iteration equals one outline entry. Do not generate all sections at once.
- Do not precompute multiple sections before calling `next_outline_item.py` again.
- `next_outline_item.py` will re-return an in-progress entry until `append_section.py --tmp` marks it done.
- Always use `append_section.py` to write content; do not manually append.

## Outline Temp File Format

Write each outline item as a checkbox line. Indentation indicates nesting (2 spaces per level).

```markdown
- [ ] 1. Introduction
  - [ ] 1.1 Background
  - [ ] 1.2 Objectives
- [ ] 2. Method
```

The script updates status markers:
- `- [ ]` pending
- `- [>]` in-progress (last returned by the script)
- `- [x]` done

## Drafting Rules

- Map indentation or numbering depth to Markdown headings (`#`, `##`, `###`, ...).
- Keep each section aligned with the summary, writing requirements, and the selected template.
- Maintain consistent tone and section order; do not reorder outline entries.
- For each module/section, follow the analysis flow: 需求理解 -> 功能点拆解 -> 实现方式与技术方案.
- Apply the "正文生成要求" from the selected template for every section.
- Do not include the section heading in the body; the append script adds it.

## Templates

Templates are stored under `references/` with two parts: "目录参考" and "正文生成要求".

- `references/template-technical-doc.md`
- `references/template-work-report.md`

## Prompt Templates (LLM-driven)

Templates are guidance, not the source of truth. Generate the outline and each section body with the model, referencing the selected template.

- Outline prompt:
  - `references/prompt-outline-technical-doc.md`
  - `references/prompt-outline-work-report.md`
- Section prompt:
  - `references/prompt-section-technical-doc.md`
  - `references/prompt-section-work-report.md`

## Scripts

### scripts/next_outline_item.py

Return the next outline entry from the temp file and update status markers.

Behavior:
- If a `- [>]` entry exists, return it as-is (do not advance).
- Otherwise, promote the first `- [ ]` entry to `- [>]` and print that entry (without the checkbox); preserve indentation so nesting can be inferred.
- Print `over` if no pending entries remain.

### scripts/append_section.py

Append a section to the target Markdown file.

Usage:
- `python scripts/append_section.py <doc-path> "<outline-entry>" "<section-body>" --tmp <temp-file>`
- If the third argument is a file path, read the body from that file.
- To observe incremental growth: add `--sleep-ms 1000`.

Behavior:
- Convert the outline entry to a heading based on indentation depth.
- Append the heading and body to the document, preserving order.
- If `--tmp` is provided, mark the in-progress outline entry as done and refuse to advance on mismatch.
