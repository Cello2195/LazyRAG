# LazyRAG Visual PPTX v3

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

Generate theme-aware 960x540 HTML slides with layouts similar to MiniMax process files: cover hero, numbered TOC, section divider, metric cards, content/cards, two-column cards, table/matrix, summary, references.

The visual route is not limited to one `dark_tech` palette. It supports named themes including `auto`, `cyber_blue`, `dark_tech`, `corporate_blue`, `academic_light`, `warm_editorial`, `emerald_dark`, `violet_neon`, `midnight_gold`, and `light_magazine`, plus custom palette dictionaries. Use `auto` as the default and infer a theme from audience/topic/style.

If Playwright is unavailable, HTML generation and QA still work, while screenshot/PPTX export returns a graceful warning.
