---
name: pptx-generation
license: MIT-compatible original LazyRAG workflow
license_url: ''
description: Generate editable PPTX artifacts from RAG evidence or user-provided content by planning a deck_schema, rendering it with LazyRAG PPTX tools, and running deterministic QA before returning a download link.
---

# PPTX Generation

Use this skill when the user asks to create a PPT, PPTX, slide deck, presentation, or report-style deck.

## Core workflow
1. Clarify the presentation goal only if essential; otherwise infer audience, language, and style from the user request.
2. Gather content evidence with `kb_search`, `kb_get_window_nodes`, `kb_keyword_search`, `web_search`, `url_fetch`, or `arxiv_search` when the deck should be grounded in documents or public sources.
3. Create a structured `deck_schema` instead of writing Python/JS code. Include `title`, `subtitle`, `theme`, and `slides`. Each slide should have `type`, `title`, concise `bullets`, and `evidence_refs` when using KB evidence.
4. Call `pptx_create_from_schema(deck_schema, filename)` to generate an editable `.pptx` file.
5. Call `pptx_parse(file_path)` and `pptx_qa(file_path, deck_schema)` to check slide count, missing text, empty pages, placeholder residue, excessive text, and basic bounds.
6. If QA reports blocking errors, revise the schema and regenerate once before returning.
7. Call `artifact_save(file_path, kind='pptx')` and return the `download_url`. Use `pptx_render_thumbnails` when the user asks for visual preview or when layout quality is important.

## Deck schema notes
Supported slide types for the first renderer are `cover`, `toc`, `section_divider`, `content_bullets`, `two_column`, `comparison`, `table`, and `summary`. Prefer short conclusion-style titles and 3–6 bullets per content page. Do not put entire paragraphs into bullets. Keep正文页 as editable PPT shapes; do not render full pages as images.

## Boundaries
Do not depend on text-to-image models for normal content pages. Use image generation only as a later optional enhancement for cover art, section backgrounds, or concept illustrations. For existing-template editing or complex OOXML manipulation, treat it as a future workflow rather than this first-generation toolchain.
