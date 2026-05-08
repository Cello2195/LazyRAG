from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Tuple

from .themes import SUPPORTED_THEMES, resolve_theme

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
    'references',
}
_ALLOWED_AUDIENCES = {'academic', 'business', 'technical', 'general'}
_PLACEHOLDER_RE = re.compile(r'(lorem ipsum|placeholder|todo|tbd|xxxx|待补充)', re.IGNORECASE)
_MAX_SLIDES = 80
_MAX_BULLETS_PER_SLIDE = 8
_MAX_BULLET_LEN = 180
_MAX_TEXT_LEN = 240
_MAX_TABLE_ROWS = 20
_MAX_TABLE_COLS = 8


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


def _truncate(value: str, max_len: int = _MAX_TEXT_LEN) -> str:
    text = _as_text(value)
    if len(text) <= max_len:
        return text
    return f'{text[: max_len - 1]}…'


def _clean_placeholder(value: str, fallback: str = '') -> str:
    text = _as_text(value)
    if not text:
        return fallback
    if _PLACEHOLDER_RE.search(text):
        return fallback
    return text


def _split_text_like_list(value: str) -> List[str]:
    text = _as_text(value)
    if not text:
        return []
    if '\n' in text:
        items = [part.strip(' \t-•') for part in text.splitlines()]
    else:
        parts = re.split(r'[;；。]+', text)
        items = [part.strip(' \t-•') for part in parts]
    return [item for item in items if item]


def _as_text_list(value: Any, *, max_items: int = 12, max_len: int = _MAX_BULLET_LEN) -> List[str]:
    candidates: List[str] = []
    if value is None:
        candidates = []
    elif isinstance(value, str):
        candidates = _split_text_like_list(value)
    elif isinstance(value, Iterable) and not isinstance(value, (dict, bytes, bytearray)):
        for item in value:
            candidates.extend(_split_text_like_list(_as_text(item)))
    else:
        candidates = _split_text_like_list(_as_text(value))

    normalized = []
    for item in candidates:
        cleaned = _clean_placeholder(item)
        if not cleaned:
            continue
        normalized.append(_truncate(cleaned, max_len=max_len))
        if len(normalized) >= max_items:
            break
    return normalized


def _normalize_language(value: Any) -> str:
    text = _as_text(value, 'zh').lower()
    if text in {'zh', 'zh-cn', 'cn', 'chinese'}:
        return 'zh'
    if text in {'en', 'en-us', 'english'}:
        return 'en'
    return 'zh'


def _normalize_audience(value: Any) -> str:
    text = _as_text(value, 'general').lower()
    if text in _ALLOWED_AUDIENCES:
        return text
    return 'general'


def _normalize_theme(value: Any, language: str) -> Dict[str, Any]:
    if isinstance(value, str):
        normalized_name = value.strip().lower()
        if normalized_name not in SUPPORTED_THEMES:
            normalized_name = 'minimal'
        return resolve_theme(normalized_name, language=language)
    if isinstance(value, dict):
        raw_name = _as_text(value.get('name') or value.get('theme'), 'minimal').lower()
        if raw_name not in SUPPORTED_THEMES:
            raw_name = 'minimal'
        payload = dict(value)
        payload['name'] = raw_name
        return resolve_theme(payload, language=language)
    return resolve_theme('minimal', language=language)


