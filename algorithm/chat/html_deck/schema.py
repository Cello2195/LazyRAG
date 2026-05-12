from __future__ import annotations

import json
import math
import re
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Mapping

from .themes import available_html_themes, resolve_html_theme

try:
    from chat.pptx.schema import normalize_deck_schema, validate_deck_schema
except Exception:  # pragma: no cover
    def _fallback_as_list(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            parts = [p.strip(' \t-•') for p in value.replace('；', '\n').replace(';', '\n').split('\n')]
            return [p for p in parts if p]
        return [str(value).strip()]

    def normalize_deck_schema(deck_schema: Any) -> Dict[str, Any]:
        if not isinstance(deck_schema, dict):
            deck_schema = {'title': 'Untitled Deck', 'slides': [{'type': 'content_bullets', 'title': 'Content', 'bullets': _fallback_as_list(deck_schema)}]}
        normalized = dict(deck_schema)
        normalized.setdefault('title', 'Untitled Deck')
        normalized.setdefault('language', 'zh')
        slides = normalized.get('slides') or []
        if not slides:
            slides = [{'type': 'summary', 'title': normalized['title'], 'bullets': ['内容待补充']}]
        out_slides: List[Dict[str, Any]] = []
        for idx, raw in enumerate(slides, start=1):
            if not isinstance(raw, dict):
                raw = {'type': 'content_bullets', 'title': f'第 {idx} 页', 'bullets': _fallback_as_list(raw)}
            slide = dict(raw)
            slide.setdefault('title', '封面' if idx == 1 else f'第 {idx} 页')
            if 'bullets' in slide:
                slide['bullets'] = _fallback_as_list(slide.get('bullets'))
            out_slides.append(slide)
        normalized['slides'] = out_slides
        return normalized

    def validate_deck_schema(deck_schema: Any) -> Dict[str, Any]:
        normalized = normalize_deck_schema(deck_schema)
        return {'success': True, 'valid': True, 'issues': [], 'warnings': [], 'normalized_schema': normalized}


SLIDE_TYPES = {
    'cover',
    'toc',
    'agenda',
    'section',
    'section_divider',
    'metric_cards',
    'challenge_cards',
    'content_bullets',
    'two_column',
    'comparison',
    'table',
    'summary',
    'conclusion',
    'closing',
    'thank_you',
    'quote',
    'process',
    'timeline',
    'references',
}

_LAYOUT_ALIASES = {
    # v3 generic
    'cover_hero': 'cover_hero',
    'toc_numbered': 'toc_numbered',
    'section_divider': 'section_divider',
    'metric_cards': 'metric_cards',
    'challenge_cards': 'challenge_cards',
    'card_grid': 'challenge_cards',
    'content_bullets': 'content_bullets',
    'two_column': 'two_column',
    'comparison': 'comparison',
    'table': 'table',
    'summary': 'summary',
    'quote': 'quote',
    'process': 'process',
    'timeline': 'timeline',
    'references': 'references',
    # old visual names
    'content_cards': 'content_bullets',
    'two_column_cards': 'two_column',
    'comparison_matrix': 'comparison',
    'table_matrix': 'table',
    'summary_takeaways': 'summary',
    # dark/light legacy aliases
    'dark_cover_hero': 'cover_hero',
    'dark_toc_numbered': 'toc_numbered',
    'dark_section_divider': 'section_divider',
    'dark_metric_cards': 'metric_cards',
    'dark_challenge_cards': 'challenge_cards',
    'dark_two_column_cards': 'two_column',
    'dark_comparison_matrix': 'comparison',
    'dark_table_matrix': 'table',
    'dark_summary_takeaways': 'summary',
    'dark_references': 'references',
    'light_cover_hero': 'cover_hero',
    'light_toc_numbered': 'toc_numbered',
    'light_section_divider': 'section_divider',
    'light_metric_cards': 'metric_cards',
    'light_challenge_cards': 'challenge_cards',
    'light_two_column_cards': 'two_column',
    'light_comparison_matrix': 'comparison',
    'light_table_matrix': 'table',
    'light_summary_takeaways': 'summary',
    'light_references': 'references',
}

_TYPE_ALIASES = {
    'title': 'cover',
    'cover': 'cover',
    'toc': 'toc',
    'agenda': 'agenda',
    'contents': 'toc',
    'section': 'section_divider',
    'divider': 'section_divider',
    'metric': 'metric_cards',
    'metrics': 'metric_cards',
    'challenge': 'challenge_cards',
    'cards': 'challenge_cards',
    'bullets': 'content_bullets',
    'content': 'content_bullets',
    'two_column': 'two_column',
    'columns': 'two_column',
    'comparison': 'comparison',
    'compare': 'comparison',
    'table': 'table',
    'summary': 'summary',
    'conclusion': 'conclusion',
    'closing': 'closing',
    'thank_you': 'thank_you',
    'thanks': 'thank_you',
    'quote': 'quote',
    'process': 'process',
    'timeline': 'timeline',
    'references': 'references',
}

_MARKDOWN_FENCE_RE = re.compile(
    r'^\s*```(?:json|javascript|js)?\s*(.*?)\s*```\s*$',
    re.IGNORECASE | re.DOTALL,
)


def _strip_markdown_code_fence(text: str) -> str:
    value = str(text or '').strip()
    if not value:
        return value
    match = _MARKDOWN_FENCE_RE.match(value)
    if match:
        return match.group(1).strip()
    return value


def parse_deck_schema_input(value: Any, *, max_decode_depth: int = 3) -> Dict[str, Any]:
    """Parse deck_schema input from dict / JSON string / fenced / double-encoded JSON.

    Args:
        value: Raw deck schema input.
        max_decode_depth: Maximum json.loads depth for nested encoded strings.

    Returns:
        Parsed deck schema dict.

    Raises:
        ValueError: If parsing fails or payload is structurally invalid.
    """
    if isinstance(value, Mapping):
        parsed: Dict[str, Any] = deepcopy(dict(value))
    else:
        current: Any = value
        if isinstance(current, (bytes, bytearray)):
            current = current.decode('utf-8', errors='ignore')

        parsed = {}
        for depth in range(max(1, int(max_decode_depth))):
            if isinstance(current, Mapping):
                parsed = deepcopy(dict(current))
                break
            if not isinstance(current, str):
                raise ValueError(
                    f'deck_schema must be a dict or JSON string, got {type(current).__name__}'
                )

            text = _strip_markdown_code_fence(current)
            if not text:
                raise ValueError('deck_schema is empty')

            try:
                current = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f'deck_schema JSON parse failed: {exc}') from exc

            if isinstance(current, Mapping):
                parsed = deepcopy(dict(current))
                break
            if isinstance(current, str) and depth + 1 < max_decode_depth:
                continue
            raise ValueError(
                f'deck_schema JSON must decode to an object, got {type(current).__name__}'
            )

        if not parsed:
            raise ValueError('deck_schema parse failed: empty object')

    if 'slides' in parsed and not isinstance(parsed.get('slides'), list):
        raise ValueError('deck_schema.slides must be a list')
    if 'slides' not in parsed:
        parsed['slides'] = []

    return parsed


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


