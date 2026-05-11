from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from .schema import normalize_deck_schema
from .themes import resolve_theme

_MAX_CONTENT_BULLETS = 6
_MAX_COLUMN_BULLETS = 5
_MAX_TABLE_ROWS = 10
_MAX_TABLE_COLS = 6


def _rgb(value: str) -> RGBColor:
    text = str(value or '000000').strip().lstrip('#')
    if len(text) != 6:
        text = '000000'
    try:
        return RGBColor(int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except Exception:
        return RGBColor(0, 0, 0)


def _to_lines(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [line.strip(' \t-•') for line in value.splitlines()]
    elif isinstance(value, Iterable) and not isinstance(value, (dict, bytes, bytearray)):
        parts = [str(item).strip() for item in value]
    else:
        parts = [str(value).strip()]
    return [part for part in parts if part]


def _truncate(text: str, max_len: int = 150) -> str:
    if len(text) <= max_len:
        return text
    return f'{text[: max_len - 1]}…'


def _new_slide(prs: Presentation):
    return prs.slides.add_slide(prs.slide_layouts[6])


def _set_background(slide: Any, color: str) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(color)


def _set_notes(slide: Any, notes: str, evidence_refs: List[str] | None = None) -> None:
    refs = evidence_refs or []
    notes_parts = []
    if notes:
        notes_parts.append(notes)
    if refs:
        notes_parts.append('Sources: ' + '; '.join(refs))
    full_text = '\n\n'.join(part for part in notes_parts if part)
    if not full_text:
        return
    try:
        notes_slide = slide.notes_slide
        notes_slide.notes_text_frame.text = full_text
    except Exception:
        # Some environments/templates may not expose notes editing; ignore gracefully.
        pass


def _add_textbox(
    slide: Any,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    font_name: str,
    font_size: int,
    color: str,
    bold: bool = False,
    align: PP_ALIGN | None = None,
    vertical_anchor: MSO_ANCHOR = MSO_ANCHOR.TOP,
    margin: float = 0.04,
) -> Any:
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.vertical_anchor = vertical_anchor
    frame.margin_left = Inches(margin)
    frame.margin_right = Inches(margin)
    frame.margin_top = Inches(margin)
    frame.margin_bottom = Inches(margin)
    paragraph = frame.paragraphs[0]
    paragraph.text = text or ''
    if align is not None:
        paragraph.alignment = align
    paragraph.space_after = Pt(5)
    for run in paragraph.runs:
        run.font.name = font_name
        run.font.size = Pt(font_size)
        run.font.bold = bold
        run.font.color.rgb = _rgb(color)
    return box


def _add_bullets(
    slide: Any,
    bullets: List[str],
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    font_name: str,
    font_size: int,
    color: str,
    max_items: int,
    include_overflow_hint: bool = True,
) -> Tuple[Any, List[str]]:
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(0.08)
    frame.margin_right = Inches(0.05)
    frame.margin_top = Inches(0.04)
    frame.margin_bottom = Inches(0.04)

    shown = bullets[:max_items]
    hidden = bullets[max_items:]

    if not shown:
        shown = ['(No content)']

    for idx, item in enumerate(shown):
        paragraph = frame.paragraphs[0] if idx == 0 else frame.add_paragraph()
        paragraph.text = _truncate(str(item), max_len=170)
        paragraph.level = 0
        paragraph.space_after = Pt(8)
        for run in paragraph.runs:
            run.font.name = font_name
            run.font.size = Pt(font_size)
            run.font.color.rgb = _rgb(color)

    if hidden and include_overflow_hint:
        hint = f'更多内容已折叠（+{len(hidden)}）'
        paragraph = frame.add_paragraph()
        paragraph.text = hint
        paragraph.level = 0
        paragraph.space_after = Pt(0)
        for run in paragraph.runs:
            run.font.name = font_name
            run.font.size = Pt(max(font_size - 2, 9))
            run.font.color.rgb = _rgb('94A3B8')

    return box, hidden


def _add_footer(slide: Any, idx: int, total: int, theme: Dict[str, Any], refs: List[str] | None = None) -> None:
    refs_text = ' '.join((refs or [])[:2])
    right = f'{idx}/{total}'
    text = right if not refs_text else f'{refs_text}    {right}'
    _add_textbox(
        slide,
        text,
        theme['margin'],
        theme['slide_height'] - 0.34,
        theme['slide_width'] - theme['margin'] * 2,
        0.2,
        font_name=theme['font_family'],
        font_size=theme['footer_font_size'],
        color=theme['muted_color'],
        align=PP_ALIGN.RIGHT,
        vertical_anchor=MSO_ANCHOR.MIDDLE,
        margin=0.0,
    )


def _add_title_block(slide: Any, title: str, subtitle: str, theme: Dict[str, Any]) -> None:
    _add_textbox(
        slide,
        _truncate(title, max_len=100),
        theme['margin'],
        0.36,
        theme['slide_width'] - theme['margin'] * 2,
        0.75,
        font_name=theme['font_family'],
        font_size=theme['title_font_size'],
        color=theme['title_color'],
        bold=True,
    )
    if subtitle:
        _add_textbox(
            slide,
            _truncate(subtitle, max_len=180),
            theme['margin'],
            1.05,
            theme['slide_width'] - theme['margin'] * 2,
            0.34,
            font_name=theme['font_family'],
            font_size=theme['subtitle_font_size'],
            color=theme['muted_color'],
        )
    accent = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE,
        Inches(theme['margin']),
        Inches(1.36),
        Inches(1.2),
        Inches(0.06),
    )
    accent.fill.solid()
    accent.fill.fore_color.rgb = _rgb(theme['accent_color'])
    accent.line.fill.background()


def _render_cover(prs: Presentation, slide_data: Dict[str, Any], deck: Dict[str, Any], idx: int) -> None:
    theme = deck['theme']
    slide = _new_slide(prs)
    _set_background(slide, theme['background_color'])

    band = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE,
        Inches(0),
        Inches(0),
        Inches(0.26),
        Inches(theme['slide_height']),
    )
    band.fill.solid()
    band.fill.fore_color.rgb = _rgb(theme['accent_color'])
    band.line.fill.background()

    _add_textbox(
        slide,
        _truncate(slide_data.get('title') or deck['title'], max_len=120),
        0.88,
        1.95,
        theme['slide_width'] - 1.6,
        1.25,
        font_name=theme['font_family'],
        font_size=theme['title_font_size'] + 4,
        color=theme['title_color'],
        bold=True,
    )
    subtitle = slide_data.get('subtitle') or deck.get('subtitle') or ''
    if subtitle:
        _add_textbox(
            slide,
            _truncate(subtitle, max_len=220),
            0.92,
            3.18,
            theme['slide_width'] - 1.8,
            0.7,
            font_name=theme['font_family'],
            font_size=theme['subtitle_font_size'],
            color=theme['muted_color'],
        )

    _set_notes(slide, slide_data.get('notes') or '', slide_data.get('evidence_refs') or [])
    _add_footer(slide, idx, len(deck['slides']), theme, slide_data.get('evidence_refs') or [])