def _normalize_table(value: Any) -> Tuple[List[str], List[List[str]]]:
    if isinstance(value, dict):
        headers = _as_text_list(value.get('headers'), max_items=_MAX_TABLE_COLS, max_len=80)
        raw_rows = value.get('rows') or []
    else:
        headers = []
        raw_rows = []

    rows: List[List[str]] = []
    if isinstance(raw_rows, Iterable) and not isinstance(raw_rows, (str, bytes, bytearray, dict)):
        for row in raw_rows:
            if isinstance(row, dict):
                if headers:
                    values = [_as_text(row.get(h)) for h in headers]
                else:
                    values = [_as_text(v) for v in row.values()]
            elif isinstance(row, Iterable) and not isinstance(row, (str, bytes, bytearray)):
                values = [_as_text(v) for v in row]
            else:
                values = [_as_text(row)]
            values = [_truncate(v, max_len=80) for v in values]
            rows.append(values)
            if len(rows) >= _MAX_TABLE_ROWS:
                break

    col_count = max([len(headers)] + [len(r) for r in rows] + [0])
    if col_count == 0:
        return [], []

    col_count = min(col_count, _MAX_TABLE_COLS)
    if not headers:
        headers = [f'Column {idx + 1}' for idx in range(col_count)]
    headers = headers[:col_count]

    normalized_rows: List[List[str]] = []
    for row in rows[:_MAX_TABLE_ROWS]:
        normalized_rows.append((row + [''] * col_count)[:col_count])

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
        'refs': 'references',
    }
    normalized = aliases.get(raw_type, raw_type)
    if normalized in _ALLOWED_SLIDE_TYPES:
        return normalized

    has_headers = raw.get('headers') is not None or (isinstance(raw.get('table'), dict) and raw['table'].get('headers'))
    has_rows = raw.get('rows') is not None or (isinstance(raw.get('table'), dict) and raw['table'].get('rows'))
    if has_headers or has_rows:
        return 'table'

    columns = raw.get('columns')
    if isinstance(columns, list) and len(columns) >= 2:
        return 'two_column'

    if raw.get('left') or raw.get('right') or raw.get('left_bullets') or raw.get('right_bullets'):
        return 'comparison'

    if raw.get('items') and len(_as_text_list(raw.get('items'))) >= 2 and index == 1:
        return 'toc'

    if raw.get('bullets') or raw.get('points') or raw.get('items'):
        return 'content_bullets'

    if index == 0:
        return 'cover'
    return 'content_bullets'


def _default_slide_title(index: int, language: str) -> str:
    if language == 'zh':
        return f'第 {index + 1} 页'
    return f'Slide {index + 1}'


