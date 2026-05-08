from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_AUTO_SIZE, MSO_ANCHOR
from pptx.util import Inches, Pt

from .schema import normalize_deck_schema

SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)


def _rgb(hex_color: str) -> RGBColor:
    value = str(hex_color or '000000').strip().lstrip('#')
    if len(value) != 6:
        value = '000000'
    try:
        return RGBColor(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
    except ValueError:
        return RGBColor(0, 0, 0)


def _blank_slide(prs: Presentation):
    return prs.slides.add_slide(prs.slide_layouts[6])


def _set_bg(slide, color: str) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(color)


def _add_textbox(
    slide,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    font_size: int = 24,
    bold: bool = False,
    color: str = '111827',
    font_face: str = 'Microsoft YaHei',
    align: PP_ALIGN | None = None,
    margin: float = 0.05,
):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = Inches(margin)
    tf.margin_right = Inches(margin)
    tf.margin_top = Inches(margin)
    tf.margin_bottom = Inches(margin)
    paragraph = tf.paragraphs[0]
    if align is not None:
        paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text or ''
    run.font.name = font_face
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(color)
    return shape


def _add_title(slide, title: str, theme: Dict[str, Any], *, y: float = 0.35, h: float = 0.55, size: int = 25):
    return _add_textbox(
        slide,
        title,
        0.65,
        y,
        12.0,
        h,
        font_size=size,
        bold=True,
        color=theme['primary'],
        font_face=theme['font_face'],
    )


def _add_accent_bar(slide, theme: Dict[str, Any], *, x: float = 0.65, y: float = 1.0, w: float = 1.2):
    bar = slide.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(0.06))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(theme['accent'])
    bar.line.color.rgb = _rgb(theme['accent'])
    return bar


def _split_bullet_text(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = [line.strip(' \t-•') for line in value.splitlines()]
    elif isinstance(value, Iterable) and not isinstance(value, (dict, bytes, bytearray)):
        items = [str(item).strip() for item in value]
    else:
        items = [str(value).strip()]
    return [item for item in items if item]


def _estimate_bullet_font(items: List[str], default: int = 20) -> int:
    if not items:
        return default
    total_chars = sum(len(item) for item in items)
    if len(items) >= 8 or total_chars > 520:
        return 15
    if len(items) >= 6 or total_chars > 380:
        return 17
    if total_chars > 260:
        return 18
    return default


def _add_bullets(
    slide,
    bullets: List[str],
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    theme: Dict[str, Any],
    font_size: int | None = None,
    level: int = 0,
):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    tf.margin_left = Inches(0.1)
    tf.margin_right = Inches(0.08)
    tf.margin_top = Inches(0.05)
    tf.margin_bottom = Inches(0.05)
    size = font_size or _estimate_bullet_font(bullets)
    for idx, bullet in enumerate(bullets or ['（暂无内容）']):
        para = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        para.text = bullet
        para.level = level
        para.space_after = Pt(7)
        para.font.name = theme['font_face']
        para.font.size = Pt(size)
        para.font.color.rgb = _rgb(theme['primary'])
    return shape


def _add_footer(slide, index: int, total: int, theme: Dict[str, Any], evidence_refs: List[str] | None = None) -> None:
    refs = ' '.join(evidence_refs or [])
    footer_text = f'{index}/{total}' if not refs else f'{refs}    {index}/{total}'
    box = _add_textbox(
        slide,
        footer_text,
        0.65,
        7.08,
        12.0,
        0.25,
        font_size=8,
        color=theme['secondary'],
        font_face=theme['font_face'],
        align=PP_ALIGN.RIGHT,
        margin=0.0,
    )
    box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE


def _render_cover(prs: Presentation, slide_data: Dict[str, Any], deck: Dict[str, Any], idx: int) -> None:
    theme = deck['theme']
    slide = _blank_slide(prs)
    _set_bg(slide, theme['background'])
    # simple left accent block
    block = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(0.22), SLIDE_HEIGHT)
    block.fill.solid()
    block.fill.fore_color.rgb = _rgb(theme['accent'])
    block.line.color.rgb = _rgb(theme['accent'])
    _add_textbox(
        slide,
        slide_data.get('title') or deck['title'],
        0.85,
        2.0,
        11.8,
        1.1,
        font_size=34,
        bold=True,
        color=theme['primary'],
        font_face=theme['font_face'],
    )
    subtitle = slide_data.get('subtitle') or deck.get('subtitle') or ''
    if subtitle:
        _add_textbox(
            slide,
            subtitle,
            0.9,
            3.15,
            11.2,
            0.55,
            font_size=17,
            color=theme['secondary'],
            font_face=theme['font_face'],
        )
    _add_accent_bar(slide, theme, x=0.9, y=4.0, w=1.6)
    _add_footer(slide, idx, len(deck['slides']), theme, slide_data.get('evidence_refs'))