def _render_toc(prs: Presentation, slide_data: Dict[str, Any], deck: Dict[str, Any], idx: int) -> None:
    theme = deck['theme']
    slide = _new_slide(prs)
    _set_background(slide, theme['background_color'])
    _add_title_block(slide, slide_data.get('title') or ('目录' if deck['language'] == 'zh' else 'Contents'), slide_data.get('subtitle') or '', theme)

    items = _to_lines(slide_data.get('items') or slide_data.get('bullets') or [])[:12]
    y = 1.72
    for num, item in enumerate(items, start=1):
        _add_textbox(
            slide,
            f'{num:02d}',
            theme['margin'] + 0.03,
            y,
            0.55,
            0.34,
            font_name=theme['font_family'],
            font_size=theme['body_font_size'] - 2,
            color=theme['accent_color'],
            bold=True,
        )
        _add_textbox(
            slide,
            _truncate(item, max_len=95),
            theme['margin'] + 0.72,
            y - 0.02,
            theme['slide_width'] - theme['margin'] * 2 - 0.85,
            0.4,
            font_name=theme['font_family'],
            font_size=theme['body_font_size'],
            color=theme['body_color'],
        )
        y += 0.46

    _set_notes(slide, slide_data.get('notes') or '', slide_data.get('evidence_refs') or [])
    _add_footer(slide, idx, len(deck['slides']), theme, slide_data.get('evidence_refs') or [])