def _normalize_columns(raw: Dict[str, Any], bullets: List[str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    columns = raw.get('columns')
    left: Dict[str, Any] = {}
    right: Dict[str, Any] = {}

    if isinstance(columns, list) and len(columns) >= 2:
        c0 = columns[0] if isinstance(columns[0], dict) else {'bullets': columns[0]}
        c1 = columns[1] if isinstance(columns[1], dict) else {'bullets': columns[1]}
        left = {
            'title': _truncate(_as_text(c0.get('title') or c0.get('heading') or 'Left'), max_len=40),
            'bullets': _as_text_list(c0.get('bullets') or c0.get('items'), max_items=6),
        }
        right = {
            'title': _truncate(_as_text(c1.get('title') or c1.get('heading') or 'Right'), max_len=40),
            'bullets': _as_text_list(c1.get('bullets') or c1.get('items'), max_items=6),
        }
    else:
        left_raw = raw.get('left') if isinstance(raw.get('left'), dict) else {}
        right_raw = raw.get('right') if isinstance(raw.get('right'), dict) else {}
        left = {
            'title': _truncate(_as_text(raw.get('left_title') or left_raw.get('title') or 'Left'), max_len=40),
            'bullets': _as_text_list(raw.get('left_bullets') or left_raw.get('bullets') or left_raw.get('items'), max_items=6),
        }
        right = {
            'title': _truncate(_as_text(raw.get('right_title') or right_raw.get('title') or 'Right'), max_len=40),
            'bullets': _as_text_list(raw.get('right_bullets') or right_raw.get('bullets') or right_raw.get('items'), max_items=6),
        }

    if not left.get('bullets') and not right.get('bullets') and bullets:
        midpoint = max(1, len(bullets) // 2)
        left['bullets'] = bullets[:midpoint]
        right['bullets'] = bullets[midpoint:]

    return left, right


def _normalize_slide(raw: Any, index: int, *, language: str) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {'title': _default_slide_title(index, language), 'bullets': raw}

    slide_type = _infer_slide_type(raw, index)
    title = _clean_placeholder(
        _truncate(_as_text(raw.get('title') or raw.get('heading')), max_len=60),
        fallback=_default_slide_title(index, language),
    )
    subtitle = _clean_placeholder(_truncate(_as_text(raw.get('subtitle') or raw.get('sub_title')), max_len=120))
    bullets = _as_text_list(
        raw.get('bullets') or raw.get('items') or raw.get('points'),
        max_items=_MAX_BULLETS_PER_SLIDE,
        max_len=_MAX_BULLET_LEN,
    )
    notes = _truncate(_as_text(raw.get('notes') or raw.get('speaker_notes')), max_len=1500)
    evidence_refs = _as_text_list(raw.get('evidence_refs') or raw.get('citations') or raw.get('sources'), max_items=20, max_len=120)

    normalized: Dict[str, Any] = {
        'type': slide_type,
        'title': title,
        'subtitle': subtitle,
        'bullets': bullets,
        'columns': [],
        'headers': [],
        'rows': [],
        'notes': notes,
        'evidence_refs': evidence_refs,
    }

    if slide_type in {'two_column', 'comparison'}:
        left, right = _normalize_columns(raw, bullets)
        normalized['left'] = left
        normalized['right'] = right
        normalized['columns'] = [left, right]
    elif slide_type == 'table':
        table_payload = raw.get('table') if isinstance(raw.get('table'), dict) else {
            'headers': raw.get('headers'),
            'rows': raw.get('rows'),
        }
        headers, rows = _normalize_table(table_payload)
        normalized['headers'] = headers
        normalized['rows'] = rows
        normalized['table'] = {'headers': headers, 'rows': rows}
        if not normalized['bullets'] and raw.get('summary'):
            normalized['bullets'] = _as_text_list(raw.get('summary'), max_items=3)
    elif slide_type == 'toc':
        normalized['items'] = _as_text_list(raw.get('items') or raw.get('sections') or bullets, max_items=12, max_len=80)
    elif slide_type == 'summary':
        normalized['takeaways'] = _as_text_list(raw.get('takeaways') or bullets, max_items=6, max_len=140)
    elif slide_type == 'references':
        ref_items = _as_text_list(raw.get('items') or raw.get('references') or raw.get('sources') or evidence_refs, max_items=20, max_len=160)
        normalized['items'] = ref_items
        normalized['bullets'] = ref_items

    return normalized


def _collect_all_evidence_refs(slides: List[Dict[str, Any]], sources: List[str]) -> List[str]:
    refs: List[str] = []
    seen = set()
    for source in sources:
        text = _truncate(_as_text(source), max_len=160)
        if text and text not in seen:
            seen.add(text)
            refs.append(text)
    for slide in slides:
        for ref in slide.get('evidence_refs') or []:
            text = _truncate(_as_text(ref), max_len=160)
            if text and text not in seen:
                seen.add(text)
                refs.append(text)
    return refs


def _append_references_slide_if_needed(deck: Dict[str, Any]) -> None:
    slides = deck.get('slides') or []
    if any((slide.get('type') == 'references') for slide in slides):
        return
    refs = _collect_all_evidence_refs(slides, deck.get('sources') or [])
    if not refs:
        return

    slide = {
        'type': 'references',
        'title': '参考资料' if deck.get('language') == 'zh' else 'References',
        'subtitle': '',
        'bullets': refs[:20],
        'items': refs[:20],
        'notes': '',
        'evidence_refs': refs[:20],
        'columns': [],
        'headers': [],
        'rows': [],
    }
    slides.append(slide)


def normalize_deck_schema(deck_schema: Any) -> Dict[str, Any]:
    """Normalize a loose deck schema into a stable, renderer-ready structure."""
    deck = _parse_json_like(deck_schema)

    language = _normalize_language(deck.get('language'))
    title = _clean_placeholder(
        _truncate(_as_text(deck.get('title') or deck.get('deck_title') or deck.get('topic')), max_len=80),
        fallback='LazyRAG Presentation' if language == 'en' else 'LazyRAG 演示文稿',
    )
    subtitle = _clean_placeholder(_truncate(_as_text(deck.get('subtitle') or deck.get('description')), max_len=160))
    audience = _normalize_audience(deck.get('audience'))
    theme = _normalize_theme(deck.get('theme'), language)

    raw_slides = deck.get('slides')
    if not isinstance(raw_slides, list) or not raw_slides:
        raw_slides = [
            {'type': 'cover', 'title': title, 'subtitle': subtitle},
            {
                'type': 'summary',
                'title': 'Summary' if language == 'en' else '总结',
                'bullets': _as_text_list(deck.get('bullets') or deck.get('items') or ['关键结论待补充']),
            },
        ]

    slides = [_normalize_slide(item, idx, language=language) for idx, item in enumerate(raw_slides[:_MAX_SLIDES])]

    if slides and slides[0].get('type') != 'cover':
        slides.insert(
            0,
            {
                'type': 'cover',
                'title': title,
                'subtitle': subtitle,
                'bullets': [],
                'columns': [],
                'headers': [],
                'rows': [],
                'notes': '',
                'evidence_refs': [],
            },
        )

    sources = _as_text_list(deck.get('sources'), max_items=30, max_len=160)

    normalized = {
        'title': title,
        'subtitle': subtitle,
        'language': language,
        'audience': audience,
        'theme': theme,
        'slides': slides,
        'sources': sources,
        'metadata': {
            'normalized': True,
            'theme_name': theme.get('name', 'minimal'),
        },
    }

    _append_references_slide_if_needed(normalized)

    # Ensure all slides have valid titles after potential insertion/appending.
    for idx, slide in enumerate(normalized['slides']):
        if not _as_text(slide.get('title')):
            slide['title'] = _default_slide_title(idx, language)
        if slide.get('type') not in _ALLOWED_SLIDE_TYPES:
            slide['type'] = 'content_bullets'

    return normalized


def validate_deck_schema(deck_schema: Any) -> Dict[str, Any]:
    """Validate a deck schema and always return a normalized recoverable payload."""
    issues: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    try:
        normalized = normalize_deck_schema(deck_schema)
    except Exception as exc:
        return {
            'success': False,
            'valid': False,
            'issues': [
                {
                    'code': 'parse_error',
                    'message': f'Failed to parse deck_schema: {exc}',
                    'slide_index': None,
                }
            ],
            'warnings': [],
            'normalized_schema': {},
        }

    slides = normalized.get('slides') or []
    if not slides:
        issues.append({'code': 'no_slides', 'message': 'No slides found after normalization.', 'slide_index': None})

    for idx, slide in enumerate(slides, start=1):
        slide_type = slide.get('type')
        if slide_type not in _ALLOWED_SLIDE_TYPES:
            issues.append({'code': 'invalid_slide_type', 'message': f'Unsupported slide type: {slide_type}', 'slide_index': idx})

        title = _as_text(slide.get('title'))
        if not title:
            issues.append({'code': 'missing_title', 'message': 'Slide title is missing.', 'slide_index': idx})

        bullets = slide.get('bullets') or []
        if isinstance(bullets, list) and len(bullets) > _MAX_BULLETS_PER_SLIDE:
            warnings.append({'code': 'too_many_bullets', 'message': f'Slide has {len(bullets)} bullets; recommended <= {_MAX_BULLETS_PER_SLIDE}.', 'slide_index': idx})

        for bullet in bullets if isinstance(bullets, list) else []:
            if len(_as_text(bullet)) > _MAX_BULLET_LEN:
                warnings.append({'code': 'bullet_too_long', 'message': 'Bullet text is very long and may overflow.', 'slide_index': idx})
                break

        if slide_type == 'table':
            headers = slide.get('headers') or (slide.get('table') or {}).get('headers') or []
            rows = slide.get('rows') or (slide.get('table') or {}).get('rows') or []
            if not headers or not rows:
                warnings.append({'code': 'sparse_table', 'message': 'Table slide has missing headers or rows.', 'slide_index': idx})
            if len(headers) > _MAX_TABLE_COLS:
                warnings.append({'code': 'table_too_many_columns', 'message': f'Table has {len(headers)} columns; renderer will trim to {_MAX_TABLE_COLS}.', 'slide_index': idx})
            if len(rows) > _MAX_TABLE_ROWS:
                warnings.append({'code': 'table_too_many_rows', 'message': f'Table has {len(rows)} rows; renderer will trim to {_MAX_TABLE_ROWS}.', 'slide_index': idx})

    valid = len(issues) == 0
    return {
        'success': True,
        'valid': valid,
        'issues': issues,
        'warnings': warnings,
        'normalized_schema': normalized,
    }


def repair_deck_schema_for_pptx(deck_schema: Any, qa_result: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Apply deterministic rule-based repairs for common PPTX QA problems."""
    normalized = normalize_deck_schema(deck_schema)
    repaired = deepcopy(normalized)
    changes: List[str] = []

    language = repaired.get('language', 'zh')

    for idx, slide in enumerate(repaired.get('slides') or []):
        if not _as_text(slide.get('title')):
            slide['title'] = _default_slide_title(idx, language)
            changes.append(f'slide_{idx + 1}: add missing title')

        if _PLACEHOLDER_RE.search(_as_text(slide.get('title'))):
            slide['title'] = _default_slide_title(idx, language)
            changes.append(f'slide_{idx + 1}: replace placeholder title')

        if _PLACEHOLDER_RE.search(_as_text(slide.get('subtitle'))):
            slide['subtitle'] = ''
            changes.append(f'slide_{idx + 1}: remove placeholder subtitle')

        bullets = slide.get('bullets') if isinstance(slide.get('bullets'), list) else []
        new_bullets = []
        for bullet in bullets:
            text = _clean_placeholder(_truncate(_as_text(bullet), max_len=140))
            if text:
                new_bullets.append(text)
        if len(new_bullets) > 6:
            new_bullets = new_bullets[:6]
            changes.append(f'slide_{idx + 1}: trim bullets to 6')
        if new_bullets != bullets:
            slide['bullets'] = new_bullets

        if slide.get('type') in {'two_column', 'comparison'}:
            for key in ('left', 'right'):
                section = slide.get(key) if isinstance(slide.get(key), dict) else {}
                raw_list = section.get('bullets') if isinstance(section.get('bullets'), list) else []
                fixed_list = []
                for item in raw_list:
                    text = _clean_placeholder(_truncate(_as_text(item), max_len=120))
                    if text:
                        fixed_list.append(text)
                if len(fixed_list) > 5:
                    fixed_list = fixed_list[:5]
                    changes.append(f'slide_{idx + 1}: trim {key} column bullets to 5')
                section['bullets'] = fixed_list
                section['title'] = _clean_placeholder(_truncate(_as_text(section.get('title')), max_len=40), fallback=key.title())
                slide[key] = section

        if slide.get('type') == 'table':
            headers = slide.get('headers') or (slide.get('table') or {}).get('headers') or []
            rows = slide.get('rows') or (slide.get('table') or {}).get('rows') or []
            if len(headers) > 6:
                headers = headers[:6]
                changes.append(f'slide_{idx + 1}: trim table columns to 6')
            if len(rows) > 10:
                rows = rows[:10]
                changes.append(f'slide_{idx + 1}: trim table rows to 10')
            clipped_rows = []
            for row in rows:
                if isinstance(row, list):
                    values = []
                    for cell in (row + [''] * len(headers))[: len(headers)]:
                        cleaned = _clean_placeholder(_truncate(_as_text(cell), max_len=70), fallback='-')
                        values.append(cleaned)
                    clipped_rows.append(values)
                else:
                    cleaned = _clean_placeholder(_truncate(_as_text(row), max_len=70), fallback='-')
                    clipped_rows.append([cleaned])
            slide['headers'] = [_truncate(_as_text(h), max_len=50) for h in headers]
            slide['rows'] = clipped_rows
            slide['table'] = {'headers': slide['headers'], 'rows': clipped_rows}

    # Use QA signals when available.
    if isinstance(qa_result, dict):
        for issue in qa_result.get('issues') or []:
            if issue.get('code') == 'placeholder_residue':
                changes.append('qa: placeholder residue detected and cleaned')
            if issue.get('code') == 'empty_slide':
                idx = int(issue.get('slide_index') or 0)
                if idx > 0 and idx - 1 < len(repaired['slides']):
                    slide = repaired['slides'][idx - 1]
                    if not slide.get('bullets'):
                        slide['bullets'] = ['内容已自动修复，请补充关键信息。'] if language == 'zh' else ['Auto-repaired placeholder slide. Please add key content.']
                        changes.append(f'slide_{idx}: fill empty slide with fallback bullet')

    _append_references_slide_if_needed(repaired)

    return {
        'success': True,
        'repaired_schema': repaired,
        'changes': changes,
        'changed': bool(changes),
    }