def _trim_text(text: Any, *, max_len: int = 120) -> str:
    value = str(text or '').strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 1] + '…'


def _normalize_palette(palette: Any) -> Dict[str, Any]:
    if isinstance(palette, Mapping):
        out: Dict[str, Any] = {}
        for key, value in palette.items():
            if value in (None, ''):
                continue
            out[str(key)] = str(value)
        return out
    return {}


_SOFT_SLIDE_TYPES = {
    'cover',
    'toc',
    'agenda',
    'section',
    'section_divider',
    'references',
    'thank_you',
    'closing',
}
_SECTION_SLIDE_TYPES = {'section', 'section_divider'}
_PLACEHOLDER_EXACT_RE = re.compile(
    r'^(left|right|column\s*1|column\s*2|point\s*1|point\s*2|todo|tbd|lorem ipsum|占位|待补充|待完善|示例内容)$',
    re.IGNORECASE,
)
_PLACEHOLDER_TEXT_RE = re.compile(
    r'(?<!\w)(column\s*1|column\s*2|point\s*1|point\s*2|todo|tbd|lorem ipsum)(?!\w)|占位|待补充|待完善|示例内容',
    re.IGNORECASE,
)
_CJK_RE = re.compile(r'[\u4e00-\u9fff]')
_WORD_RE = re.compile(r'[A-Za-z0-9]+')


