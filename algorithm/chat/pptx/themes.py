from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List


SUPPORTED_THEMES = {'academic', 'business', 'minimal'}
SUPPORTED_LANGUAGES = {'zh', 'en'}

_THEME_REGISTRY: Dict[str, Dict[str, Any]] = {
    'minimal': {
        'name': 'minimal',
        'slide_width': 13.333,
        'slide_height': 7.5,
        'background_color': 'FFFFFF',
        'title_color': '111827',
        'body_color': '1F2937',
        'accent_color': '2563EB',
        'muted_color': '6B7280',
        'surface_color': 'F8FAFC',
        'line_color': 'E5E7EB',
        'font_candidates_zh': ['Microsoft YaHei', 'PingFang SC', 'Noto Sans CJK SC', 'SimHei', 'Arial'],
        'font_candidates_en': ['Calibri', 'Arial', 'Helvetica'],
        'title_font_size': 30,
        'subtitle_font_size': 17,
        'body_font_size': 19,
        'small_font_size': 10,
        'footer_font_size': 8,
        'margin': 0.68,
        'top_spacing': 1.35,
        'line_spacing': 1.15,
    },
    'academic': {
        'name': 'academic',
        'slide_width': 13.333,
        'slide_height': 7.5,
        'background_color': 'FFFFFF',
        'title_color': '0F172A',
        'body_color': '1E293B',
        'accent_color': '0369A1',
        'muted_color': '64748B',
        'surface_color': 'F1F5F9',
        'line_color': 'CBD5E1',
        'font_candidates_zh': ['Microsoft YaHei', 'Noto Sans CJK SC', 'PingFang SC', 'SimSun', 'Arial'],
        'font_candidates_en': ['Cambria', 'Georgia', 'Calibri', 'Arial'],
        'title_font_size': 29,
        'subtitle_font_size': 16,
        'body_font_size': 18,
        'small_font_size': 10,
        'footer_font_size': 8,
        'margin': 0.72,
        'top_spacing': 1.38,
        'line_spacing': 1.18,
    },
    'business': {
        'name': 'business',
        'slide_width': 13.333,
        'slide_height': 7.5,
        'background_color': 'F8FAFC',
        'title_color': '0B1120',
        'body_color': '1F2937',
        'accent_color': '0EA5E9',
        'muted_color': '64748B',
        'surface_color': 'FFFFFF',
        'line_color': 'D1D5DB',
        'font_candidates_zh': ['Microsoft YaHei', 'PingFang SC', 'Noto Sans CJK SC', 'SimHei', 'Arial'],
        'font_candidates_en': ['Segoe UI', 'Calibri', 'Arial', 'Helvetica'],
        'title_font_size': 32,
        'subtitle_font_size': 18,
        'body_font_size': 18,
        'small_font_size': 10,
        'footer_font_size': 8,
        'margin': 0.62,
        'top_spacing': 1.34,
        'line_spacing': 1.16,
    },
}


def _pick_font(language: str, theme: Dict[str, Any]) -> str:
    lang = str(language or 'zh').strip().lower()
    if lang in {'zh', 'zh-cn', 'zh-hans'}:
        candidates = theme.get('font_candidates_zh') or []
    else:
        candidates = theme.get('font_candidates_en') or []
    if isinstance(candidates, list) and candidates:
        return str(candidates[0])
    return 'Arial'


def normalize_theme_name(value: Any) -> str:
    text = str(value or '').strip().lower()
    if text in SUPPORTED_THEMES:
        return text
    return 'minimal'


def resolve_theme(theme: Any, *, language: str = 'zh') -> Dict[str, Any]:
    if isinstance(theme, dict):
        base_name = normalize_theme_name(theme.get('name') or theme.get('theme'))
        resolved = deepcopy(_THEME_REGISTRY[base_name])
        for key, value in theme.items():
            if key in resolved and value not in (None, ''):
                resolved[key] = value
    else:
        base_name = normalize_theme_name(theme)
        resolved = deepcopy(_THEME_REGISTRY[base_name])

    resolved['name'] = normalize_theme_name(resolved.get('name'))
    resolved['font_family'] = _pick_font(language, resolved)
    resolved['language'] = language if language in SUPPORTED_LANGUAGES else 'zh'
    return resolved


def available_theme_names() -> List[str]:
    return sorted(_THEME_REGISTRY.keys())
