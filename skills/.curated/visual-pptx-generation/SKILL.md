---
name: visual-pptx-generation
category: presentation
summary: Generate theme-aware high-visual HTML decks and image-based PPTX artifacts.
---

# Visual PPTX Generation Skill

Use this skill when the user asks for a polished, MiniMax-like, magazine-style, demo/pitch-style, strongly visual, or non-white-background presentation. This route prioritizes visual quality over native text editability.

## Route selection

- Use `editable_pptx` when the user needs an editable office document, formal academic slides, or text/table-heavy deliverables.
- Use `visual_pptx` when the user explicitly wants strong visual impact, MiniMax-like effects, rich layout, product/demo/pitch style, or says the current PPT looks too plain.
- Tell the user that `visual_pptx` is usually image-based after screenshot export, so the final PPTX is visually faithful but not fully text-editable.

## Theme policy

Do **not** force every visual deck into one dark-tech palette. `dark_tech` is only a reference style. Prefer `visual_theme="auto"` unless the user gives a specific style. The renderer can use named themes or custom palettes:

- `cyber_blue`: technical / AI / software / infrastructure decks.
- `dark_tech`: dark MiniMax-like tech deck.
- `corporate_blue`: business, product, strategy, pitch decks.
- `academic_light`: research, paper, lecture, thesis-style decks.
- `warm_editorial`: magazine/editorial/brand storytelling decks.
- `emerald_dark`: science, bio, drug discovery, sustainability decks.
- `violet_neon`: creative, futuristic, design-heavy decks.
- `midnight_gold`: premium/keynote/launch decks.
- `light_magazine`: clean general-purpose visual deck.

If the user provides colors, pass a custom palette, for example:

```json
{"base":"corporate_blue", "palette":{"primary":"#7c3aed", "background":"#faf5ff", "surface":"#ffffff"}}
```

## Workflow

1. Gather evidence with `kb_search`, `web_search`, `url_fetch`, or `arxiv_search` if the deck needs factual content.
2. Create a concise `deck_schema`. Include `title`, `subtitle`, `language`, `audience`, optional `visual_theme` or custom palette, and `slides`.
3. Plan the visual rhythm before rendering: `cover -> toc -> section_divider -> metric_cards -> cards/content -> comparison/table -> summary/references`.
4. Call `html_deck_validate_schema` and then `html_deck_create_from_schema`.
5. Call `html_deck_preview` to return preview path/URL, then call `html_deck_qa`.
6. Render screenshots + export PPTX with `html_deck_render_screenshots` and `pptx_create_from_html_screenshots`, or use `html_deck_generate_visual_pptx` for one-shot flow.
7. If screenshot export is unavailable, return the HTML deck and explain that Playwright/browser runtime is needed for image-based PPTX export.
8. If an image-based PPTX is created, return the PPTX artifact URL/path and mention that it is image-based.

## Schema tips

- Use `metrics` for big-number pages, e.g. `{label, value, desc}`.
- Use `cards` or `bullets` for visual cards pages, with 3-4 concise points.
- Use `columns`, `left/right`, or `headers/rows` for comparison/table pages.
- Add `evidence_refs` to preserve source traceability.
- Keep each slide visually sparse: short title, few bullets, one dominant visual pattern.
- Avoid repeating exactly the same layout and color mood for too many consecutive slides.

## Do not

- Do not use this route for users who require fully editable text and shapes.
- Do not output only a slide outline.
- Do not depend on text-to-image models as a required step.
- Do not invent missing citations or sources.
- Do not hard-code the same palette for every deck when the user asks for flexible style.
