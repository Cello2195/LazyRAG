# LazyRAG Visual PPTX v3 / Guizang-style visual system

This v3 layer adds a MiniMax-style visual presentation route next to the existing editable PPTX route.

## Routes

- `editable_pptx`: `deck_schema -> python-pptx -> editable .pptx`
- `visual_pptx`: `deck_schema -> fixed-size HTML slides -> Playwright screenshots -> image-based .pptx`

The visual route produces stronger presentation design but the exported PPTX is screenshot-based, so text is not fully editable.

## New modules

```text
algorithm/chat/html_deck/
  schema.py
  themes.py
  renderer.py
  screenshot.py
  export_pptx.py
  qa.py
algorithm/chat/tools/html_deck.py
```

## Main tools

- `html_deck_validate_schema`
- `html_deck_create_from_schema`
- `html_deck_preview`
- `html_deck_qa`
- `html_deck_render_screenshots`
- `pptx_create_from_html_screenshots`
- `html_deck_generate_visual_pptx`

## First v3 target

Generate 960x540 HTML slides using one coherent Guizang-style design family rather than many unrelated templates. The visual family emphasizes magazine framing, large page numbers, editorial cards, SVG ornaments, strong section posters, metric posters, and quote/process pages.

Theme names are variants of this family, not independent one-off templates: `guizang_ink`, `guizang_aurora`, `guizang_paper`, `guizang_blueprint`, `guizang_business`, and `guizang_noir`. Legacy names such as `cyber_blue`, `dark_tech`, `corporate_blue`, `academic_light`, `warm_editorial`, `emerald_dark`, `violet_neon`, `midnight_gold`, and `light_magazine` remain supported for compatibility, but they resolve to the Guizang-style visual system. Use `auto` as the default and infer a variant from audience/topic/style.

The key rule is: a theme should change composition tokens, not only colors. It should affect background ornament, title treatment, card style, layout frame, density, and page rhythm.

If Playwright is unavailable, HTML generation and QA still work. Screenshot/PPTX export should not silently accept low-quality Pillow fallback as a real MiniMax-style visual export; Codex should enforce this in the engineering chain.
