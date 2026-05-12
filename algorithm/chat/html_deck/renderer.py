from __future__ import annotations

import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from .artifact import artifact_dir, save_artifact, static_file_url
from .schema import normalize_visual_deck_schema, parse_deck_schema_input

"""Guizang-style visual renderer for the HTML deck route.

This renderer deliberately avoids the previous "one template + many color names"
problem.  It keeps one coherent design family and varies composition through
layout-frame, background, title treatment, and card-style tokens.  The HTML is
still deterministic and dependency-free so Codex can focus on the engineering
chain: Playwright, fonts, artifact URLs, and fallback policy.
"""


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
    return f'<div class="page-badge"><span>{page:02d}</span><em>{total:02d}</em></div>'


def _source_footer(slide: Mapping[str, Any]) -> str:
    refs = _as_list(slide.get('evidence_refs'))[:3]
    if not refs:
        return ''
    return f'<div class="sources">Sources · {_h(" · ".join(refs))}</div>'


def _accent_for(token: Any, theme: Mapping[str, Any]) -> str:
    text = str(token or '').lower()
    if text in {'danger', 'risk', 'red'}:
        return theme['danger']
    if text in {'success', 'green', 'good'}:
        return theme['success']
    if text in {'secondary', 'blue'}:
        return theme['secondary']
    return theme['accent']


def _background_art(theme: Mapping[str, Any], *, page: int = 1) -> str:
    accent = theme['accent']
    primary = theme['primary']
    secondary = theme['secondary']
    border = theme['border']
    fg = theme['foreground']
    variant = str(theme.get('background_variant') or 'ink_radial')
    mode = str(theme.get('mode') or 'dark')

    if variant in {'paper_grid', 'paper_warm'}:
        return f'''
        <svg class="bg-svg bg-paper" viewBox="0 0 960 540" aria-hidden="true">
          <defs>
            <pattern id="papergrid" width="36" height="36" patternUnits="userSpaceOnUse">
              <path d="M36 0H0V36" fill="none" stroke="{_rgba(border, 0.45)}" stroke-width="1"/>
            </pattern>
          </defs>
          <rect width="960" height="540" fill="url(#papergrid)" opacity="0.72"/>
          <circle cx="820" cy="80" r="120" fill="{_rgba(accent, 0.12)}"/>
          <circle cx="90" cy="460" r="95" fill="{_rgba(secondary, 0.12)}"/>
          <path d="M52 62H206" stroke="{_rgba(primary, 0.28)}" stroke-width="2"/>
          <path d="M720 456H892" stroke="{_rgba(primary, 0.22)}" stroke-width="2"/>
        </svg>
        '''
    if variant == 'blueprint_grid':
        return f'''
        <svg class="bg-svg bg-blueprint" viewBox="0 0 960 540" aria-hidden="true">
          <defs>
            <pattern id="smallgrid" width="24" height="24" patternUnits="userSpaceOnUse">
              <path d="M24 0H0V24" fill="none" stroke="{_rgba(primary, 0.16)}" stroke-width="1"/>
            </pattern>
            <pattern id="largegrid" width="96" height="96" patternUnits="userSpaceOnUse">
              <path d="M96 0H0V96" fill="none" stroke="{_rgba(primary, 0.24)}" stroke-width="1.5"/>
            </pattern>
          </defs>
          <rect width="960" height="540" fill="url(#smallgrid)"/>
          <rect width="960" height="540" fill="url(#largegrid)"/>
          <path d="M0 112H960M0 424H960M152 0V540M808 0V540" stroke="{_rgba(secondary, 0.13)}" stroke-width="3"/>
          <circle cx="820" cy="105" r="76" fill="none" stroke="{_rgba(accent, 0.22)}" stroke-width="14"/>
        </svg>
        '''
    if variant in {'aurora_mesh', 'botanic_mesh'}:
        return f'''
        <svg class="bg-svg bg-aurora" viewBox="0 0 960 540" aria-hidden="true">
          <defs>
            <radialGradient id="a" cx="78%" cy="18%" r="60%"><stop offset="0%" stop-color="{_rgba(accent, 0.45)}"/><stop offset="56%" stop-color="{_rgba(primary, 0.18)}"/><stop offset="100%" stop-color="rgba(0,0,0,0)"/></radialGradient>
            <radialGradient id="b" cx="12%" cy="86%" r="56%"><stop offset="0%" stop-color="{_rgba(secondary, 0.35)}"/><stop offset="100%" stop-color="rgba(0,0,0,0)"/></radialGradient>
            <pattern id="dots" width="34" height="34" patternUnits="userSpaceOnUse"><circle cx="17" cy="17" r="1.2" fill="{_rgba(fg, 0.18)}"/></pattern>
          </defs>
          <rect width="960" height="540" fill="url(#dots)" opacity="0.55"/>
          <rect width="960" height="540" fill="url(#a)"/>
          <rect width="960" height="540" fill="url(#b)"/>
          <path d="M720 64C820 118 860 180 906 286" fill="none" stroke="{_rgba(accent,0.24)}" stroke-width="2"/>
          <path d="M54 476C176 396 278 424 390 350" fill="none" stroke="{_rgba(secondary,0.24)}" stroke-width="2"/>
        </svg>
        '''
    if variant == 'executive_wash':
        return f'''
        <svg class="bg-svg bg-business" viewBox="0 0 960 540" aria-hidden="true">
          <rect x="0" y="0" width="960" height="540" fill="{_rgba(primary, 0.035)}"/>
          <path d="M0 0H960V92H0Z" fill="{_rgba(primary, 0.08)}"/>
          <path d="M0 446H960V540H0Z" fill="{_rgba(secondary, 0.09)}"/>
          <circle cx="836" cy="132" r="118" fill="none" stroke="{_rgba(accent, 0.20)}" stroke-width="18"/>
          <path d="M72 72H278M72 88H190" stroke="{_rgba(primary,0.28)}" stroke-width="2"/>
        </svg>
        '''
    if variant == 'noir_spotlight':
        return f'''
        <svg class="bg-svg bg-noir" viewBox="0 0 960 540" aria-hidden="true">
          <defs><radialGradient id="spot" cx="50%" cy="46%" r="58%"><stop offset="0%" stop-color="{_rgba(accent, 0.16)}"/><stop offset="62%" stop-color="{_rgba(primary, 0.08)}"/><stop offset="100%" stop-color="rgba(0,0,0,0)"/></radialGradient></defs>
          <rect width="960" height="540" fill="url(#spot)"/>
          <path d="M64 52H896M64 488H896" stroke="{_rgba(accent,0.26)}" stroke-width="1.5"/>
          <path d="M84 72V198M876 342V468" stroke="{_rgba(accent,0.26)}" stroke-width="1.5"/>
          <circle cx="480" cy="270" r="220" fill="none" stroke="{_rgba(accent,0.10)}" stroke-width="1"/>
        </svg>
        '''
    # ink_radial default
    return f'''
    <svg class="bg-svg bg-ink" viewBox="0 0 960 540" aria-hidden="true">
      <defs>
        <radialGradient id="ink" cx="72%" cy="24%" r="65%"><stop offset="0%" stop-color="{_rgba(accent, 0.20)}"/><stop offset="58%" stop-color="{_rgba(secondary, 0.10)}"/><stop offset="100%" stop-color="rgba(0,0,0,0)"/></radialGradient>
        <pattern id="grain" width="28" height="28" patternUnits="userSpaceOnUse"><circle cx="6" cy="8" r="0.8" fill="{_rgba(fg, 0.13)}"/><circle cx="22" cy="19" r="0.7" fill="{_rgba(accent, 0.10)}"/></pattern>
      </defs>
      <rect width="960" height="540" fill="url(#grain)" opacity="0.66"/>
      <rect width="960" height="540" fill="url(#ink)"/>
      <circle cx="104" cy="448" r="96" fill="{_rgba(accent, 0.09)}"/>
      <circle cx="104" cy="448" r="62" fill="none" stroke="{_rgba(accent, 0.16)}" stroke-width="2"/>
      <path d="M0 0 L74 0 L0 74 Z" fill="{_rgba(accent, 0.13)}"/>
      <path d="M960 540 L886 540 L960 466 Z" fill="{_rgba(accent, 0.13)}"/>
    </svg>
    '''


