from __future__ import annotations

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
    'section_divider',
    'metric_cards',
    'challenge_cards',
    'content_bullets',
    'two_column',
    'comparison',
    'table',
    'summary',
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
    'quote': 'quote',
    'process': 'process',
    'timeline': 'timeline',
    'references': 'references',
}


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
        'section_divider': 'section_divider',
        'metric_cards': 'metric_cards',
        'challenge_cards': 'challenge_cards',
        'content_bullets': 'content_bullets',
        'two_column': 'two_column',
        'comparison': 'comparison',
        'table': 'table',
        'summary': 'summary',
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


def normalize_visual_deck_schema(deck_schema: Any) -> Dict[str, Any]:
    raw_input = deck_schema if isinstance(deck_schema, Mapping) else {}
    base = normalize_deck_schema(deck_schema)
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


def validate_visual_deck_schema(deck_schema: Any) -> Dict[str, Any]:
    base = validate_deck_schema(deck_schema)
    normalized = normalize_visual_deck_schema(base.get('normalized_schema') if isinstance(base, dict) else deck_schema)

    issues: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = list(base.get('warnings') or []) if isinstance(base, dict) else []

    if not normalized.get('title'):
        issues.append({'level': 'error', 'code': 'missing_title', 'message': 'deck title is empty'})
    if not normalized.get('slides'):
        issues.append({'level': 'error', 'code': 'missing_slides', 'message': 'no slides after normalization'})

    seen_layouts: set[str] = set()
    for idx, slide in enumerate(normalized.get('slides') or [], start=1):
        if not slide.get('title'):
            warnings.append({'level': 'warning', 'code': 'slide_missing_title', 'message': f'slide {idx} missing title'})
        layout = str(slide.get('layout') or '')
        if layout:
            seen_layouts.add(layout)
        for warn in slide.get('_warnings') or []:
            warnings.append({'level': 'warning', 'code': warn, 'message': f'slide {idx}: {warn}'})

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