def _slide_type(slide: Mapping[str, Any]) -> str:
    raw = str(slide.get('type') or '').strip().lower().replace('-', '_').replace(' ', '_')
    return _TYPE_ALIASES.get(raw, raw)


def _non_space_len(value: Any) -> int:
    return len(re.sub(r'\s+', '', str(value or '').strip()))


def _content_units(value: Any) -> int:
    text = str(value or '').strip()
    if not text:
        return 0
    cjk = len(_CJK_RE.findall(text))
    words = len(_WORD_RE.findall(text))
    compact = _non_space_len(text)
    return max(cjk + words * 2, compact)


def _looks_substantive_text(value: Any, *, min_units: int = 12) -> bool:
    text = str(value or '').strip()
    if not text:
        return False
    if _PLACEHOLDER_EXACT_RE.match(text):
        return False
    return _content_units(text) >= min_units


def _contains_placeholder(value: Any) -> bool:
    text = str(value or '').strip()
    if not text:
        return False
    return bool(_PLACEHOLDER_TEXT_RE.search(text))


def _to_rows(raw_rows: Any) -> List[List[str]]:
    if not isinstance(raw_rows, list):
        return []
    rows: List[List[str]] = []
    for row in raw_rows:
        if isinstance(row, list):
            rows.append([str(cell or '').strip() for cell in row])
        else:
            rows.append([str(row or '').strip()])
    return rows