def _render_section(prs: Presentation, slide_data: Dict[str, Any], deck: Dict[str, Any], idx: int) -> None:
    theme = deck['theme']
    slide = _new_slide(prs)
    _set_background(slide, theme['surface_color'])

    _add_textbox(
        slide,
        _truncate(slide_data.get('title') or ('章节' if deck['language'] == 'zh' else f'Section {idx}'), max_len=90),
        theme['margin'] + 0.1,
        2.32,
        theme['slide_width'] - (theme['margin'] + 0.1) * 2,
        0.95,
        font_name=theme['font_family'],
        font_size=theme['title_font_size'] + 2,
        color=theme['title_color'],
        bold=True,
        align=PP_ALIGN.CENTER,
    )
    subtitle = _truncate(slide_data.get('subtitle') or '', max_len=140)
    if subtitle:
        _add_textbox(
            slide,
            subtitle,
            theme['margin'] + 0.2,
            3.28,
            theme['slide_width'] - (theme['margin'] + 0.2) * 2,
            0.46,
            font_name=theme['font_family'],
            font_size=theme['subtitle_font_size'],
            color=theme['muted_color'],
            align=PP_ALIGN.CENTER,
        )

    _set_notes(slide, slide_data.get('notes') or '', slide_data.get('evidence_refs') or [])
    _add_footer(slide, idx, len(deck['slides']), theme, slide_data.get('evidence_refs') or [])


def _render_content_bullets(prs: Presentation, slide_data: Dict[str, Any], deck: Dict[str, Any], idx: int) -> None:
    theme = deck['theme']
    slide = _new_slide(prs)
    _set_background(slide, theme['background_color'])

    _add_title_block(slide, slide_data.get('title') or f'Slide {idx}', slide_data.get('subtitle') or '', theme)

    bullets = [_truncate(item, max_len=180) for item in _to_lines(slide_data.get('bullets') or [])]
    _, hidden = _add_bullets(
        slide,
        bullets,
        theme['margin'] + 0.06,
        theme['top_spacing'] + 0.12,
        theme['slide_width'] - theme['margin'] * 2 - 0.12,
        theme['slide_height'] - theme['top_spacing'] - 1.0,
        font_name=theme['font_family'],
        font_size=theme['body_font_size'],
        color=theme['body_color'],
        max_items=_MAX_CONTENT_BULLETS,
    )

    notes = slide_data.get('notes') or ''
    if hidden:
        overflow_notes = '\n'.join(f'- {line}' for line in hidden)
        notes = f"{notes}\n\nOverflow bullets:\n{overflow_notes}".strip()
    _set_notes(slide, notes, slide_data.get('evidence_refs') or [])
    _add_footer(slide, idx, len(deck['slides']), theme, slide_data.get('evidence_refs') or [])


def _column_card(slide: Any, x: float, y: float, w: float, h: float, theme: Dict[str, Any]) -> None:
    card = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    card.fill.solid()
    card.fill.fore_color.rgb = _rgb(theme['surface_color'])
    card.line.color.rgb = _rgb(theme['line_color'])


