from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Tuple

_ALLOWED_SLIDE_TYPES = {
    'cover',
    'toc',
    'section_divider',
    'content',
    'content_bullets',
    'two_column',
    'comparison',
    'table',
    'summary',
}
_DEFAULT_THEME = {
    'name': 'lazyrag_default',
    'style': 'clean_academic',
    'primary': '1F2937',
    'secondary': '4B5563',
    'accent': '2563EB',
    'background': 'FFFFFF',
    'muted_background': 'F3F4F6',
    'font_face': 'Microsoft YaHei',
}
_HEX_RE = re.compile(r'^[0-9a-fA-F]{6}$')


def _parse_json_like(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    if isinstance(value, (bytes, bytearray)):
        value = value.decode('utf-8', errors='ignore')
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f'deck_schema must be a dict or valid JSON string: {exc}') from exc
        if not isinstance(parsed, dict):
            raise ValueError('deck_schema JSON must decode to an object')
        return parsed
    raise ValueError('deck_schema must be a dict or JSON string')


def _as_text(value: Any, default: str = '') -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _as_text_list(value: Any, *, max_items: int = 12) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [line.strip(' \t-•') for line in value.splitlines()]
    elif isinstance(value, Iterable) and not isinstance(value, (dict, bytes, bytearray)):
        candidates = [_as_text(item) for item in value]
    else:
        candidates = [_as_text(value)]
    return [item for item in candidates if item][:max_items]


def _normalize_hex(value: Any, fallback: str) -> str:
    text = _as_text(value, fallback).lstrip('#')
    return text.upper() if _HEX_RE.match(text) else fallback


def _normalize_theme(value: Any) -> Dict[str, Any]:
    theme = dict(_DEFAULT_THEME)
    if isinstance(value, str) and value.strip():
        theme['name'] = value.strip()
    elif isinstance(value, dict):
        for key in ('name', 'style', 'font_face'):
            if value.get(key):
                theme[key] = _as_text(value[key], str(theme[key]))
        for key in ('primary', 'secondary', 'accent', 'background', 'muted_background'):
            theme[key] = _normalize_hex(value.get(key), str(theme[key]))
    return theme


def _normalize_table(value: Any) -> Tuple[List[str], List[List[str]]]:
    if not isinstance(value, dict):
        return [], []
    headers = _as_text_list(value.get('headers'), max_items=8)
    rows: List[List[str]] = []
    raw_rows = value.get('rows') or []
    if isinstance(raw_rows, Iterable) and not isinstance(raw_rows, (str, bytes, bytearray, dict)):
        for row in raw_rows:
            if isinstance(row, dict):
                if headers:
                    rows.append([_as_text(row.get(h)) for h in headers])
                else:
                    rows.append([_as_text(v) for v in row.values()])
            elif isinstance(row, Iterable) and not isinstance(row, (str, bytes, bytearray)):
                rows.append([_as_text(cell) for cell in row][:8])
            else:
                rows.append([_as_text(row)])
            if len(rows) >= 12:
                break
    width = max([len(headers)] + [len(row) for row in rows] + [0])
    if width == 0:
        return [], []
    if not headers:
        headers = [f'Column {idx + 1}' for idx in range(width)]
    headers = headers[:width]
    normalized_rows = []
    for row in rows:
        normalized_rows.append((row + [''] * width)[:width])
    return headers, normalized_rows


def _infer_slide_type(raw: Dict[str, Any], index: int) -> str:
    raw_type = _as_text(raw.get('type') or raw.get('layout')).lower().replace('-', '_')
    aliases = {
        'title': 'cover',
        'divider': 'section_divider',
        'section': 'section_divider',
        'bullets': 'content_bullets',
        'content': 'content_bullets',
        'columns': 'two_column',
        '2col': 'two_column',
        'compare': 'comparison',
    }
    normalized = aliases.get(raw_type, raw_type)
    if normalized in _ALLOWED_SLIDE_TYPES:
        return normalized
    if index == 0:
        return 'cover'
    if raw.get('table'):
        return 'table'
    if raw.get('left') or raw.get('right') or raw.get('left_bullets') or raw.get('right_bullets'):
        return 'two_column'
    if raw.get('items') and len(_as_text_list(raw.get('items'))) <= 8:
        return 'content_bullets'
    return 'content_bullets'