def _resolve_two_columns(slide: Mapping[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    left = dict(slide.get('left')) if isinstance(slide.get('left'), Mapping) else {}
    right = dict(slide.get('right')) if isinstance(slide.get('right'), Mapping) else {}
    if left and right:
        return left, right
    columns = slide.get('columns') if isinstance(slide.get('columns'), list) else []
    if len(columns) >= 2:
        if isinstance(columns[0], Mapping):
            left = dict(columns[0])
        else:
            left = {'title': '', 'bullets': _as_list(columns[0])}
        if isinstance(columns[1], Mapping):
            right = dict(columns[1])
        else:
            right = {'title': '', 'bullets': _as_list(columns[1])}
    return left, right


def _required_substantive_slides(total_slides: int) -> int:
    if total_slides <= 0:
        return 0
    if total_slides <= 4:
        return max(1, total_slides - 1)
    if total_slides <= 7:
        return max(3, math.ceil(total_slides * 0.6))
    return max(4, math.ceil(total_slides * 0.6))


def _max_section_slides(total_slides: int) -> int:
    if total_slides <= 6:
        return 1
    if total_slides <= 10:
        return 2
    return max(2, math.ceil(total_slides * 0.25))


def _is_substantive_body_slide(slide: Mapping[str, Any]) -> tuple[bool, List[str]]:
    slide_type = _slide_type(slide)
    reasons: List[str] = []

    def _check_bullet_block(raw: Any, *, label: str = 'bullets') -> None:
        bullets = _as_list(raw)
        if len(bullets) < 3:
            reasons.append(f'{label} count < 3')
            return
        short_count = 0
        total_units = 0
        for idx, bullet in enumerate(bullets, start=1):
            if _contains_placeholder(bullet):
                reasons.append(f'{label}[{idx}] contains placeholder content')
            units = _content_units(bullet)
            total_units += units
            if units < 12:
                short_count += 1
        if short_count:
            reasons.append(f'{label} has {short_count} short items')
        if total_units < 80:
            reasons.append(f'{label} total body text too short ({total_units} < 80)')

    if slide_type in {'content_bullets', 'summary', 'conclusion'}:
        _check_bullet_block(slide.get('bullets') or slide.get('items') or slide.get('takeaways'))

    elif slide_type == 'challenge_cards':
        cards = slide.get('cards') if isinstance(slide.get('cards'), list) else []
        if len(cards) < 3:
            reasons.append('cards count < 3')
        total_units = 0
        for idx, card in enumerate(cards, start=1):
            if not isinstance(card, Mapping):
                reasons.append(f'card[{idx}] is not an object')
                continue
            title = str(card.get('title') or '').strip()
            body = str(card.get('body') or '').strip()
            if not title:
                reasons.append(f'card[{idx}] missing title')
            if _contains_placeholder(title):
                reasons.append(f'card[{idx}] title contains placeholder content')
            if not body:
                reasons.append(f'card[{idx}] missing body')
                continue
            if _contains_placeholder(body):
                reasons.append(f'card[{idx}] body contains placeholder content')
            units = _content_units(body)
            total_units += units
            if units < 12:
                reasons.append(f'card[{idx}] body too short')
        if cards and total_units < 60:
            reasons.append(f'cards total body text too short ({total_units} < 60)')

    elif slide_type == 'metric_cards':
        metrics = slide.get('metrics') if isinstance(slide.get('metrics'), list) else []
        if len(metrics) < 2:
            reasons.append('metrics count < 2')
        for idx, metric in enumerate(metrics, start=1):
            if not isinstance(metric, Mapping):
                reasons.append(f'metric[{idx}] is not an object')
                continue
            label = str(metric.get('label') or '').strip()
            value = str(metric.get('value') or '').strip()
            description = str(metric.get('description') or '').strip()
            if not label:
                reasons.append(f'metric[{idx}] missing label')
            if not value:
                reasons.append(f'metric[{idx}] missing value')
            if not description:
                reasons.append(f'metric[{idx}] missing description')
            elif not _looks_substantive_text(description, min_units=10):
                reasons.append(f'metric[{idx}] description too short')
            if _contains_placeholder(f'{label} {value} {description}'):
                reasons.append(f'metric[{idx}] contains placeholder content')

    elif slide_type == 'two_column':
        left, right = _resolve_two_columns(slide)
        if not left or not right:
            reasons.append('missing left/right column objects')
        total_units = 0
        for name, col in (('left', left), ('right', right)):
            title = str(col.get('title') or '').strip()
            if not title:
                reasons.append(f'{name}.title is empty')
            elif _PLACEHOLDER_EXACT_RE.match(title):
                reasons.append(f'{name}.title is placeholder content')
            bullets = _as_list(col.get('bullets') or col.get('items'))
            if len(bullets) < 3:
                reasons.append(f'{name}.bullets count < 3')
                continue
            for idx, bullet in enumerate(bullets, start=1):
                if _contains_placeholder(bullet):
                    reasons.append(f'{name}.bullets[{idx}] contains placeholder content')
                units = _content_units(bullet)
                total_units += units
                if units < 10:
                    reasons.append(f'{name}.bullets[{idx}] too short')
        if total_units < 100:
            reasons.append(f'two_column total body text too short ({total_units} < 100)')

    elif slide_type in {'comparison', 'table'}:
        headers = _as_list(slide.get('headers'))
        rows = _to_rows(slide.get('rows'))
        if headers and rows:
            if len(headers) < 2:
                reasons.append('table headers count < 2')
            if len(rows) < 3:
                reasons.append('table rows count < 3')
            for idx, row in enumerate(rows, start=1):
                if not any(str(cell or '').strip() for cell in row):
                    reasons.append(f'row[{idx}] is empty')
        else:
            left_items = _as_list(slide.get('left_items'))
            right_items = _as_list(slide.get('right_items'))
            if len(left_items) < 3 or len(right_items) < 3:
                reasons.append('comparison items are insufficient (<3 per side)')
            if _PLACEHOLDER_EXACT_RE.match(str(slide.get('left_title') or '').strip()):
                reasons.append('left_title is placeholder content')
            if _PLACEHOLDER_EXACT_RE.match(str(slide.get('right_title') or '').strip()):
                reasons.append('right_title is placeholder content')

    elif slide_type in {'process', 'timeline'}:
        raw_steps = slide.get('steps') if isinstance(slide.get('steps'), list) else []
        raw_items = slide.get('items') if isinstance(slide.get('items'), list) else []
        steps = raw_steps or raw_items
        if len(steps) < 4:
            reasons.append('steps/items count < 4')
        for idx, item in enumerate(steps, start=1):
            if isinstance(item, Mapping):
                title = str(item.get('title') or '').strip()
                description = str(item.get('description') or item.get('desc') or '').strip()
                if slide_type == 'timeline' and not str(item.get('time') or '').strip():
                    reasons.append(f'{slide_type}[{idx}] missing time')
                if not title:
                    reasons.append(f'{slide_type}[{idx}] missing title')
                if not description:
                    reasons.append(f'{slide_type}[{idx}] missing description')
                elif not _looks_substantive_text(description, min_units=10):
                    reasons.append(f'{slide_type}[{idx}] description too short')
                if _contains_placeholder(f'{title} {description}'):
                    reasons.append(f'{slide_type}[{idx}] contains placeholder content')
            else:
                if not _looks_substantive_text(item, min_units=12):
                    reasons.append(f'{slide_type}[{idx}] text too short')

    elif slide_type == 'quote':
        quote = (
            slide.get('quote')
            or slide.get('body')
            or slide.get('subtitle')
            or slide.get('title')
            or ''
        )
        if not _looks_substantive_text(quote, min_units=24):
            reasons.append('quote text too short')
        author = str(slide.get('author') or slide.get('source') or '').strip()
        if not author:
            reasons.append('quote source/author is empty')
        elif _contains_placeholder(author):
            reasons.append('quote source/author contains placeholder content')

    else:
        has_body = bool(
            _as_list(slide.get('bullets') or slide.get('items') or slide.get('steps'))
            or (slide.get('cards') if isinstance(slide.get('cards'), list) else [])
            or (slide.get('metrics') if isinstance(slide.get('metrics'), list) else [])
            or (_to_rows(slide.get('rows')))
        )
        if not has_body:
            reasons.append('missing body structures (bullets/cards/metrics/rows/steps)')

    return len(reasons) == 0, reasons


def _infer_slide_type(slide: Mapping[str, Any], index: int) -> str:
    raw_type = str(slide.get('type') or slide.get('slide_type') or '').strip().lower().replace('-', '_').replace(' ', '_')
    if raw_type:
        raw_type = _TYPE_ALIASES.get(raw_type, raw_type)
        if raw_type in SLIDE_TYPES:
            return raw_type

    if slide.get('headers') or slide.get('rows'):
        return 'table'
    if slide.get('columns') or slide.get('left') or slide.get('right'):
        return 'two_column'
    if slide.get('metrics'):
        return 'metric_cards'
    cards = slide.get('cards')
    if isinstance(cards, list) and len(cards) >= 3:
        return 'challenge_cards'
    if slide.get('items') and index == 0:
        return 'toc'
    if slide.get('items'):
        return 'content_bullets'
    if slide.get('bullets'):
        return 'content_bullets'
    if index == 0:
        return 'cover'
    return 'summary'


def resolve_slide_layout(slide: Mapping[str, Any], deck_schema: Mapping[str, Any], index: int) -> str:
    raw = str(slide.get('layout') or slide.get('visual_layout') or '').strip().lower().replace('-', '_').replace(' ', '_')
    if raw:
        mapped = _LAYOUT_ALIASES.get(raw)
        if mapped:
            return mapped

    slide_type = str(slide.get('type') or '').strip().lower().replace('-', '_')
    mapping = {
        'cover': 'cover_hero',
        'toc': 'toc_numbered',
        'agenda': 'toc_numbered',
        'section': 'section_divider',
        'section_divider': 'section_divider',
        'metric_cards': 'metric_cards',
        'challenge_cards': 'challenge_cards',
        'content_bullets': 'content_bullets',
        'two_column': 'two_column',
        'comparison': 'comparison',
        'table': 'table',
        'summary': 'summary',
        'conclusion': 'summary',
        'closing': 'summary',
        'thank_you': 'summary',
        'quote': 'quote',
        'process': 'process',
        'timeline': 'timeline',
        'references': 'references',
    }
    return mapping.get(slide_type, 'content_bullets')


def resolve_visual_theme(deck_schema: Mapping[str, Any]) -> Dict[str, Any]:
    theme_input = (
        deck_schema.get('visual_theme')
        or deck_schema.get('theme')
        or deck_schema.get('style')
        or 'auto'
    )
    palette = _normalize_palette(deck_schema.get('palette'))
    if palette:
        if isinstance(theme_input, Mapping):
            merged = dict(theme_input)
            merged.setdefault('palette', {})
            merged['palette'] = {**_normalize_palette(merged.get('palette')), **palette}
            return resolve_html_theme(merged, deck_schema=deck_schema)
        return resolve_html_theme({'base': theme_input, 'palette': palette}, deck_schema=deck_schema)
    return resolve_html_theme(theme_input, deck_schema=deck_schema)


def normalize_visual_deck_schema(deck_schema: Any, theme: Any = None) -> Dict[str, Any]:
    try:
        parsed_input = parse_deck_schema_input(deck_schema)
    except ValueError:
        parsed_input = deck_schema if isinstance(deck_schema, Mapping) else {}

    raw_input = dict(parsed_input) if isinstance(parsed_input, Mapping) else {}
    if theme not in (None, ''):
        raw_input['visual_theme'] = theme
    base = normalize_deck_schema(parsed_input if parsed_input else deck_schema)
    normalized: Dict[str, Any] = deepcopy(base if isinstance(base, dict) else {})

    # Preserve visual-route top-level fields that may be dropped by editable-pptx normalizer.
    for field in ('visual_theme', 'palette', 'style', 'visual_style', 'audience', 'language', 'title', 'subtitle'):
        if isinstance(raw_input, Mapping) and raw_input.get(field) not in (None, ''):
            normalized[field] = deepcopy(raw_input.get(field))

    normalized['title'] = _trim_text(normalized.get('title') or 'Untitled Visual Deck', max_len=120)
    normalized['subtitle'] = _trim_text(normalized.get('subtitle') or '', max_len=160)
    normalized['language'] = 'en' if str(normalized.get('language') or '').lower().startswith('en') else 'zh'

    audience = str(normalized.get('audience') or 'general').strip().lower()
    if audience not in {'academic', 'business', 'technical', 'general', 'product', 'demo'}:
        audience = 'general'
    normalized['audience'] = audience

    style = str(normalized.get('style') or normalized.get('visual_style') or 'auto').strip().lower()
    normalized['style'] = style or 'auto'

    theme = resolve_visual_theme(normalized)
    normalized['visual_theme'] = theme
    normalized['theme_used'] = theme.get('name')
    normalized['palette_used'] = {
        key: theme.get(key)
        for key in ('background', 'surface', 'surface_alt', 'primary', 'secondary', 'accent', 'foreground', 'muted', 'danger', 'success', 'border')
    }
    normalized['available_visual_themes'] = list(available_html_themes().keys())
    normalized['output_mode'] = 'visual_pptx'

    base_slides_raw = normalized.get('slides') if isinstance(normalized.get('slides'), list) else []
    source_slides_raw = raw_input.get('slides') if isinstance(raw_input, Mapping) and isinstance(raw_input.get('slides'), list) else []

    merged_slides_raw: List[Dict[str, Any]] = []
    for idx in range(max(len(base_slides_raw), len(source_slides_raw))):
        base_slide = base_slides_raw[idx] if idx < len(base_slides_raw) and isinstance(base_slides_raw[idx], Mapping) else {}
        source_slide = source_slides_raw[idx] if idx < len(source_slides_raw) and isinstance(source_slides_raw[idx], Mapping) else {}
        merged = dict(base_slide)
        merged.update(dict(source_slide))
        merged_slides_raw.append(merged if merged else {'title': f'第 {idx + 1} 页'})

    slides: List[Dict[str, Any]] = []
    evidence_pool: List[str] = []
    for idx, raw in enumerate(merged_slides_raw):
        slide = dict(raw) if isinstance(raw, Mapping) else {'bullets': _as_list(raw)}
        slide_type = _infer_slide_type(slide, idx)
        slide['type'] = slide_type

        title_default = '封面' if idx == 0 else f'第 {idx + 1} 页'
        slide['title'] = _trim_text(slide.get('title') or title_default, max_len=64)
        slide['subtitle'] = _trim_text(slide.get('subtitle') or '', max_len=120)

        bullets = _as_list(slide.get('bullets'))
        bullets = [_trim_text(item, max_len=110) for item in bullets]
        if len(bullets) > 6:
            bullets = bullets[:6]
            slide.setdefault('_warnings', []).append('bullets_truncated_to_6')
        slide['bullets'] = bullets

        metrics = slide.get('metrics') if isinstance(slide.get('metrics'), list) else []
        normalized_metrics: List[Dict[str, str]] = []
        for item in metrics[:6]:
            if not isinstance(item, Mapping):
                continue
            normalized_metrics.append({
                'label': _trim_text(item.get('label') or item.get('name') or item.get('title'), max_len=24),
                'value': _trim_text(item.get('value') or item.get('metric') or item.get('number'), max_len=18),
                'description': _trim_text(item.get('description') or item.get('desc') or item.get('note'), max_len=60),
            })
        slide['metrics'] = normalized_metrics

        cards = slide.get('cards') if isinstance(slide.get('cards'), list) else []
        normalized_cards: List[Dict[str, str]] = []
        for item in cards[:6]:
            if isinstance(item, Mapping):
                normalized_cards.append({
                    'title': _trim_text(item.get('title') or '', max_len=28),
                    'body': _trim_text(item.get('body') or item.get('content') or '', max_len=90),
                    'accent': _trim_text(item.get('accent') or 'primary', max_len=16),
                })
            else:
                normalized_cards.append({'title': '', 'body': _trim_text(item, max_len=90), 'accent': 'primary'})
        slide['cards'] = normalized_cards

        if slide_type == 'table':
            headers = _as_list(slide.get('headers'))[:8]
            rows = slide.get('rows') if isinstance(slide.get('rows'), list) else []
            rows = rows[:12]
            compact_rows: List[List[str]] = []
            for row in rows:
                if isinstance(row, list):
                    compact_rows.append([_trim_text(c, max_len=36) for c in row[: len(headers) or 8]])
                else:
                    compact_rows.append([_trim_text(row, max_len=36)])
            slide['headers'] = [_trim_text(h, max_len=20) for h in headers]
            slide['rows'] = compact_rows
            if len(rows) > 10:
                slide.setdefault('_warnings', []).append('table_rows_truncated')

        refs = _as_list(slide.get('evidence_refs'))
        slide['evidence_refs'] = [_trim_text(r, max_len=120) for r in refs[:8]]
        for ref in slide['evidence_refs']:
            if ref not in evidence_pool:
                evidence_pool.append(ref)

        layout = resolve_slide_layout(slide, normalized, idx)
        slide['layout'] = layout
        slide['visual_layout'] = layout
        slides.append(slide)

    if not slides:
        slides = [
            {
                'type': 'summary',
                'title': normalized['title'],
                'subtitle': normalized['subtitle'],
                'bullets': ['内容待补充'],
                'layout': 'summary',
                'visual_layout': 'summary',
                'evidence_refs': [],
            }
        ]

    has_ref_slide = any(str(s.get('type') or '').lower() == 'references' for s in slides)
    if evidence_pool and not has_ref_slide:
        slides.append(
            {
                'type': 'references',
                'title': 'References' if normalized['language'] == 'en' else '资料来源',
                'subtitle': '',
                'bullets': evidence_pool[:10],
                'items': evidence_pool[:10],
                'layout': 'references',
                'visual_layout': 'references',
                'evidence_refs': evidence_pool[:10],
            }
        )

    normalized['slides'] = slides
    normalized['slide_count'] = len(slides)
    return normalized


def validate_visual_deck_schema(deck_schema: Any, theme: Any = None) -> Dict[str, Any]:
    try:
        parsed_input = parse_deck_schema_input(deck_schema)
    except ValueError as exc:
        return {
            'success': False,
            'valid': False,
            'issues': [
                {
                    'level': 'error',
                    'code': 'schema_parse_failed',
                    'message': str(exc),
                }
            ],
            'warnings': [],
            'normalized_schema': {},
        }

    base = validate_deck_schema(parsed_input)
    normalized = normalize_visual_deck_schema(parsed_input, theme=theme)

    issues: List[Dict[str, Any]] = list(base.get('issues') or []) if isinstance(base, dict) else []
    warnings: List[Dict[str, Any]] = list(base.get('warnings') or []) if isinstance(base, dict) else []

    if not normalized.get('title'):
        issues.append({'level': 'error', 'code': 'missing_title', 'message': 'deck title is empty'})
    if not normalized.get('slides'):
        issues.append({'level': 'error', 'code': 'missing_slides', 'message': 'no slides after normalization'})

    seen_layouts: set[str] = set()
    cover_count = 0
    toc_count = 0
    section_count = 0
    substantive_count = 0
    slides = normalized.get('slides') or []
    total_slides = len(slides)
    for idx, slide in enumerate(slides, start=1):
        if not slide.get('title'):
            warnings.append({'level': 'warning', 'code': 'slide_missing_title', 'message': f'slide {idx} missing title'})
        layout = str(slide.get('layout') or '')
        if layout:
            seen_layouts.add(layout)
        for warn in slide.get('_warnings') or []:
            warnings.append({'level': 'warning', 'code': warn, 'message': f'slide {idx}: {warn}'})

        slide_type = _slide_type(slide)
        if slide_type == 'cover':
            cover_count += 1
        if slide_type in {'toc', 'agenda'}:
            toc_count += 1
        if slide_type in _SECTION_SLIDE_TYPES:
            section_count += 1

        if slide_type in _SOFT_SLIDE_TYPES:
            continue

        substantive_ok, reasons = _is_substantive_body_slide(slide)
        if substantive_ok:
            substantive_count += 1
            continue

        has_placeholder = any('placeholder' in reason.lower() for reason in reasons)
        issues.append(
            {
                'level': 'error',
                'code': 'placeholder_content' if has_placeholder else 'sparse_body_slide',
                'slide_index': idx,
                'slide_title': str(slide.get('title') or ''),
                'message': 'Slide has title but insufficient substantive body content. Rebuild deck_schema with richer details before rendering.',
                'reasons': reasons[:8],
                'hints': [
                    'Add at least 3 concrete bullets with explanatory text.',
                    'Do not use title-only or outline-only body slides.',
                    'For two_column slides, fill both left and right columns with substantive bullets.',
                ],
            }
        )

    if cover_count > 1:
        issues.append(
            {
                'level': 'error',
                'code': 'too_many_cover_slides',
                'message': f'cover slides exceed limit (count={cover_count}, max=1)',
                'hints': ['Keep only one cover slide and convert extra cover pages to substantive body slides.'],
            }
        )
    if toc_count > 1:
        issues.append(
            {
                'level': 'error',
                'code': 'too_many_toc_slides',
                'message': f'toc/agenda slides exceed limit (count={toc_count}, max=1)',
                'hints': ['Keep only one toc/agenda slide; move details into body slides.'],
            }
        )

    section_limit = _max_section_slides(total_slides)
    if section_count > section_limit:
        issues.append(
            {
                'level': 'error',
                'code': 'too_many_section_slides',
                'message': f'section divider slides are too many (count={section_count}, max={section_limit})',
                'hints': ['Reduce section divider slides and expand substantive content pages instead.'],
            }
        )

    required_substantive = _required_substantive_slides(total_slides)
    if substantive_count < required_substantive:
        issues.append(
            {
                'level': 'error',
                'code': 'too_few_substantive_slides',
                'message': (
                    f'too few substantive body slides: {substantive_count}/{total_slides}; '
                    f'require at least {required_substantive}'
                ),
                'hints': [
                    'Increase content-rich body slides with bullets/cards/table/process/timeline details.',
                    'Do not count cover/toc/section/closing pages as substantive body content.',
                ],
            }
        )

    if len(seen_layouts) <= 1 and len(normalized.get('slides') or []) > 2:
        warnings.append({'level': 'warning', 'code': 'layout_repetition', 'message': 'most slides use the same layout; visual rhythm may be weak'})

    warnings.append(
        {
            'level': 'warning',
            'code': 'visual_pptx_image_based',
            'message': 'visual_pptx export is image-based PPTX and not fully text-editable',
        }
    )

    return {
        'success': True,
        'valid': not issues and bool(base.get('valid', True) if isinstance(base, dict) else True),
        'issues': issues,
        'warnings': warnings,
        'normalized_schema': normalized,
    }


# Backward-compatible aliases (existing delta code may import these names).
normalize_html_deck_schema = normalize_visual_deck_schema
validate_html_deck_schema = validate_visual_deck_schema
