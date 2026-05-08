---
name: pptx-generation
license: MIT-compatible original LazyRAG workflow
license_url: ''
description: Generate editable PPTX artifacts from user requirements and evidence using schema normalization, deterministic QA, one-round auto-repair, artifact saving, and optional thumbnail preview.
---

# PPTX Generation

Use this skill when the user asks for PPT/PPTX/slides/deck output.

## Workflow
1. Understand the presentation goal (audience, language, style, expected slide count).
2. If external grounding is needed, collect evidence via `kb_search`, `web_search`, `url_fetch`, or `arxiv_search`.
3. Build a structured `deck_schema` instead of writing Python/JS code. Include: `title`, `subtitle`, `language`, `audience`, `theme`, `slides`.
4. Run `pptx_validate_schema(deck_schema)` to normalize and catch schema issues early.
5. Generate editable PPTX using `pptx_create_from_schema` (or `pptx_generate_with_qa_loop` for one-step generation + QA + repair).
6. Run `pptx_parse` and `pptx_qa` to check slide count, empty slides, placeholders, text density, overflow risk, and table density.
7. If QA shows fixable issues, call `pptx_repair_schema`, regenerate once, and rerun parse + QA.
8. Save the final result using `artifact_save`, then return `file_path` and `download_url`.
9. If the user asks for preview, call `pptx_render_thumbnails`; if thumbnail generation is unavailable, still return the PPTX artifact.

## Deck Rules
- Keep body slides editable (text/table shapes), avoid image-only pages.
- Prefer 3-6 bullets per content page.
- Keep bullets concise for projector readability.
- Use `table` slides for structured comparisons; avoid overcrowded cells.
- Preserve `evidence_refs` and include a references page when sources are present.

## Theme Rules
- Supported themes: `academic`, `business`, `minimal`.
- Use `academic` for research/technical reports, `business` for executive/product summaries, `minimal` for neutral default.
- In Chinese scenarios, keep titles short and avoid dense paragraphs.

## Boundaries
- Do not require Node/PptxGenJS for this workflow.
- Do not depend on text-to-image generation for normal slide content.
- Do not output only an outline when the user asked for a PPTX file.