def _normalize_slide(raw: Any, index: int) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {'title': f'Slide {index + 1}', 'bullets': _as_text_list(raw)}
    slide_type = _infer_slide_type(raw, index)
    title = _as_text(raw.get('title') or raw.get('heading'), f'Slide {index + 1}')
    subtitle = _as_text(raw.get('subtitle') or raw.get('sub_title'))
    bullets = _as_text_list(raw.get('bullets') or raw.get('items') or raw.get('points'), max_items=10)
    notes = _as_text(raw.get('notes') or raw.get('speaker_notes'))
    evidence_refs = _as_text_list(raw.get('evidence_refs') or raw.get('citations') or raw.get('sources'), max_items=8)

    normalized: Dict[str, Any] = {
        'type': slide_type,
        'title': title,
        'subtitle': subtitle,
        'bullets': bullets,
        'notes': notes,
        'evidence_refs': evidence_refs,
    }

    if slide_type in {'two_column', 'comparison'}:
        left = raw.get('left') if isinstance(raw.get('left'), dict) else {}
        right = raw.get('right') if isinstance(raw.get('right'), dict) else {}
        normalized['left'] = {
            'title': _as_text(raw.get('left_title') or left.get('title') or 'A'),
            'bullets': _as_text_list(raw.get('left_bullets') or left.get('bullets') or left.get('items'), max_items=8),
        }
        normalized['right'] = {
            'title': _as_text(raw.get('right_title') or right.get('title') or 'B'),
            'bullets': _as_text_list(raw.get('right_bullets') or right.get('bullets') or right.get('items'), max_items=8),
        }
        if not normalized['left']['bullets'] and bullets:
            midpoint = max(1, len(bullets) // 2)
            normalized['left']['bullets'] = bullets[:midpoint]
            normalized['right']['bullets'] = bullets[midpoint:]
    elif slide_type == 'table':
        headers, rows = _normalize_table(raw.get('table') or raw)
        normalized['table'] = {'headers': headers, 'rows': rows}
        if not bullets:
            normalized['bullets'] = _as_text_list(raw.get('caption') or raw.get('summary'), max_items=3)
    elif slide_type == 'toc':
        normalized['items'] = _as_text_list(raw.get('items') or raw.get('sections') or bullets, max_items=12)
    elif slide_type == 'summary':
        normalized['takeaways'] = _as_text_list(raw.get('takeaways') or bullets, max_items=6)

    return normalized


def normalize_deck_schema(deck_schema: Any) -> Dict[str, Any]:
    """Validate and normalize a loose deck schema produced by the agent.

    The function is intentionally permissive because LLM-produced schemas often
    use synonyms such as `items`, `points`, `layout`, or `citations`. The output
    is a stable schema consumed by the Python renderer and QA tools.
    """
    deck = _parse_json_like(deck_schema)
    title = _as_text(deck.get('title') or deck.get('deck_title'), 'LazyRAG Presentation')
    subtitle = _as_text(deck.get('subtitle') or deck.get('description'))
    language = _as_text(deck.get('language'), 'zh') or 'zh'
    audience = _as_text(deck.get('audience'), 'technical') or 'technical'
    theme = _normalize_theme(deck.get('theme'))

    raw_slides = deck.get('slides')
    if not isinstance(raw_slides, list) or not raw_slides:
        raw_slides = [
            {'type': 'cover', 'title': title, 'subtitle': subtitle},
            {'type': 'content_bullets', 'title': '主要内容', 'bullets': _as_text_list(deck.get('bullets') or deck.get('items'))},
        ]
    slides = [_normalize_slide(slide, idx) for idx, slide in enumerate(raw_slides[:60])]
    if slides and slides[0]['type'] != 'cover' and title:
        slides.insert(0, {'type': 'cover', 'title': title, 'subtitle': subtitle, 'bullets': [], 'notes': '', 'evidence_refs': []})

    return {
        'title': title,
        'subtitle': subtitle,
        'language': language,
        'audience': audience,
        'theme': theme,
        'slides': slides,
        'sources': deck.get('sources') if isinstance(deck.get('sources'), list) else [],
    }
