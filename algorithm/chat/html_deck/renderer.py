from __future__ import annotations

import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from .artifact import artifact_dir, save_artifact, static_file_url
from .schema import normalize_visual_deck_schema


def _h(value: Any) -> str:
    return html.escape(str(value or ''), quote=True)


def _safe_name(value: Any, default: str = 'visual_deck') -> str:
    text = str(value or default).strip().replace('..', '').replace('\\', '/').split('/')[-1]
    text = re.sub(r'[^A-Za-z0-9._-]+', '_', text).strip('._-')
    return text or default


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        parts = [p.strip(' \t-•') for p in value.replace('；', '\n').replace(';', '\n').split('\n')]
        return [p for p in parts if p]
    if isinstance(value, Iterable) and not isinstance(value, (dict, bytes, bytearray)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()]


def _trim(value: Any, max_len: int = 120) -> str:
    text = str(value or '').strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + '…'


def _hex_to_rgb(value: str, default: tuple[int, int, int] = (255, 255, 255)) -> tuple[int, int, int]:
    text = str(value or '').strip().lstrip('#')
    if len(text) == 3:
        text = ''.join(ch * 2 for ch in text)
    if len(text) != 6:
        return default
    try:
        return int(text[:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return default


def _rgba(value: str, alpha: float) -> str:
    r, g, b = _hex_to_rgb(value)
    return f'rgba({r},{g},{b},{alpha})'


def _slide_badge(page: int, total: int) -> str:
    return f'<span class="page-badge">{page:02d}/{total:02d}</span>'


def _source_footer(slide: Mapping[str, Any]) -> str:
    refs = _as_list(slide.get('evidence_refs'))[:4]
    if not refs:
        return ''
    return f'<div class="sources">Sources: {_h(" · ".join(refs))}</div>'


def _decorations(theme: Mapping[str, Any]) -> str:
    accent = theme['accent']
    secondary = theme['secondary']
    border = theme['border']
    if theme.get('mode') == 'dark':
        return f'''
        <svg class="bg-svg" viewBox="0 0 960 540" aria-hidden="true">
          <defs>
            <pattern id="dots" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
              <circle cx="20" cy="20" r="1.3" fill="{_rgba(border, 0.45)}"/>
            </pattern>
            <radialGradient id="glowA" cx="68%" cy="25%" r="62%">
              <stop offset="0%" stop-color="{_rgba(accent, 0.28)}"/>
              <stop offset="55%" stop-color="{_rgba(secondary, 0.16)}"/>
              <stop offset="100%" stop-color="rgba(0,0,0,0)"/>
            </radialGradient>
          </defs>
          <rect width="960" height="540" fill="url(#dots)"/>
          <circle cx="700" cy="170" r="280" fill="url(#glowA)"/>
          <circle cx="80" cy="470" r="120" fill="{_rgba(accent, 0.12)}"/>
          <path d="M0 0 L46 0 L0 46 Z" fill="{_rgba(accent, 0.22)}"/>
          <path d="M960 540 L914 540 L960 494 Z" fill="{_rgba(accent, 0.22)}"/>
        </svg>
        '''
    return f'''
    <svg class="bg-svg" viewBox="0 0 960 540" aria-hidden="true">
      <defs>
        <pattern id="grid" x="0" y="0" width="32" height="32" patternUnits="userSpaceOnUse">
          <path d="M 32 0 L 0 0 0 32" fill="none" stroke="{_rgba(border, 0.45)}" stroke-width="1"/>
        </pattern>
        <linearGradient id="wash" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="{_rgba(accent, 0.10)}"/>
          <stop offset="100%" stop-color="{_rgba(secondary, 0.14)}"/>
        </linearGradient>
      </defs>
      <rect width="960" height="540" fill="url(#grid)"/>
      <rect width="960" height="540" fill="url(#wash)"/>
      <circle cx="820" cy="70" r="110" fill="{_rgba(accent, 0.10)}"/>
      <circle cx="70" cy="470" r="85" fill="{_rgba(secondary, 0.10)}"/>
      <path d="M0 0 L66 0 L0 66 Z" fill="{_rgba(accent, 0.16)}"/>
      <path d="M960 540 L894 540 L960 474 Z" fill="{_rgba(accent, 0.16)}"/>
    </svg>
    '''


def _layout_cover(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    title = _trim(slide.get('title') or deck.get('title'), 64)
    subtitle = _trim(slide.get('subtitle') or deck.get('subtitle'), 110)
    highlight = _trim(slide.get('highlight') or '', 40)
    date_text = _trim(slide.get('date') or datetime.now(timezone.utc).strftime('%Y-%m'), 20)
    return f'''
    {_decorations(deck['visual_theme'])}
    <div class="cover-wrap">
      <div class="cover-line"></div>
      <h1>{_h(title)}</h1>
      <p class="subtitle">{_h(subtitle)}</p>
      <p class="meta">{_h(highlight)} <span>{_h(date_text)}</span></p>
    </div>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_toc(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    items = _as_list(slide.get('items') or slide.get('bullets'))
    if not items:
        items = [s.get('title') for s in deck.get('slides', [])[1:] if s.get('title')]
    rows = ''.join(
        f'<li><span>{idx:02d}</span><p>{_h(_trim(item, 56))}</p></li>'
        for idx, item in enumerate(items[:9], start=1)
    )
    return f'''
    {_decorations(deck['visual_theme'])}
    <h2 class="slide-title">{_h(slide.get('title') or ('目录' if deck.get('language') == 'zh' else 'Contents'))}</h2>
    <div class="title-rule"></div>
    <ol class="toc-list">{rows}</ol>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_section(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    section_no = _trim(slide.get('section_number') or f'{page:02d}', 8)
    return f'''
    {_decorations(deck['visual_theme'])}
    <div class="section-center">
      <div class="section-no">{_h(section_no)}</div>
      <h2>{_h(_trim(slide.get('title'), 46))}</h2>
      <p>{_h(_trim(slide.get('subtitle'), 80))}</p>
    </div>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_metric_cards(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    metrics = slide.get('metrics') if isinstance(slide.get('metrics'), list) else []
    cards = []
    for idx, item in enumerate(metrics[:4]):
        if not isinstance(item, Mapping):
            continue
        cards.append(
            f'<article class="metric-card"><h4>{_h(_trim(item.get("label"), 22))}</h4><strong>{_h(_trim(item.get("value"), 18))}</strong><p>{_h(_trim(item.get("description"), 64))}</p></article>'
        )
    while len(cards) < 3:
        cards.append('<article class="metric-card"><h4>指标</h4><strong>--</strong><p>N/A</p></article>')
    bullets = ''.join(f'<li>{_h(_trim(x, 86))}</li>' for x in _as_list(slide.get('bullets'))[:4])
    return f'''
    {_decorations(deck['visual_theme'])}
    <h2 class="slide-title">{_h(_trim(slide.get('title'), 52))}</h2>
    <div class="title-rule"></div>
    <div class="metric-grid">{''.join(cards)}</div>
    <div class="callout">{_h(_trim(slide.get('subtitle') or '关键结论：指标变化正在重塑工作方式。', 96))}</div>
    <ul class="bullet-list">{bullets}</ul>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_challenge_cards(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    cards = slide.get('cards') if isinstance(slide.get('cards'), list) and slide.get('cards') else []
    if not cards:
        cards = [{'title': '', 'body': txt, 'accent': 'primary'} for txt in _as_list(slide.get('bullets'))[:6]]
    grid = ''.join(
        f'<article class="challenge-card"><h4>{_h(_trim(item.get("title") or f"Point {idx+1}", 26))}</h4><p>{_h(_trim(item.get("body"), 96))}</p></article>'
        for idx, item in enumerate(cards[:6])
    )
    return f'''
    {_decorations(deck['visual_theme'])}
    <h2 class="slide-title">{_h(_trim(slide.get('title'), 52))}</h2>
    <div class="title-rule"></div>
    <div class="challenge-grid">{grid}</div>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_content_bullets(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    bullets = _as_list(slide.get('bullets'))[:6]
    if not bullets:
        bullets = _as_list(slide.get('items'))[:6]
    rows = ''.join(f'<li><span></span>{_h(_trim(item, 98))}</li>' for item in bullets)
    return f'''
    {_decorations(deck['visual_theme'])}
    <h2 class="slide-title">{_h(_trim(slide.get('title'), 52))}</h2>
    <div class="title-rule"></div>
    <div class="content-panel">
      <p class="intro">{_h(_trim(slide.get('subtitle') or '', 120))}</p>
      <ul class="bullet-list bullet-large">{rows}</ul>
    </div>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_two_column(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    left = slide.get('left') if isinstance(slide.get('left'), Mapping) else {}
    right = slide.get('right') if isinstance(slide.get('right'), Mapping) else {}
    if not left or not right:
        columns = slide.get('columns') if isinstance(slide.get('columns'), list) else []
        if len(columns) >= 2:
            left = columns[0] if isinstance(columns[0], Mapping) else {'title': 'Left', 'bullets': _as_list(columns[0])}
            right = columns[1] if isinstance(columns[1], Mapping) else {'title': 'Right', 'bullets': _as_list(columns[1])}
    def _col(item: Mapping[str, Any], cls: str) -> str:
        bullets = ''.join(f'<li>{_h(_trim(x, 56))}</li>' for x in _as_list(item.get('bullets') or item.get('items'))[:5])
        return f'<article class="column-card {cls}"><h4>{_h(_trim(item.get("title") or cls, 24))}</h4><ul>{bullets}</ul></article>'
    return f'''
    {_decorations(deck['visual_theme'])}
    <h2 class="slide-title">{_h(_trim(slide.get('title'), 52))}</h2>
    <div class="title-rule"></div>
    <div class="column-wrap">{_col(left, 'left')}{_col(right, 'right')}</div>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_comparison(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    rows = slide.get('rows') if isinstance(slide.get('rows'), list) else []
    headers = _as_list(slide.get('headers'))
    if headers and rows:
        head = ''.join(f'<th>{_h(_trim(h, 18))}</th>' for h in headers[:4])
        body_rows = []
        for row in rows[:6]:
            cells = row if isinstance(row, list) else [row]
            body_rows.append('<tr>' + ''.join(f'<td>{_h(_trim(c, 40))}</td>' for c in cells[: len(headers)]) + '</tr>')
        matrix = f'<table class="compare-table"><thead><tr>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table>'
    else:
        left_title = _trim(slide.get('left_title') or 'A', 22)
        right_title = _trim(slide.get('right_title') or 'B', 22)
        left_items = ''.join(f'<li>{_h(_trim(x, 54))}</li>' for x in _as_list(slide.get('left_items'))[:5])
        right_items = ''.join(f'<li>{_h(_trim(x, 54))}</li>' for x in _as_list(slide.get('right_items'))[:5])
        matrix = (
            '<div class="compare-cards">'
            f'<article><h4>{_h(left_title)}</h4><ul>{left_items}</ul></article>'
            f'<article><h4>{_h(right_title)}</h4><ul>{right_items}</ul></article>'
            '</div>'
        )
    return f'''
    {_decorations(deck['visual_theme'])}
    <h2 class="slide-title">{_h(_trim(slide.get('title'), 52))}</h2>
    <div class="title-rule"></div>
    {matrix}
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_table(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    headers = _as_list(slide.get('headers'))
    rows = slide.get('rows') if isinstance(slide.get('rows'), list) else []
    if not headers:
        headers = ['维度', '现状', '建议']
    head = ''.join(f'<th>{_h(_trim(h, 18))}</th>' for h in headers[:8])
    body_rows = []
    for row in rows[:10]:
        cells = row if isinstance(row, list) else [row]
        cells = list(cells[: len(headers)])
        while len(cells) < len(headers):
            cells.append('')
        body_rows.append('<tr>' + ''.join(f'<td>{_h(_trim(c, 34))}</td>' for c in cells) + '</tr>')
    if not body_rows:
        body_rows.append('<tr>' + ''.join('<td>—</td>' for _ in headers[:3]) + '</tr>')
    return f'''
    {_decorations(deck['visual_theme'])}
    <h2 class="slide-title">{_h(_trim(slide.get('title'), 52))}</h2>
    <div class="title-rule"></div>
    <table class="data-table"><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_summary(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    bullets = _as_list(slide.get('bullets') or slide.get('items'))[:5]
    if not bullets:
        bullets = ['形成统一结论', '明确下一步行动', '持续迭代与复盘']
    rows = ''.join(f'<article class="takeaway"><span>{idx:02d}</span><p>{_h(_trim(item, 88))}</p></article>' for idx, item in enumerate(bullets, start=1))
    return f'''
    {_decorations(deck['visual_theme'])}
    <h2 class="slide-title">{_h(_trim(slide.get('title') or '总结与行动建议', 52))}</h2>
    <div class="title-rule"></div>
    <div class="takeaway-grid">{rows}</div>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_quote(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    quote = _trim(slide.get('quote') or (slide.get('bullets') or [''])[0] or '“真正的竞争力来自持续学习与系统思考。”', 140)
    author = _trim(slide.get('author') or slide.get('subtitle') or '', 60)
    return f'''
    {_decorations(deck['visual_theme'])}
    <div class="quote-wrap">
      <p class="quote-mark">“</p>
      <blockquote>{_h(quote)}</blockquote>
      <div class="quote-author">{_h(author)}</div>
    </div>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_process(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    steps = _as_list(slide.get('steps') or slide.get('bullets') or slide.get('items'))[:6]
    if not steps:
        steps = ['识别问题', '构建方案', '落地执行', '监控迭代']
    cards = ''.join(
        f'<article class="process-step"><span>{idx:02d}</span><p>{_h(_trim(step, 48))}</p></article>'
        for idx, step in enumerate(steps, start=1)
    )
    return f'''
    {_decorations(deck['visual_theme'])}
    <h2 class="slide-title">{_h(_trim(slide.get('title'), 52))}</h2>
    <div class="title-rule"></div>
    <div class="process-row">{cards}</div>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_timeline(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    items = slide.get('timeline') if isinstance(slide.get('timeline'), list) else []
    if not items:
        items = [{'time': f'Q{idx+1}', 'title': txt} for idx, txt in enumerate(_as_list(slide.get('bullets') or slide.get('items'))[:5])]
    rows = []
    for idx, item in enumerate(items[:6], start=1):
        if isinstance(item, Mapping):
            t = _trim(item.get('time') or item.get('date') or f'S{idx}', 18)
            title = _trim(item.get('title') or item.get('event') or '', 42)
            desc = _trim(item.get('description') or item.get('desc') or '', 70)
        else:
            t = f'S{idx}'
            title = _trim(item, 42)
            desc = ''
        rows.append(f'<article class="timeline-item"><span>{_h(t)}</span><h4>{_h(title)}</h4><p>{_h(desc)}</p></article>')
    return f'''
    {_decorations(deck['visual_theme'])}
    <h2 class="slide-title">{_h(_trim(slide.get('title'), 52))}</h2>
    <div class="title-rule"></div>
    <div class="timeline-wrap">{''.join(rows)}</div>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_references(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    refs = _as_list(slide.get('items') or slide.get('bullets') or slide.get('evidence_refs'))[:12]
    rows = ''.join(f'<li>{_h(_trim(ref, 100))}</li>' for ref in refs)
    return f'''
    {_decorations(deck['visual_theme'])}
    <h2 class="slide-title">{_h(_trim(slide.get('title') or 'References', 52))}</h2>
    <div class="title-rule"></div>
    <ol class="reference-list">{rows}</ol>
    {_slide_badge(page, total)}
    '''


_LAYOUTS = {
    'cover_hero': _layout_cover,
    'toc_numbered': _layout_toc,
    'section_divider': _layout_section,
    'metric_cards': _layout_metric_cards,
    'challenge_cards': _layout_challenge_cards,
    'content_bullets': _layout_content_bullets,
    'two_column': _layout_two_column,
    'comparison': _layout_comparison,
    'table': _layout_table,
    'summary': _layout_summary,
    'quote': _layout_quote,
    'process': _layout_process,
    'timeline': _layout_timeline,
    'references': _layout_references,
}


def _base_css(theme: Mapping[str, Any]) -> str:
    mode_bg = theme['background']
    accent = theme['accent']
    border = theme['border']
    return f'''
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; width: 100%; height: 100%; background: #050505; display: flex; align-items: center; justify-content: center; overflow: hidden; }}
    body {{ font-family: {theme['font_zh']}; }}
    .slide-content {{ width: {int(theme['canvas_width'])}px; height: {int(theme['canvas_height'])}px; position: relative; overflow: hidden; background: {mode_bg}; color: {theme['foreground']}; border: 1px solid {border}; }}
    .bg-svg {{ position: absolute; left: 0; top: 0; width: 100%; height: 100%; pointer-events: none; }}
    .page-badge {{ position: absolute; right: 22px; bottom: 16px; padding: 6px 10px; border-radius: 999px; font: 700 12px {theme['font_en']}; background: {accent}; color: {theme['background']}; }}
    .sources {{ position: absolute; left: 24px; bottom: 18px; max-width: 720px; color: {theme['muted']}; font-size: {theme['caption_font_size']}px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .slide-title {{ position: absolute; left: 30px; top: 20px; margin: 0; font-size: {theme['title_font_size']}px; line-height: 1.14; letter-spacing: 0.5px; z-index: 2; }}
    .title-rule {{ position: absolute; left: 30px; top: 78px; width: 280px; height: 4px; border-radius: 2px; background: {accent}; z-index: 2; }}

    .cover-wrap {{ position: absolute; left: 70px; top: 120px; width: 760px; z-index: 2; }}
    .cover-line {{ width: 140px; height: 4px; border-radius: 2px; background: {accent}; margin-bottom: 24px; }}
    .cover-wrap h1 {{ margin: 0; font-size: 54px; line-height: 1.2; }}
    .cover-wrap .subtitle {{ margin: 24px 0 0; color: {theme['muted']}; font-size: 24px; }}
    .cover-wrap .meta {{ margin: 28px 0 0; font-size: 15px; color: {theme['muted']}; }}
    .cover-wrap .meta span {{ margin-left: 18px; color: {theme['accent']}; }}

    .toc-list {{ position: absolute; left: 52px; top: 104px; width: 840px; margin: 0; padding: 0; list-style: none; z-index: 2; }}
    .toc-list li {{ display: grid; grid-template-columns: 52px 1fr; gap: 14px; align-items: baseline; margin: 10px 0; }}
    .toc-list li span {{ font: 800 26px {theme['font_en']}; color: {theme['accent']}; }}
    .toc-list li p {{ margin: 0; font-size: 24px; line-height: 1.3; }}

    .section-center {{ position: absolute; inset: 0; display: flex; flex-direction: column; justify-content: center; align-items: center; z-index: 2; }}
    .section-center .section-no {{ font: 900 94px {theme['font_en']}; color: {theme['accent']}; line-height: 1; }}
    .section-center h2 {{ margin: 14px 0 0; font-size: 50px; }}
    .section-center p {{ margin: 14px 0 0; font-size: 22px; color: {theme['muted']}; }}

    .metric-grid {{ position: absolute; left: 30px; top: 102px; width: 900px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; z-index: 2; }}
    .metric-card {{ background: {theme['surface']}; border: 1px solid {border}; border-left: 4px solid {accent}; border-radius: {theme['radius']}px; padding: 14px 16px; box-shadow: {theme['shadow']}; min-height: 138px; }}
    .metric-card h4 {{ margin: 0; font-size: 13px; color: {theme['muted']}; }}
    .metric-card strong {{ display: block; margin-top: 10px; font: 800 42px {theme['font_en']}; color: {theme['accent']}; }}
    .metric-card p {{ margin: 10px 0 0; font-size: 13px; color: {theme['muted']}; line-height: 1.45; }}
    .callout {{ position: absolute; left: 30px; top: 264px; width: 900px; border: 1px solid {border}; background: {theme['surface_alt']}; border-radius: {theme['radius']}px; padding: 12px 14px; font-size: 18px; z-index: 2; }}

    .bullet-list {{ position: absolute; left: 44px; top: 326px; width: 870px; margin: 0; padding: 0; list-style: none; z-index: 2; }}
    .bullet-list li {{ position: relative; margin: 10px 0; padding-left: 20px; font-size: 15px; color: {theme['muted']}; line-height: 1.48; }}
    .bullet-list li span {{ position: absolute; left: 0; top: 8px; width: 8px; height: 8px; border-radius: 50%; background: {accent}; }}
    .bullet-large li {{ font-size: 18px; line-height: 1.5; }}

    .challenge-grid {{ position: absolute; left: 30px; top: 102px; width: 900px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; z-index: 2; }}
    .challenge-card {{ min-height: 130px; background: {theme['surface']}; border: 1px solid {border}; border-radius: {theme['radius']}px; box-shadow: {theme['shadow']}; padding: 14px 16px; }}
    .challenge-card h4 {{ margin: 0; font-size: 18px; color: {theme['accent']}; }}
    .challenge-card p {{ margin: 10px 0 0; font-size: 14px; color: {theme['muted']}; line-height: 1.46; }}

    .content-panel {{ position: absolute; left: 30px; top: 108px; width: 900px; min-height: 360px; padding: 18px; background: {theme['surface']}; border: 1px solid {border}; border-radius: {theme['radius']}px; box-shadow: {theme['shadow']}; z-index: 2; }}
    .content-panel .intro {{ margin: 0 0 8px; font-size: 18px; color: {theme['muted']}; }}

    .column-wrap {{ position: absolute; left: 30px; top: 104px; width: 900px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; z-index: 2; }}
    .column-card {{ min-height: 340px; background: {theme['surface']}; border: 1px solid {border}; border-radius: {theme['radius']}px; box-shadow: {theme['shadow']}; padding: 16px 18px; }}
    .column-card h4 {{ margin: 0; font-size: 24px; color: {theme['accent']}; }}
    .column-card ul {{ margin: 14px 0 0; padding-left: 20px; color: {theme['muted']}; }}
    .column-card li {{ margin: 8px 0; font-size: 16px; line-height: 1.46; }}

    .compare-table, .data-table {{ position: absolute; left: 30px; top: 110px; width: 900px; border-collapse: collapse; z-index: 2; border-radius: {theme['radius']}px; overflow: hidden; box-shadow: {theme['shadow']}; }}
    .compare-table thead th, .data-table thead th {{ background: {theme['accent']}; color: {theme['background']}; padding: 12px; font-size: 14px; text-align: left; }}
    .compare-table tbody td, .data-table tbody td {{ background: {theme['surface']}; color: {theme['muted']}; padding: 11px 12px; border-bottom: 1px solid {border}; font-size: 13px; line-height: 1.4; }}

    .compare-cards {{ position: absolute; left: 30px; top: 112px; width: 900px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; z-index: 2; }}
    .compare-cards article {{ min-height: 280px; background: {theme['surface']}; border: 1px solid {border}; border-radius: {theme['radius']}px; padding: 14px 16px; box-shadow: {theme['shadow']}; }}
    .compare-cards h4 {{ margin: 0; color: {theme['accent']}; font-size: 24px; }}
    .compare-cards ul {{ margin: 14px 0 0; padding-left: 18px; color: {theme['muted']}; }}
    .compare-cards li {{ margin: 8px 0; font-size: 15px; }}

    .takeaway-grid {{ position: absolute; left: 30px; top: 110px; width: 900px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; z-index: 2; }}
    .takeaway {{ min-height: 96px; display: grid; grid-template-columns: 56px 1fr; gap: 10px; align-items: center; background: {theme['surface']}; border: 1px solid {border}; border-radius: {theme['radius']}px; padding: 12px 14px; box-shadow: {theme['shadow']}; }}
    .takeaway span {{ font: 800 30px {theme['font_en']}; color: {theme['accent']}; }}
    .takeaway p {{ margin: 0; font-size: 16px; line-height: 1.45; }}

    .quote-wrap {{ position: absolute; left: 76px; top: 110px; width: 808px; min-height: 280px; padding: 26px 30px; background: {theme['surface']}; border: 1px solid {border}; border-radius: {theme['radius']}px; box-shadow: {theme['shadow']}; z-index: 2; }}
    .quote-mark {{ margin: 0; font: 700 80px {theme['font_en']}; color: {theme['accent']}; line-height: 0.8; }}
    .quote-wrap blockquote {{ margin: 10px 0 0; font-size: 31px; line-height: 1.34; }}
    .quote-author {{ margin-top: 24px; font-size: 16px; color: {theme['muted']}; text-align: right; }}

    .process-row {{ position: absolute; left: 30px; top: 112px; width: 900px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; z-index: 2; }}
    .process-step {{ min-height: 180px; background: {theme['surface']}; border: 1px solid {border}; border-radius: {theme['radius']}px; padding: 12px; box-shadow: {theme['shadow']}; }}
    .process-step span {{ display: inline-block; padding: 4px 8px; border-radius: 999px; background: {accent}; color: {theme['background']}; font: 800 12px {theme['font_en']}; }}
    .process-step p {{ margin: 20px 0 0; font-size: 17px; line-height: 1.45; color: {theme['foreground']}; }}

    .timeline-wrap {{ position: absolute; left: 44px; top: 110px; width: 872px; display: grid; grid-template-columns: 1fr; gap: 10px; z-index: 2; }}
    .timeline-item {{ display: grid; grid-template-columns: 84px 220px 1fr; align-items: center; background: {theme['surface']}; border: 1px solid {border}; border-radius: 10px; padding: 10px 14px; box-shadow: {theme['shadow']}; }}
    .timeline-item span {{ font: 800 16px {theme['font_en']}; color: {theme['accent']}; }}
    .timeline-item h4 {{ margin: 0; font-size: 18px; color: {theme['foreground']}; }}
    .timeline-item p {{ margin: 0; font-size: 14px; color: {theme['muted']}; line-height: 1.35; }}

    .reference-list {{ position: absolute; left: 52px; top: 110px; width: 860px; margin: 0; padding-left: 24px; color: {theme['muted']}; z-index: 2; }}
    .reference-list li {{ margin: 8px 0; font-size: 14px; line-height: 1.45; }}
    '''


def _scale_script(width: int, height: int) -> str:
    return f'''
    function scaleSlide() {{
      const slide = document.querySelector('.slide-content');
      if (!slide) return;
      const scale = Math.min(window.innerWidth / {width}, window.innerHeight / {height});
      slide.style.transform = `scale(${{scale}})`;
      slide.style.transformOrigin = 'center center';
    }}
    window.addEventListener('load', scaleSlide);
    window.addEventListener('resize', scaleSlide);
    '''


def render_slide_html(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    layout = str(slide.get('visual_layout') or slide.get('layout') or 'content_bullets')
    renderer = _LAYOUTS.get(layout, _layout_content_bullets)
    body = renderer(slide, deck, page, total)
    theme = deck['visual_theme']
    width = int(theme.get('canvas_width') or 960)
    height = int(theme.get('canvas_height') or 540)
    title = _trim(slide.get('title') or deck.get('title') or f'Slide {page}', 80)
    return f'''<!DOCTYPE html>
<html lang="{_h(deck.get('language') or 'zh')}">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{_h(title)}</title>
  <style>{_base_css(theme)}</style>
  <script>{_scale_script(width, height)}</script>
</head>
<body>
  <div class="slide-content">{body}</div>
</body>
</html>
'''


def _index_html(deck: Mapping[str, Any], slide_files: List[Path]) -> str:
    theme = deck['visual_theme']
    rows = []
    for idx, path in enumerate(slide_files, start=1):
        slide = (deck.get('slides') or [])[idx - 1]
        rows.append(
            f'<li><a href="{_h(path.name)}" target="slide-frame"><span>{idx:02d}</span><p>{_h(_trim(slide.get("title"), 52))}</p><small>{_h(slide.get("layout") or slide.get("visual_layout") or "")}</small></a></li>'
        )
    first = slide_files[0].name if slide_files else ''
    lang = str(deck.get('language') or 'zh')
    return f'''<!DOCTYPE html>
<html lang="{_h(lang)}">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{_h(deck.get('title') or 'Visual Deck')}</title>
<style>
*{{box-sizing:border-box;}}
html,body{{margin:0;width:100%;height:100%;background:{theme['background']};color:{theme['foreground']};font-family:{theme['font_zh']};}}
body{{display:grid;grid-template-columns:300px 1fr;}}
aside{{padding:18px;background:{theme['surface']};border-right:1px solid {theme['border']};overflow:auto;}}
aside h1{{margin:0;font-size:20px;color:{theme['accent']};}}
aside p{{margin:8px 0 16px;color:{theme['muted']};font-size:13px;}}
aside ol{{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:8px;}}
aside li a{{display:grid;grid-template-columns:36px 1fr;gap:10px;text-decoration:none;background:{theme['surface_alt']};border:1px solid {theme['border']};border-radius:10px;padding:8px 10px;color:{theme['foreground']};}}
aside li a span{{font:800 14px {theme['font_en']};color:{theme['accent']};margin-top:2px;}}
aside li a p{{margin:0;font-size:13px;line-height:1.35;color:{theme['foreground']};}}
aside li a small{{grid-column:2/3;color:{theme['muted']};font-size:11px;}}
iframe{{width:100%;height:100%;border:0;background:#000;}}
</style>
</head>
<body>
<aside>
<h1>{_h(deck.get('title') or 'Visual Deck')}</h1>
<p>{_h(deck.get('subtitle') or '')}</p>
<ol>{''.join(rows)}</ol>
</aside>
<iframe name="slide-frame" src="{_h(first)}"></iframe>
</body>
</html>
'''


def create_html_deck_from_schema(
    deck_schema: Any,
    output_dir: str | Path | None = None,
    *,
    theme: Any = None,
    deck_name: str = 'visual_deck',
    persist_index: bool = True,
) -> Dict[str, Any]:
    if theme is None:
        schema_input = deck_schema
    elif isinstance(deck_schema, Mapping):
        schema_input = dict(deck_schema)
        schema_input['visual_theme'] = theme
    else:
        schema_input = {
            'title': 'Visual Deck',
            'slides': [{'type': 'content_bullets', 'title': 'Content', 'bullets': [str(deck_schema or '')]}],
            'visual_theme': theme,
        }
    deck = normalize_visual_deck_schema(schema_input)

    base_dir = Path(output_dir).expanduser().resolve() if output_dir else artifact_dir('html-deck-work') / _safe_name(deck_name)
    base_dir.mkdir(parents=True, exist_ok=True)

    slides = deck.get('slides') or []
    if not slides:
        return {
            'success': False,
            'error_message': 'no slides found after normalization',
            'deck_dir': str(base_dir),
            'slide_paths': [],
            'slide_count': 0,
            'warnings': ['deck_schema contains no slides'],
        }

    warnings: List[str] = []
    slide_paths: List[Path] = []
    layout_counter: Counter[str] = Counter()

    for idx, slide in enumerate(slides, start=1):
        layout = str(slide.get('layout') or slide.get('visual_layout') or 'content_bullets')
        layout_counter.update([layout])
        path = base_dir / f'slide-{idx:02d}.html'
        path.write_text(render_slide_html(slide, deck, idx, len(slides)), encoding='utf-8')
        slide_paths.append(path)

    index_path = base_dir / 'index.html'
    index_path.write_text(_index_html(deck, slide_paths), encoding='utf-8')

    manifest_path = base_dir / 'manifest.json'
    manifest_path.write_text(
        json.dumps(
            {
                'title': deck.get('title'),
                'subtitle': deck.get('subtitle'),
                'theme_used': deck.get('theme_used'),
                'palette_used': deck.get('palette_used'),
                'slide_count': len(slide_paths),
                'layout_summary': dict(layout_counter),
                'slide_paths': [str(p) for p in slide_paths],
                'created_at': datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    preview_url = static_file_url(index_path)
    saved_index = {}
    if persist_index:
        try:
            saved = save_artifact(index_path, kind='html-deck', filename=f'{_safe_name(deck_name)}.html')
            saved_index = saved.get('artifact') or saved
            preview_url = saved_index.get('file_url') or preview_url
        except Exception as exc:  # pragma: no cover
            warnings.append(f'index artifact save failed: {exc}')

    return {
        'success': True,
        'deck_schema': deck,
        'deck_dir': str(base_dir),
        'index_path': str(index_path),
        'index_url': static_file_url(index_path),
        'preview_url': preview_url,
        'local_path': str(index_path),
        'slide_paths': [str(p) for p in slide_paths],
        'slide_count': len(slide_paths),
        'theme_used': deck.get('theme_used') or (deck.get('visual_theme') or {}).get('name'),
        'palette_used': deck.get('palette_used'),
        'layout_summary': dict(layout_counter),
        'warnings': warnings,
        'saved_index': saved_index,
        'manifest_path': str(manifest_path),
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