def _render_two_column(prs: Presentation, slide_data: Dict[str, Any], deck: Dict[str, Any], idx: int) -> None:
    theme = deck['theme']
    slide = _new_slide(prs)
    _set_background(slide, theme['background_color'])
    _add_title_block(slide, slide_data.get('title') or f'Slide {idx}', slide_data.get('subtitle') or '', theme)

    left = slide_data.get('left') if isinstance(slide_data.get('left'), dict) else {}
    right = slide_data.get('right') if isinstance(slide_data.get('right'), dict) else {}

    y = theme['top_spacing'] + 0.08
    h = theme['slide_height'] - y - 0.7
    w = (theme['slide_width'] - theme['margin'] * 2 - 0.35) / 2
    x1 = theme['margin']
    x2 = x1 + w + 0.35

    _column_card(slide, x1, y, w, h, theme)
    _column_card(slide, x2, y, w, h, theme)

    _add_textbox(
        slide,
        _truncate(left.get('title') or 'Left', max_len=35),
        x1 + 0.2,
        y + 0.15,
        w - 0.4,
        0.36,
        font_name=theme['font_family'],
        font_size=theme['body_font_size'],
        color=theme['accent_color'],
        bold=True,
    )
    _, hidden_left = _add_bullets(
        slide,
        _to_lines(left.get('bullets') or []),
        x1 + 0.16,
        y + 0.54,
        w - 0.3,
        h - 0.7,
        font_name=theme['font_family'],
        font_size=theme['body_font_size'] - 1,
        color=theme['body_color'],
        max_items=_MAX_COLUMN_BULLETS,
    )

    _add_textbox(
        slide,
        _truncate(right.get('title') or 'Right', max_len=35),
        x2 + 0.2,
        y + 0.15,
        w - 0.4,
        0.36,
        font_name=theme['font_family'],
        font_size=theme['body_font_size'],
        color=theme['accent_color'],
        bold=True,
    )
    _, hidden_right = _add_bullets(
        slide,
        _to_lines(right.get('bullets') or []),
        x2 + 0.16,
        y + 0.54,
        w - 0.3,
        h - 0.7,
        font_name=theme['font_family'],
        font_size=theme['body_font_size'] - 1,
        color=theme['body_color'],
        max_items=_MAX_COLUMN_BULLETS,
    )

    notes = slide_data.get('notes') or ''
    if hidden_left or hidden_right:
        notes_tail = []
        if hidden_left:
            notes_tail.append('Left overflow:\n' + '\n'.join(f'- {item}' for item in hidden_left))
        if hidden_right:
            notes_tail.append('Right overflow:\n' + '\n'.join(f'- {item}' for item in hidden_right))
        notes = f"{notes}\n\n" + '\n\n'.join(notes_tail)

    _set_notes(slide, notes.strip(), slide_data.get('evidence_refs') or [])
    _add_footer(slide, idx, len(deck['slides']), theme, slide_data.get('evidence_refs') or [])


def _render_comparison(prs: Presentation, slide_data: Dict[str, Any], deck: Dict[str, Any], idx: int) -> None:
    # If table payload exists, render as comparison table first.
    headers = slide_data.get('headers') or []
    rows = slide_data.get('rows') or []
    if headers and rows:
        _render_table(prs, slide_data, deck, idx)
        return
    _render_two_column(prs, slide_data, deck, idx)