def _render_section(prs: Presentation, slide_data: Dict[str, Any], deck: Dict[str, Any], idx: int) -> None:
    theme = deck['theme']
    slide = _blank_slide(prs)
    _set_bg(slide, theme['muted_background'])
    _add_textbox(
        slide,
        slide_data.get('title') or f'Section {idx}',
        0.95,
        2.45,
        11.5,
        0.9,
        font_size=31,
        bold=True,
        color=theme['primary'],
        font_face=theme['font_face'],
        align=PP_ALIGN.CENTER,
    )
    if slide_data.get('subtitle'):
        _add_textbox(
            slide,
            slide_data['subtitle'],
            1.4,
            3.35,
            10.5,
            0.5,
            font_size=15,
            color=theme['secondary'],
            font_face=theme['font_face'],
            align=PP_ALIGN.CENTER,
        )
    _add_footer(slide, idx, len(deck['slides']), theme, slide_data.get('evidence_refs'))


def _render_toc(prs: Presentation, slide_data: Dict[str, Any], deck: Dict[str, Any], idx: int) -> None:
    theme = deck['theme']
    slide = _blank_slide(prs)
    _set_bg(slide, theme['background'])
    _add_title(slide, slide_data.get('title') or '目录', theme)
    _add_accent_bar(slide, theme)
    items = slide_data.get('items') or slide_data.get('bullets') or []
    y = 1.55
    for i, item in enumerate(items[:10], start=1):
        _add_textbox(slide, f'{i:02d}', 1.0, y, 0.55, 0.35, font_size=14, bold=True, color=theme['accent'], font_face=theme['font_face'])
        _add_textbox(slide, str(item), 1.7, y - 0.02, 10.2, 0.4, font_size=18, color=theme['primary'], font_face=theme['font_face'])
        y += 0.48
    _add_footer(slide, idx, len(deck['slides']), theme, slide_data.get('evidence_refs'))


def _render_content(prs: Presentation, slide_data: Dict[str, Any], deck: Dict[str, Any], idx: int) -> None:
    theme = deck['theme']
    slide = _blank_slide(prs)
    _set_bg(slide, theme['background'])
    _add_title(slide, slide_data.get('title') or f'Slide {idx}', theme)
    _add_accent_bar(slide, theme)
    bullets = _split_bullet_text(slide_data.get('bullets'))
    if slide_data.get('subtitle'):
        _add_textbox(slide, slide_data['subtitle'], 0.78, 1.22, 11.8, 0.35, font_size=12, color=theme['secondary'], font_face=theme['font_face'])
        y, h = 1.75, 5.05
    else:
        y, h = 1.55, 5.25
    _add_bullets(slide, bullets, 0.85, y, 11.7, h, theme=theme)
    _add_footer(slide, idx, len(deck['slides']), theme, slide_data.get('evidence_refs'))


def _render_two_column(prs: Presentation, slide_data: Dict[str, Any], deck: Dict[str, Any], idx: int) -> None:
    theme = deck['theme']
    slide = _blank_slide(prs)
    _set_bg(slide, theme['background'])
    _add_title(slide, slide_data.get('title') or f'Slide {idx}', theme)
    _add_accent_bar(slide, theme)
    left = slide_data.get('left') or {}
    right = slide_data.get('right') or {}
    # Column cards
    for x in (0.8, 6.85):
        card = slide.shapes.add_shape(1, Inches(x), Inches(1.55), Inches(5.65), Inches(5.25))
        card.fill.solid()
        card.fill.fore_color.rgb = _rgb(theme['muted_background'])
        card.line.color.rgb = _rgb('E5E7EB')
    _add_textbox(slide, str(left.get('title') or 'A'), 1.05, 1.75, 5.1, 0.35, font_size=17, bold=True, color=theme['accent'], font_face=theme['font_face'])
    _add_bullets(slide, _split_bullet_text(left.get('bullets')), 1.0, 2.25, 5.25, 4.25, theme=theme, font_size=16)
    _add_textbox(slide, str(right.get('title') or 'B'), 7.1, 1.75, 5.1, 0.35, font_size=17, bold=True, color=theme['accent'], font_face=theme['font_face'])
    _add_bullets(slide, _split_bullet_text(right.get('bullets')), 7.05, 2.25, 5.25, 4.25, theme=theme, font_size=16)
    _add_footer(slide, idx, len(deck['slides']), theme, slide_data.get('evidence_refs'))