def _kicker(slide: Mapping[str, Any], page: int) -> str:
    raw = slide.get('kicker') or slide.get('section_number') or f'{page:02d}'
    return _trim(raw, 18)


def _layout_cover(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    title = _trim(slide.get('title') or deck.get('title'), 68)
    subtitle = _trim(slide.get('subtitle') or deck.get('subtitle'), 118)
    highlight = _trim(slide.get('highlight') or deck.get('audience') or '', 36)
    date_text = _trim(slide.get('date') or datetime.now(timezone.utc).strftime('%Y.%m'), 20)
    theme = deck['visual_theme']
    return f'''
    {_background_art(theme, page=page)}
    <div class="cover-rail"><b>{_h(_kicker(slide, page))}</b><span></span><em>{_h(date_text)}</em></div>
    <section class="cover-stage">
      <div class="cover-kicker">{_h(highlight or 'VISUAL BRIEFING')}</div>
      <h1>{_h(title)}</h1>
      <p>{_h(subtitle)}</p>
    </section>
    <div class="cover-orbit"><span></span><span></span><span></span></div>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_toc(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    items = _as_list(slide.get('items') or slide.get('bullets'))
    if not items:
        items = [s.get('title') for s in deck.get('slides', [])[1:] if s.get('title')]
    rows = ''.join(
        f'<li><b>{idx:02d}</b><span></span><p>{_h(_trim(item, 54))}</p></li>'
        for idx, item in enumerate(items[:8], start=1)
    )
    return f'''
    {_background_art(deck['visual_theme'], page=page)}
    <aside class="toc-aside"><small>INDEX</small><h2>{_h(slide.get('title') or ('目录' if deck.get('language') == 'zh' else 'Contents'))}</h2></aside>
    <ol class="toc-list">{rows}</ol>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_section(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    section_no = _trim(slide.get('section_number') or f'{page:02d}', 8)
    return f'''
    {_background_art(deck['visual_theme'], page=page)}
    <section class="section-poster">
      <span class="section-ghost">{_h(section_no)}</span>
      <div class="section-rule"></div>
      <h2>{_h(_trim(slide.get('title'), 48))}</h2>
      <p>{_h(_trim(slide.get('subtitle'), 90))}</p>
    </section>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_metric_cards(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    theme = deck['visual_theme']
    metrics = slide.get('metrics') if isinstance(slide.get('metrics'), list) else []
    metrics = [m for m in metrics if isinstance(m, Mapping)][:4]
    if not metrics:
        metrics = [{'label': '', 'value': '', 'description': '[Missing metric content]'}]
    hero = metrics[0]
    small_cards = ''.join(
        f'<article><small>{_h(_trim(item.get("label"), 22))}</small><strong>{_h(_trim(item.get("value"), 18))}</strong><p>{_h(_trim(item.get("description"), 58))}</p></article>'
        for item in metrics[1:4]
    )
    bullets = ''.join(f'<li>{_h(_trim(x, 72))}</li>' for x in _as_list(slide.get('bullets'))[:3])
    return f'''
    {_background_art(theme, page=page)}
    <header class="slide-header"><small>{_h(_kicker(slide, page))}</small><h2>{_h(_trim(slide.get('title'), 54))}</h2></header>
    <section class="metric-poster">
      <div class="metric-hero"><small>{_h(_trim(hero.get('label'), 24))}</small><strong>{_h(_trim(hero.get('value'), 18))}</strong><p>{_h(_trim(hero.get('description'), 80))}</p></div>
      <div class="metric-stack">{small_cards}</div>
      <div class="metric-note"><b>{_h(_trim(slide.get('subtitle') or '关键判断', 36))}</b><ul>{bullets}</ul></div>
    </section>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_challenge_cards(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    cards = slide.get('cards') if isinstance(slide.get('cards'), list) and slide.get('cards') else []
    if not cards:
        cards = [{'title': '', 'body': txt, 'accent': 'primary'} for txt in _as_list(slide.get('bullets'))[:6]]
    grid = []
    for idx, item in enumerate(cards[:6], start=1):
        color = _accent_for(item.get('accent'), deck['visual_theme']) if isinstance(item, Mapping) else deck['visual_theme']['accent']
        grid.append(
            f'<article style="--card-accent:{_h(color)}"><small>{idx:02d}</small><h4>{_h(_trim(item.get("title") if isinstance(item, Mapping) else "", 28))}</h4><p>{_h(_trim(item.get("body") if isinstance(item, Mapping) else item, 96))}</p></article>'
        )
    return f'''
    {_background_art(deck['visual_theme'], page=page)}
    <header class="slide-header wide"><small>{_h(_kicker(slide, page))}</small><h2>{_h(_trim(slide.get('title'), 54))}</h2><p>{_h(_trim(slide.get('subtitle'), 80))}</p></header>
    <section class="risk-grid">{''.join(grid)}</section>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_content_bullets(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    bullets = _as_list(slide.get('bullets') or slide.get('items'))[:6]
    rows = ''.join(f'<li><b>{idx:02d}</b><p>{_h(_trim(item, 96))}</p></li>' for idx, item in enumerate(bullets, start=1))
    return f'''
    {_background_art(deck['visual_theme'], page=page)}
    <section class="content-magazine">
      <div class="content-title"><small>{_h(_kicker(slide, page))}</small><h2>{_h(_trim(slide.get('title'), 52))}</h2><p>{_h(_trim(slide.get('subtitle'), 118))}</p></div>
      <ul class="content-list">{rows}</ul>
    </section>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_two_column(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    left = slide.get('left') if isinstance(slide.get('left'), Mapping) else {}
    right = slide.get('right') if isinstance(slide.get('right'), Mapping) else {}
    if not left or not right:
        columns = slide.get('columns') if isinstance(slide.get('columns'), list) else []
        if len(columns) >= 2:
            left = columns[0] if isinstance(columns[0], Mapping) else {'title': '', 'bullets': _as_list(columns[0])}
            right = columns[1] if isinstance(columns[1], Mapping) else {'title': '', 'bullets': _as_list(columns[1])}
    def _col(item: Mapping[str, Any], idx: int) -> str:
        bullets = ''.join(f'<li>{_h(_trim(x, 56))}</li>' for x in _as_list(item.get('bullets') or item.get('items'))[:5])
        return f'<article><span>{idx:02d}</span><h4>{_h(_trim(item.get("title") or "", 28))}</h4><ul>{bullets}</ul></article>'
    return f'''
    {_background_art(deck['visual_theme'], page=page)}
    <header class="slide-header"><small>{_h(_kicker(slide, page))}</small><h2>{_h(_trim(slide.get('title'), 54))}</h2></header>
    <section class="duo-board">{_col(left, 1)}<div class="duo-divider">VS</div>{_col(right, 2)}</section>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_comparison(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    rows = slide.get('rows') if isinstance(slide.get('rows'), list) else []
    headers = _as_list(slide.get('headers'))
    if headers and rows:
        body_rows = []
        for row in rows[:6]:
            cells = row if isinstance(row, list) else [row]
            cells = list(cells[: len(headers)])
            while len(cells) < len(headers):
                cells.append('')
            body_rows.append('<tr>' + ''.join(f'<td>{_h(_trim(c, 44))}</td>' for c in cells) + '</tr>')
        head = ''.join(f'<th>{_h(_trim(h, 20))}</th>' for h in headers[:4])
        matrix = f'<table class="compare-table"><thead><tr>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table>'
    else:
        left_items = ''.join(f'<li>{_h(_trim(x, 54))}</li>' for x in _as_list(slide.get('left_items'))[:5])
        right_items = ''.join(f'<li>{_h(_trim(x, 54))}</li>' for x in _as_list(slide.get('right_items'))[:5])
        matrix = f'<div class="compare-panels"><article><h4>{_h(_trim(slide.get("left_title") or "", 24))}</h4><ul>{left_items}</ul></article><span>VS</span><article><h4>{_h(_trim(slide.get("right_title") or "", 24))}</h4><ul>{right_items}</ul></article></div>'
    return f'''
    {_background_art(deck['visual_theme'], page=page)}
    <header class="slide-header"><small>{_h(_kicker(slide, page))}</small><h2>{_h(_trim(slide.get('title'), 54))}</h2></header>
    <section class="comparison-board">{matrix}</section>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_table(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    headers = _as_list(slide.get('headers')) or ['维度', '现状', '建议']
    rows = slide.get('rows') if isinstance(slide.get('rows'), list) else []
    head = ''.join(f'<th>{_h(_trim(h, 18))}</th>' for h in headers[:6])
    body_rows = []
    for row in rows[:8]:
        cells = row if isinstance(row, list) else [row]
        cells = list(cells[: len(headers)])
        while len(cells) < len(headers):
            cells.append('')
        body_rows.append('<tr>' + ''.join(f'<td>{_h(_trim(c, 36))}</td>' for c in cells) + '</tr>')
    return f'''
    {_background_art(deck['visual_theme'], page=page)}
    <header class="slide-header"><small>{_h(_kicker(slide, page))}</small><h2>{_h(_trim(slide.get('title'), 54))}</h2></header>
    <section class="table-spread"><table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></section>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_summary(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    bullets = _as_list(slide.get('bullets') or slide.get('items'))[:5]
    cards = ''.join(f'<article><b>{idx:02d}</b><p>{_h(_trim(item, 84))}</p></article>' for idx, item in enumerate(bullets, start=1))
    return f'''
    {_background_art(deck['visual_theme'], page=page)}
    <section class="summary-poster"><small>TAKEAWAYS</small><h2>{_h(_trim(slide.get('title') or '总结与行动建议', 54))}</h2><div>{cards}</div></section>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_quote(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    quote = _trim(slide.get('quote') or slide.get('body') or slide.get('subtitle') or slide.get('title'), 120)
    author = _trim(slide.get('author') or slide.get('source') or '', 50)
    return f'''
    {_background_art(deck['visual_theme'], page=page)}
    <section class="quote-spread"><h2 class="sr-title">{_h(_trim(slide.get('title') or 'Quote', 54))}</h2><span>“</span><blockquote>{_h(quote)}</blockquote><p>{_h(author)}</p></section>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_process(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    items = _as_list(slide.get('steps') or slide.get('bullets') or slide.get('items'))[:5]
    steps = ''.join(f'<article><b>{idx:02d}</b><p>{_h(_trim(item, 58))}</p></article>' for idx, item in enumerate(items, start=1))
    return f'''
    {_background_art(deck['visual_theme'], page=page)}
    <header class="slide-header"><small>{_h(_kicker(slide, page))}</small><h2>{_h(_trim(slide.get('title'), 54))}</h2></header>
    <section class="process-ribbon">{steps}</section>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_timeline(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    items = slide.get('items') if isinstance(slide.get('items'), list) else []
    if not items:
        items = [{'time': f'阶段 {i+1}', 'title': item, 'desc': ''} for i, item in enumerate(_as_list(slide.get('bullets'))[:5])]
    rows = []
    for idx, item in enumerate(items[:5], start=1):
        if isinstance(item, Mapping):
            rows.append(f'<article><b>{_h(_trim(item.get("time") or idx, 16))}</b><h4>{_h(_trim(item.get("title"), 30))}</h4><p>{_h(_trim(item.get("desc") or item.get("description"), 72))}</p></article>')
        else:
            rows.append(f'<article><b>{idx:02d}</b><h4>{_h(_trim(item, 30))}</h4><p></p></article>')
    return f'''
    {_background_art(deck['visual_theme'], page=page)}
    <header class="slide-header"><small>{_h(_kicker(slide, page))}</small><h2>{_h(_trim(slide.get('title'), 54))}</h2></header>
    <section class="timeline-lane">{''.join(rows)}</section>
    {_source_footer(slide)}
    {_slide_badge(page, total)}
    '''


def _layout_references(slide: Mapping[str, Any], deck: Mapping[str, Any], page: int, total: int) -> str:
    refs = _as_list(slide.get('items') or slide.get('bullets') or slide.get('evidence_refs'))[:10]
    rows = ''.join(f'<li>{_h(_trim(ref, 118))}</li>' for ref in refs)
    return f'''
    {_background_art(deck['visual_theme'], page=page)}
    <header class="slide-header"><small>{_h(_kicker(slide, page))}</small><h2>{_h(_trim(slide.get('title') or '资料来源', 54))}</h2></header>
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
    width = int(theme.get('canvas_width') or 960)
    height = int(theme.get('canvas_height') or 540)
    bg = theme.get('canvas') or theme['background']
    surface = theme['surface']
    surface_alt = theme['surface_alt']
    fg = theme['foreground']
    muted = theme['muted']
    accent = theme['accent']
    primary = theme['primary']
    secondary = theme['secondary']
    border = theme['border']
    radius = int(theme.get('radius') or 16)
    shadow = theme['shadow']
    mode = theme.get('mode')
    title_font = theme['font_serif'] if 'serif' in str(theme.get('title_treatment')) else theme['font_zh']
    body_font = theme['font_zh']
    card_outline = _rgba(accent, 0.18)
    frame_color = _rgba(accent, 0.36)
    return f'''
    :root {{
      --bg: {bg}; --surface: {surface}; --surface-alt: {surface_alt}; --fg: {fg}; --muted: {muted};
      --accent: {accent}; --primary: {primary}; --secondary: {secondary}; --border: {border};
      --danger: {theme['danger']}; --success: {theme['success']}; --shadow: {shadow}; --radius: {radius}px;
      --frame: {frame_color}; --card-outline: {card_outline};
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin:0; padding:0; width:100%; height:100%; overflow:hidden; display:flex; align-items:center; justify-content:center; background:{theme['background']}; }}
    body {{ font-family:{body_font}; color:var(--fg); }}
    .slide-content {{ width:{width}px; height:{height}px; position:relative; overflow:hidden; flex-shrink:0; background:var(--bg); transform-origin:center center; }}
    .slide-content::before {{ content:""; position:absolute; inset:22px; border:1px solid var(--frame); pointer-events:none; z-index:1; }}
    .slide-content::after {{ content:""; position:absolute; left:32px; bottom:32px; width:110px; height:2px; background:linear-gradient(90deg,var(--accent),transparent); z-index:2; }}
    .bg-svg {{ position:absolute; inset:0; width:100%; height:100%; pointer-events:none; z-index:0; }}
    h1,h2,h3,h4,p,ul,ol,li,blockquote {{ margin-top:0; }}
    .sr-title {{ position:absolute; left:-9999px; width:1px; height:1px; overflow:hidden; }}
    .page-badge {{ position:absolute; right:34px; bottom:26px; z-index:5; display:grid; grid-template-columns:1fr; place-items:center; width:46px; height:46px; border-radius:999px; background:var(--accent); color:var(--bg); box-shadow:var(--shadow); font-family:{theme['font_en']}; }}
    .page-badge span {{ font-size:15px; font-weight:900; line-height:1; }}
    .page-badge em {{ font-size:9px; font-style:normal; opacity:.72; line-height:1; margin-top:-6px; }}
    .sources {{ position:absolute; left:42px; bottom:24px; width:720px; z-index:5; color:var(--muted); font-size:10px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; opacity:.82; }}
    .slide-header {{ position:absolute; left:52px; top:38px; width:730px; z-index:3; display:grid; grid-template-columns:72px 1fr; column-gap:18px; align-items:start; }}
    .slide-header.wide {{ width:820px; }}
    .slide-header small {{ display:block; color:var(--accent); font:900 18px {theme['font_en']}; letter-spacing:.14em; border-top:3px solid var(--accent); padding-top:8px; }}
    .slide-header h2 {{ margin:0; font-family:{title_font}; font-size:36px; line-height:1.16; letter-spacing:.02em; }}
    .slide-header p {{ grid-column:2/3; margin:8px 0 0; color:var(--muted); font-size:15px; }}

    .cover-rail {{ position:absolute; left:42px; top:42px; bottom:42px; z-index:3; display:flex; flex-direction:column; align-items:center; gap:16px; color:var(--accent); font-family:{theme['font_en']}; }}
    .cover-rail b {{ writing-mode:vertical-rl; letter-spacing:.2em; font-size:13px; }}
    .cover-rail span {{ flex:1; width:2px; background:linear-gradient(var(--accent),transparent); opacity:.65; }}
    .cover-rail em {{ writing-mode:vertical-rl; font-style:normal; color:var(--muted); font-size:12px; }}
    .cover-stage {{ position:absolute; left:106px; top:116px; width:650px; z-index:3; }}
    .cover-kicker {{ color:var(--accent); font:800 13px {theme['font_en']}; letter-spacing:.22em; margin-bottom:18px; text-transform:uppercase; }}
    .cover-stage h1 {{ margin:0; font-family:{title_font}; font-size:54px; line-height:1.16; letter-spacing:.01em; max-width:760px; }}
    .cover-stage h1::first-letter {{ color:var(--accent); }}
    .cover-stage p {{ margin:28px 0 0; max-width:600px; color:var(--muted); font-size:23px; line-height:1.48; letter-spacing:.04em; }}
    .cover-orbit {{ position:absolute; right:86px; top:126px; width:170px; height:250px; z-index:2; }}
    .cover-orbit span {{ position:absolute; border:1px solid var(--frame); border-radius:999px; }}
    .cover-orbit span:nth-child(1) {{ inset:0 18px 80px 18px; }}
    .cover-orbit span:nth-child(2) {{ inset:74px 0 14px 0; border-color:{_rgba(secondary, 0.34)}; }}
    .cover-orbit span:nth-child(3) {{ left:68px; top:92px; width:32px; height:32px; background:var(--accent); border:0; box-shadow:0 0 40px {_rgba(accent, .55)}; }}

    .toc-aside {{ position:absolute; left:52px; top:56px; width:226px; height:388px; padding:30px 22px; background:var(--surface); border:1px solid var(--border); box-shadow:var(--shadow); z-index:3; }}
    .toc-aside small {{ color:var(--accent); font:900 12px {theme['font_en']}; letter-spacing:.28em; }}
    .toc-aside h2 {{ margin:34px 0 0; font-family:{title_font}; font-size:52px; line-height:1; }}
    .toc-list {{ position:absolute; left:318px; top:72px; width:566px; margin:0; padding:0; list-style:none; z-index:3; }}
    .toc-list li {{ display:grid; grid-template-columns:52px 1fr; gap:18px; align-items:center; margin:0 0 16px; padding:12px 0; border-bottom:1px solid var(--border); }}
    .toc-list b {{ color:var(--accent); font:900 25px {theme['font_en']}; }}
    .toc-list span {{ grid-column:1/2; grid-row:2; width:32px; height:2px; background:var(--accent); opacity:.55; }}
    .toc-list p {{ grid-column:2/3; grid-row:1/3; margin:0; font-size:23px; line-height:1.34; }}

    .section-poster {{ position:absolute; inset:0; z-index:3; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; }}
    .section-ghost {{ position:absolute; font:900 170px {theme['font_en']}; color:{_rgba(accent, .16)}; transform:translateY(-48px); letter-spacing:-.08em; }}
    .section-rule {{ width:180px; height:4px; background:var(--accent); margin:80px 0 22px; }}
    .section-poster h2 {{ margin:0; font-family:{title_font}; font-size:50px; line-height:1.15; z-index:2; }}
    .section-poster p {{ margin:18px 0 0; color:var(--muted); font-size:22px; z-index:2; }}

    .metric-poster {{ position:absolute; left:48px; top:108px; width:864px; height:354px; z-index:3; display:grid; grid-template-columns:1.08fr 1fr; grid-template-rows:1fr 112px; gap:16px; }}
    .metric-hero {{ grid-row:1/3; padding:24px; background:linear-gradient(135deg,var(--surface),var(--surface-alt)); border:1px solid var(--border); box-shadow:var(--shadow); border-radius:var(--radius); position:relative; overflow:hidden; }}
    .metric-hero::after {{ content:""; position:absolute; right:-36px; bottom:-48px; width:180px; height:180px; border:22px solid var(--card-outline); border-radius:999px; }}
    .metric-hero small {{ color:var(--muted); font-size:16px; }}
    .metric-hero strong {{ display:block; margin:28px 0 12px; font:900 70px {theme['font_en']}; color:var(--accent); letter-spacing:-.04em; }}
    .metric-hero p {{ width:72%; color:var(--muted); font-size:17px; line-height:1.5; }}
    .metric-stack {{ display:grid; grid-template-columns:repeat(2,1fr); gap:14px; }}
    .metric-stack article, .metric-note {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:16px; box-shadow:var(--shadow); }}
    .metric-stack small {{ color:var(--muted); font-size:12px; }}
    .metric-stack strong {{ display:block; color:var(--accent); font:900 34px {theme['font_en']}; margin-top:8px; }}
    .metric-stack p {{ color:var(--muted); font-size:12px; line-height:1.35; margin:8px 0 0; }}
    .metric-note {{ grid-column:2/3; }}
    .metric-note b {{ color:var(--fg); font-size:16px; }}
    .metric-note ul {{ margin:8px 0 0; padding-left:18px; color:var(--muted); font-size:13px; line-height:1.36; }}

    .risk-grid {{ position:absolute; left:48px; top:136px; width:864px; display:grid; grid-template-columns:repeat(2,1fr); gap:16px; z-index:3; }}
    .risk-grid article {{ min-height:136px; background:var(--surface); border:1px solid var(--border); border-left:6px solid var(--card-accent,var(--accent)); border-radius:var(--radius); padding:18px 20px; box-shadow:var(--shadow); position:relative; overflow:hidden; }}
    .risk-grid article::after {{ content:""; position:absolute; right:-24px; bottom:-30px; width:90px; height:90px; border-radius:999px; background:var(--card-accent,var(--accent)); opacity:.10; }}
    .risk-grid small {{ color:var(--card-accent,var(--accent)); font:900 14px {theme['font_en']}; letter-spacing:.12em; }}
    .risk-grid h4 {{ margin:10px 0 0; font-size:20px; }}
    .risk-grid p {{ margin:9px 0 0; color:var(--muted); font-size:14px; line-height:1.46; }}

    .content-magazine {{ position:absolute; left:46px; top:70px; width:868px; height:398px; z-index:3; display:grid; grid-template-columns:314px 1fr; gap:24px; }}
    .content-title {{ padding:28px 24px; background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); box-shadow:var(--shadow); }}
    .content-title small {{ color:var(--accent); font:900 14px {theme['font_en']}; letter-spacing:.18em; }}
    .content-title h2 {{ margin:32px 0 0; font-family:{title_font}; font-size:38px; line-height:1.18; }}
    .content-title p {{ margin:18px 0 0; color:var(--muted); font-size:15px; line-height:1.54; }}
    .content-list {{ margin:0; padding:0; list-style:none; display:grid; gap:12px; }}
    .content-list li {{ display:grid; grid-template-columns:50px 1fr; gap:14px; align-items:start; padding:13px 16px; background:var(--surface); border:1px solid var(--border); border-radius:calc(var(--radius) - 4px); box-shadow:var(--shadow); }}
    .content-list b {{ color:var(--accent); font:900 19px {theme['font_en']}; }}
    .content-list p {{ margin:0; color:var(--muted); font-size:16px; line-height:1.46; }}

    .duo-board {{ position:absolute; left:48px; top:120px; width:864px; height:316px; display:grid; grid-template-columns:1fr 70px 1fr; gap:14px; z-index:3; align-items:stretch; }}
    .duo-board article {{ padding:22px; background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); box-shadow:var(--shadow); }}
    .duo-board article:nth-child(3) {{ background:var(--surface-alt); }}
    .duo-board span {{ color:var(--accent); font:900 26px {theme['font_en']}; }}
    .duo-board h4 {{ margin:20px 0 0; font-size:26px; }}
    .duo-board ul {{ margin:18px 0 0; padding-left:20px; color:var(--muted); }}
    .duo-board li {{ margin:10px 0; font-size:16px; line-height:1.42; }}
    .duo-divider {{ display:grid; place-items:center; color:var(--accent); font:900 20px {theme['font_en']}; }}

    .comparison-board {{ position:absolute; left:48px; top:116px; width:864px; z-index:3; }}
    .compare-table, .table-spread table {{ width:100%; border-collapse:separate; border-spacing:0; overflow:hidden; border-radius:var(--radius); box-shadow:var(--shadow); border:1px solid var(--border); }}
    .compare-table th, .table-spread th {{ background:var(--accent); color:var(--bg); padding:12px 14px; font-size:14px; text-align:left; }}
    .compare-table td, .table-spread td {{ background:var(--surface); color:var(--muted); padding:12px 14px; border-bottom:1px solid var(--border); font-size:13px; line-height:1.38; }}
    .compare-panels {{ display:grid; grid-template-columns:1fr 70px 1fr; gap:14px; align-items:stretch; }}
    .compare-panels article {{ min-height:278px; padding:22px; background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); box-shadow:var(--shadow); }}
    .compare-panels > span {{ display:grid; place-items:center; color:var(--accent); font:900 20px {theme['font_en']}; }}
    .compare-panels h4 {{ margin:0; font-size:26px; color:var(--accent); }}
    .compare-panels ul {{ margin:18px 0 0; padding-left:20px; color:var(--muted); }}
    .compare-panels li {{ margin:10px 0; font-size:15px; }}

    .table-spread {{ position:absolute; left:48px; top:118px; width:864px; z-index:3; }}
    .table-spread table {{ font-size:13px; }}

    .summary-poster {{ position:absolute; left:54px; top:64px; width:852px; height:398px; z-index:3; display:grid; grid-template-columns:300px 1fr; gap:24px; align-items:start; }}
    .summary-poster small {{ color:var(--accent); font:900 13px {theme['font_en']}; letter-spacing:.24em; }}
    .summary-poster h2 {{ grid-column:1/2; margin:38px 0 0; font-family:{title_font}; font-size:42px; line-height:1.15; }}
    .summary-poster > div {{ grid-column:2/3; grid-row:1/3; display:grid; gap:12px; }}
    .summary-poster article {{ display:grid; grid-template-columns:48px 1fr; gap:14px; align-items:center; min-height:66px; background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:12px 15px; box-shadow:var(--shadow); }}
    .summary-poster article b {{ color:var(--accent); font:900 20px {theme['font_en']}; }}
    .summary-poster article p {{ margin:0; color:var(--muted); font-size:15px; line-height:1.42; }}

    .quote-spread {{ position:absolute; left:80px; top:94px; width:800px; min-height:330px; z-index:3; padding:36px 44px; background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); box-shadow:var(--shadow); }}
    .quote-spread span {{ display:block; color:var(--accent); font:900 96px {theme['font_serif']}; line-height:.65; }}
    .quote-spread blockquote {{ margin:18px 0 0; font-family:{title_font}; font-size:36px; line-height:1.32; }}
    .quote-spread p {{ margin:26px 0 0; color:var(--muted); text-align:right; font-size:16px; }}

    .process-ribbon {{ position:absolute; left:48px; top:134px; width:864px; display:grid; grid-template-columns:repeat(4,1fr); gap:14px; z-index:3; }}
    .process-ribbon article {{ min-height:210px; padding:18px; background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); box-shadow:var(--shadow); position:relative; }}
    .process-ribbon article:not(:last-child)::after {{ content:""; position:absolute; right:-20px; top:50%; width:24px; height:2px; background:var(--accent); }}
    .process-ribbon b {{ display:inline-block; background:var(--accent); color:var(--bg); border-radius:999px; padding:5px 10px; font:900 13px {theme['font_en']}; }}
    .process-ribbon p {{ margin:46px 0 0; color:var(--muted); font-size:17px; line-height:1.44; }}

    .timeline-lane {{ position:absolute; left:70px; top:120px; width:820px; display:grid; gap:10px; z-index:3; }}
    .timeline-lane article {{ display:grid; grid-template-columns:92px 220px 1fr; gap:14px; align-items:center; background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:12px 16px; box-shadow:var(--shadow); }}
    .timeline-lane b {{ color:var(--accent); font:900 16px {theme['font_en']}; }}
    .timeline-lane h4 {{ margin:0; font-size:19px; }}
    .timeline-lane p {{ margin:0; color:var(--muted); font-size:13px; line-height:1.36; }}

    .reference-list {{ position:absolute; left:74px; top:120px; width:820px; z-index:3; margin:0; padding-left:24px; color:var(--muted); }}
    .reference-list li {{ margin:9px 0; font-size:14px; line-height:1.45; }}

    .mode-light .page-badge {{ color:#fff; }}
    .style-guizang_paper .slide-content::before, .style-guizang_business .slide-content::before {{ inset:18px; }}
    .style-guizang_paper .cover-stage h1, .style-guizang_paper .section-poster h2, .style-guizang_paper .quote-spread blockquote {{ letter-spacing:-.02em; }}
    .style-guizang_blueprint .slide-content::before {{ border-style:dashed; }}
    .style-guizang_blueprint .metric-hero::after {{ border-radius:12px; transform:rotate(12deg); }}
    .style-guizang_aurora .cover-orbit span:nth-child(3), .style-guizang_violet .cover-orbit span:nth-child(3) {{ box-shadow:0 0 48px {_rgba(accent,.72)}; }}
    '''


def _scale_script(width: int, height: int) -> str:
    return f'''
    function scaleSlide() {{
      const slide = document.querySelector('.slide-content');
      if (!slide) return;
      const params = new URLSearchParams(window.location.search || '');
      if (params.get('screenshot') === '1') {{
        slide.style.transform = 'none';
        slide.style.transformOrigin = 'center center';
        return;
      }}
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
    style_class = f"mode-{theme.get('mode','dark')} style-{theme.get('style_tag','guizang_ink')} frame-{theme.get('layout_frame','magazine_frame')} card-{theme.get('card_style','ink_card')}"
    return f'''<!DOCTYPE html>
<html lang="{_h(deck.get('language') or 'zh')}">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{_h(title)}</title>
  <style>{_base_css(theme)}</style>
  <script>{_scale_script(width, height)}</script>
</head>
<body class="{_h(style_class)}">
  <div class="slide-content" data-layout="{_h(layout)}">{body}</div>
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
iframe{{width:100%;height:100%;border:0;background:{theme['background']};}}
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
    try:
        schema_input = parse_deck_schema_input(deck_schema)
    except ValueError as exc:
        return {
            'success': False,
            'error_code': 'schema_parse_failed',
            'error_message': str(exc),
            'warnings': ['deck_schema must be a structured object with slides list'],
            'slide_paths': [],
            'slide_count': 0,
        }
    if theme is not None:
        schema_input = dict(schema_input)
        schema_input['visual_theme'] = theme
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
                'visual_family': 'guizang_style',
                'theme_tokens': {
                    key: deck.get('visual_theme', {}).get(key)
                    for key in ('layout_frame', 'background_variant', 'title_treatment', 'card_style', 'ornament', 'density')
                },
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
        'visual_family': 'guizang_style',
        'theme_tokens': {
            key: deck.get('visual_theme', {}).get(key)
            for key in ('layout_frame', 'background_variant', 'title_treatment', 'card_style', 'ornament', 'density')
        },
        'layout_summary': dict(layout_counter),
        'warnings': warnings,
        'saved_index': saved_index,
        'manifest_path': str(manifest_path),
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