def _render_table(prs: Presentation, slide_data: Dict[str, Any], deck: Dict[str, Any], idx: int) -> None:
    theme = deck['theme']
    slide = _new_slide(prs)
    _set_background(slide, theme['background_color'])
    _add_title_block(slide, slide_data.get('title') or f'Slide {idx}', slide_data.get('subtitle') or '', theme)

    headers = [str(h) for h in (slide_data.get('headers') or (slide_data.get('table') or {}).get('headers') or [])]
    rows = slide_data.get('rows') or (slide_data.get('table') or {}).get('rows') or []

    clipped = False
    if len(headers) > _MAX_TABLE_COLS:
        headers = headers[:_MAX_TABLE_COLS]
        clipped = True
    if len(rows) > _MAX_TABLE_ROWS:
        rows = rows[:_MAX_TABLE_ROWS]
        clipped = True

    if not headers:
        _add_bullets(
            slide,
            _to_lines(slide_data.get('bullets') or ['No table data']),
            theme['margin'],
            theme['top_spacing'],
            theme['slide_width'] - theme['margin'] * 2,
            theme['slide_height'] - theme['top_spacing'] - 0.9,
            font_name=theme['font_family'],
            font_size=theme['body_font_size'],
            color=theme['body_color'],
            max_items=5,
        )
        _set_notes(slide, slide_data.get('notes') or '', slide_data.get('evidence_refs') or [])
        _add_footer(slide, idx, len(deck['slides']), theme, slide_data.get('evidence_refs') or [])
        return

    col_count = len(headers)
    normalized_rows: List[List[str]] = []
    for row in rows:
        if isinstance(row, list):
            values = [str(cell) for cell in (row + [''] * col_count)[:col_count]]
        else:
            values = [str(row)] + [''] * (col_count - 1)
        normalized_rows.append([_truncate(value, max_len=80) for value in values])

    n_rows = max(2, len(normalized_rows) + 1)
    table_left = theme['margin']
    table_top = theme['top_spacing'] + 0.05
    table_width = theme['slide_width'] - theme['margin'] * 2
    table_height = min(4.8, theme['slide_height'] - table_top - 1.0)

    table_shape = slide.shapes.add_table(
        n_rows,
        col_count,
        Inches(table_left),
        Inches(table_top),
        Inches(table_width),
        Inches(table_height),
    )
    table = table_shape.table

    for col_idx, header in enumerate(headers):
        cell = table.cell(0, col_idx)
        cell.text = _truncate(header, max_len=70)
        cell.fill.solid()
        cell.fill.fore_color.rgb = _rgb(theme['accent_color'])
        for paragraph in cell.text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.name = theme['font_family']
                run.font.size = Pt(max(theme['body_font_size'] - 7, 10))
                run.font.bold = True
                run.font.color.rgb = _rgb('FFFFFF')

    body_size = theme['body_font_size'] - 7 if len(normalized_rows) >= 8 else theme['body_font_size'] - 6
    body_size = max(body_size, 9)

    for row_idx, row in enumerate(normalized_rows, start=1):
        for col_idx, value in enumerate(row):
            cell = table.cell(row_idx, col_idx)
            cell.text = value
            for paragraph in cell.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.name = theme['font_family']
                    run.font.size = Pt(body_size)
                    run.font.color.rgb = _rgb(theme['body_color'])

    caption = _to_lines(slide_data.get('bullets') or [])
    if clipped:
        caption.insert(0, '表格已自动裁剪以保证可读性。')
    if caption:
        _add_bullets(
            slide,
            caption,
            theme['margin'],
            table_top + table_height + 0.08,
            theme['slide_width'] - theme['margin'] * 2,
            0.58,
            font_name=theme['font_family'],
            font_size=theme['small_font_size'],
            color=theme['muted_color'],
            max_items=2,
            include_overflow_hint=False,
        )

    _set_notes(slide, slide_data.get('notes') or '', slide_data.get('evidence_refs') or [])
    _add_footer(slide, idx, len(deck['slides']), theme, slide_data.get('evidence_refs') or [])