def _render_table(prs: Presentation, slide_data: Dict[str, Any], deck: Dict[str, Any], idx: int) -> None:
    theme = deck['theme']
    slide = _blank_slide(prs)
    _set_bg(slide, theme['background'])
    _add_title(slide, slide_data.get('title') or f'Slide {idx}', theme)
    _add_accent_bar(slide, theme)
    table_data = slide_data.get('table') or {}
    headers = list(table_data.get('headers') or [])[:7]
    rows = list(table_data.get('rows') or [])[:9]
    if not headers:
        _add_bullets(slide, slide_data.get('bullets') or ['表格数据为空'], 0.85, 1.55, 11.7, 5.2, theme=theme)
        _add_footer(slide, idx, len(deck['slides']), theme, slide_data.get('evidence_refs'))
        return
    n_rows = max(1, len(rows) + 1)
    n_cols = max(1, len(headers))
    table_shape = slide.shapes.add_table(n_rows, n_cols, Inches(0.75), Inches(1.55), Inches(11.85), Inches(4.75))
    table = table_shape.table
    for c, header in enumerate(headers):
        cell = table.cell(0, c)
        cell.text = str(header)
        cell.fill.solid()
        cell.fill.fore_color.rgb = _rgb(theme['accent'])
        for paragraph in cell.text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.name = theme['font_face']
                run.font.size = Pt(10)
                run.font.bold = True
                run.font.color.rgb = _rgb('FFFFFF')
    for r, row in enumerate(rows, start=1):
        for c, value in enumerate((list(row) + [''] * n_cols)[:n_cols]):
            cell = table.cell(r, c)
            cell.text = str(value)
            for paragraph in cell.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.name = theme['font_face']
                    run.font.size = Pt(8 if n_rows > 7 else 9)
                    run.font.color.rgb = _rgb(theme['primary'])
    caption = slide_data.get('bullets') or []
    if caption:
        _add_bullets(slide, caption[:2], 0.85, 6.35, 11.7, 0.55, theme=theme, font_size=10)
    _add_footer(slide, idx, len(deck['slides']), theme, slide_data.get('evidence_refs'))


def _render_summary(prs: Presentation, slide_data: Dict[str, Any], deck: Dict[str, Any], idx: int) -> None:
    theme = deck['theme']
    slide = _blank_slide(prs)
    _set_bg(slide, theme['background'])
    _add_title(slide, slide_data.get('title') or '总结', theme)
    _add_accent_bar(slide, theme)
    takeaways = slide_data.get('takeaways') or slide_data.get('bullets') or []
    y = 1.55
    for i, item in enumerate(takeaways[:5], start=1):
        badge = slide.shapes.add_shape(9, Inches(0.95), Inches(y + 0.03), Inches(0.38), Inches(0.38))
        badge.fill.solid()
        badge.fill.fore_color.rgb = _rgb(theme['accent'])
        badge.line.color.rgb = _rgb(theme['accent'])
        _add_textbox(slide, str(i), 0.95, y + 0.06, 0.38, 0.22, font_size=8, bold=True, color='FFFFFF', font_face=theme['font_face'], align=PP_ALIGN.CENTER, margin=0)
        _add_textbox(slide, str(item), 1.55, y, 10.7, 0.45, font_size=18, color=theme['primary'], font_face=theme['font_face'])
        y += 0.78
    _add_footer(slide, idx, len(deck['slides']), theme, slide_data.get('evidence_refs'))


def render_deck_to_pptx(deck_schema: Any, output_path: str | Path) -> Dict[str, Any]:
    """Render a normalized deck schema to an editable PPTX using python-pptx."""
    deck = normalize_deck_schema(deck_schema)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    # Remove default slide if a template ever creates one. Blank Presentation has no slides.
    for idx, slide_data in enumerate(deck['slides'], start=1):
        slide_type = slide_data.get('type')
        if slide_type == 'cover':
            _render_cover(prs, slide_data, deck, idx)
        elif slide_type == 'toc':
            _render_toc(prs, slide_data, deck, idx)
        elif slide_type == 'section_divider':
            _render_section(prs, slide_data, deck, idx)
        elif slide_type in {'two_column', 'comparison'}:
            _render_two_column(prs, slide_data, deck, idx)
        elif slide_type == 'table':
            _render_table(prs, slide_data, deck, idx)
        elif slide_type == 'summary':
            _render_summary(prs, slide_data, deck, idx)
        else:
            _render_content(prs, slide_data, deck, idx)

    prs.save(str(path))
    return {
        'success': True,
        'file_path': str(path),
        'filename': path.name,
        'slide_count': len(deck['slides']),
        'deck_schema': deck,
    }
