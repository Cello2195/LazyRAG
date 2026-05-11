---
name: pptx-generation
license: MIT-compatible original LazyRAG workflow
license_url: ''
description: Generate editable PPTX artifacts or route to MiniMax-style visual PPTX when the user asks for stronger presentation design.
---

# PPTX Generation

Use this skill when the user asks for PPT/PPTX/slides/deck output.

## Route selection

LazyRAG now has two routes:

1. `editable_pptx`: schema-driven `python-pptx` output. Use this for formal reports, academic decks, editable deliverables, and text/table-heavy slides.
2. `visual_pptx`: theme-aware fixed-size HTML slides, optional Playwright screenshots, and image-based PPTX export. Use this when the user asks for a polished, MiniMax-like, magazine-like, demo/pitch-style, or non-white-background deck.

Be explicit when using `visual_pptx`: the exported PPTX is usually screenshot/image-based and therefore visually faithful but not fully text-editable.

## Editable PPTX workflow

1. Understand the presentation goal: audience, language, style, expected slide count.
2. If external grounding is needed, collect evidence via `kb_search`, `web_search`, `url_fetch`, or `arxiv_search`.
3. Build a structured `deck_schema` instead of writing Python/JS code. Include `title`, `subtitle`, `language`, `audience`, `theme`, and `slides`.
4. Run `pptx_validate_schema(deck_schema)`.
5. Generate editable PPTX using `pptx_create_from_schema` or `pptx_generate_with_qa_loop`.
6. Run `pptx_parse` and `pptx_qa`.
7. If QA shows fixable issues, call `pptx_repair_schema`, regenerate once, and rerun QA.
8. Save the final result using `artifact_save` and return signed URL fields first: `download_link` (preferred), then `download_url`/`file_url`.
9. Never treat `relative_path` or local `file_path` as a web download URL.
10. Use `pptx_render_thumbnails` for preview if needed; if unavailable, still return the PPTX artifact.

## Visual PPTX workflow

1. Build or reuse the same `deck_schema`, but include `visual_theme` or custom palette when relevant, concise bullets, optional `metrics`, `columns`, `headers/rows`, and `evidence_refs`.
2. Plan slide rhythm: `cover -> toc -> section_divider -> metric_cards -> challenge_cards -> comparison/table -> summary/references`.
3. Do not force a single palette. Use `visual_theme="auto"` by default, or choose a named theme such as `cyber_blue`, `dark_tech`, `corporate_blue`, `academic_light`, `warm_editorial`, `emerald_dark`, `violet_neon`, `midnight_gold`, or `light_magazine`. If the user gives colors, pass a custom palette dict.
4. Call `html_deck_validate_schema` -> `html_deck_create_from_schema` -> `html_deck_preview` -> `html_deck_qa`.
5. Then call `html_deck_render_screenshots` + `pptx_create_from_html_screenshots`, or use `html_deck_generate_visual_pptx` for one-shot generation.
6. If Playwright is unavailable, return the generated HTML deck and explain that screenshot/PPTX export requires Playwright browser runtime.

## Deck Rules

- For editable PPTX, keep body slides editable and avoid image-only pages.
- For visual PPTX, prioritize visual rhythm, varied theme/layout selection, big titles, metric cards, and sparse content. Do not overfill pages.
- Prefer 3-6 bullets per content page.
- Keep bullets concise for projector readability.
- Use `table` slides for structured comparisons, but avoid overcrowded cells.
- Preserve `evidence_refs` and include a references page when sources are present.

## Boundaries

- Do not require Node/PptxGenJS for either first-party LazyRAG route.
- Do not depend on text-to-image generation for normal slide content.
- Do not output only an outline when the user asked for a PPTX file.