def _render_summary(prs: Presentation, slide_data: Dict[str, Any], deck: Dict[str, Any], idx: int) -> None:
    theme = deck['theme']
    slide = _new_slide(prs)
    _set_background(slide, theme['background_color'])
    _add_title_block(slide, slide_data.get('title') or ('总结' if deck['language'] == 'zh' else 'Summary'), slide_data.get('subtitle') or '', theme)

    takeaways = _to_lines(slide_data.get('takeaways') or slide_data.get('bullets') or [])[:5]
    y = theme['top_spacing'] + 0.08
    for index, item in enumerate(takeaways, start=1):
        badge = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.OVAL,
            Inches(theme['margin'] + 0.02),
            Inches(y + 0.04),
            Inches(0.34),
            Inches(0.34),
        )
        badge.fill.solid()
        badge.fill.fore_color.rgb = _rgb(theme['accent_color'])
        badge.line.fill.background()

        _add_textbox(
            slide,
            str(index),
            theme['margin'] + 0.02,
            y + 0.07,
            0.34,
            0.24,
            font_name=theme['font_family'],
            font_size=theme['small_font_size'],
            color='FFFFFF',
            bold=True,
            align=PP_ALIGN.CENTER,
            margin=0,
        )
        _add_textbox(
            slide,
            _truncate(item, max_len=160),
            theme['margin'] + 0.48,
            y,
            theme['slide_width'] - theme['margin'] * 2 - 0.48,
            0.46,
            font_name=theme['font_family'],
            font_size=theme['body_font_size'],
            color=theme['body_color'],
        )
        y += 0.76

    _set_notes(slide, slide_data.get('notes') or '', slide_data.get('evidence_refs') or [])
    _add_footer(slide, idx, len(deck['slides']), theme, slide_data.get('evidence_refs') or [])


def _render_references(prs: Presentation, slide_data: Dict[str, Any], deck: Dict[str, Any], idx: int) -> None:
    theme = deck['theme']
    slide = _new_slide(prs)
    _set_background(slide, theme['background_color'])

    title = slide_data.get('title') or ('参考资料' if deck['language'] == 'zh' else 'References')
    _add_title_block(slide, title, slide_data.get('subtitle') or '', theme)

    refs = _to_lines(slide_data.get('items') or slide_data.get('bullets') or slide_data.get('evidence_refs') or [])
    _, hidden = _add_bullets(
        slide,
        refs,
        theme['margin'] + 0.05,
        theme['top_spacing'] + 0.12,
        theme['slide_width'] - theme['margin'] * 2 - 0.1,
        theme['slide_height'] - theme['top_spacing'] - 1.02,
        font_name=theme['font_family'],
        font_size=theme['small_font_size'],
        color=theme['body_color'],
        max_items=14,
    )
    notes = slide_data.get('notes') or ''
    if hidden:
        notes = (notes + '\n\nExtra references:\n' + '\n'.join(hidden)).strip()
    _set_notes(slide, notes, slide_data.get('evidence_refs') or [])
    _add_footer(slide, idx, len(deck['slides']), theme, slide_data.get('evidence_refs') or [])


def render_deck_to_pptx(deck_schema: Any, output_path: str | Path) -> Dict[str, Any]:
    """Render a normalized deck schema to an editable PPTX using python-pptx."""
    deck = normalize_deck_schema(deck_schema)

    theme_payload = deck.get('theme') if isinstance(deck.get('theme'), dict) else {'name': deck.get('theme')}
    theme = resolve_theme(theme_payload, language=deck.get('language') or 'zh')
    deck['theme'] = theme

    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    prs = Presentation()
    prs.slide_width = Inches(float(theme['slide_width']))
    prs.slide_height = Inches(float(theme['slide_height']))

    renderer_map = {
        'cover': _render_cover,
        'toc': _render_toc,
        'section_divider': _render_section,
        'content': _render_content_bullets,
        'content_bullets': _render_content_bullets,
        'two_column': _render_two_column,
        'comparison': _render_comparison,
        'table': _render_table,
        'summary': _render_summary,
        'references': _render_references,
    }

    for idx, slide in enumerate(deck.get('slides') or [], start=1):
        slide_type = str(slide.get('type') or 'content_bullets')
        renderer = renderer_map.get(slide_type, _render_content_bullets)
        renderer(prs, slide, deck, idx)

    prs.save(str(output))

    return {
        'success': True,
        'file_path': str(output),
        'filename': output.name,
        'slide_count': len(deck.get('slides') or []),
        'theme': theme,
        'deck_schema': deck,
    }
