from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

DEFAULT_HTML_DECK_THEME = 'auto'

_FONT_ZH = 'Microsoft YaHei, PingFang SC, Noto Sans CJK SC, SimHei, Arial, sans-serif'
_FONT_EN = 'Segoe UI, Calibri, Arial, Helvetica, sans-serif'


def _theme(
    name: str,
    mode: str,
    *,
    background: str,
    surface: str,
    surface_alt: str,
    primary: str,
    secondary: str,
    accent: str,
    foreground: str,
    muted: str,
    danger: str,
    success: str,
    border: str,
    style_tag: str,
) -> Dict[str, Any]:
    return {
        'name': name,
        'mode': mode,
        'style_tag': style_tag,
        'canvas_width': 960,
        'canvas_height': 540,
        'background': background,
        'surface': surface,
        'surface_alt': surface_alt,
        'primary': primary,
        'secondary': secondary,
        'accent': accent,
        'foreground': foreground,
        'muted': muted,
        'danger': danger,
        'success': success,
        'border': border,
        'font_zh': _FONT_ZH,
        'font_en': _FONT_EN,
        'title_font_size': 44,
        'body_font_size': 20,
        'caption_font_size': 12,
        'radius': 14,
        'shadow': '0 18px 40px rgba(0,0,0,0.22)' if mode == 'dark' else '0 12px 32px rgba(2, 6, 23, 0.12)',
        'spacing': 24,
    }


_THEME_REGISTRY: Dict[str, Dict[str, Any]] = {
    'dark_tech': _theme(
        'dark_tech',
        'dark',
        background='#000814',
        surface='#001d3d',
        surface_alt='#002855',
        primary='#ffc300',
        secondary='#8ecae6',
        accent='#ffc300',
        foreground='#f8fbff',
        muted='#8fa4bb',
        danger='#ff5d73',
        success='#34d399',
        border='rgba(143,164,187,0.22)',
        style_tag='tech',
    ),
    'cyber_blue': _theme(
        'cyber_blue',
        'dark',
        background='#06111f',
        surface='#0e2847',
        surface_alt='#123761',
        primary='#22d3ee',
        secondary='#60a5fa',
        accent='#22d3ee',
        foreground='#f1f5f9',
        muted='#a3b4c8',
        danger='#fb7185',
        success='#4ade80',
        border='rgba(163,180,200,0.24)',
        style_tag='tech',
    ),
    'corporate_blue': _theme(
        'corporate_blue',
        'light',
        background='#eef4ff',
        surface='#ffffff',
        surface_alt='#dde9ff',
        primary='#1d4ed8',
        secondary='#0ea5e9',
        accent='#1d4ed8',
        foreground='#0f172a',
        muted='#475569',
        danger='#dc2626',
        success='#059669',
        border='rgba(29,78,216,0.18)',
        style_tag='corporate',
    ),
    'academic_light': _theme(
        'academic_light',
        'light',
        background='#f8fafc',
        surface='#ffffff',
        surface_alt='#eef2f7',
        primary='#1e3a8a',
        secondary='#334155',
        accent='#1e40af',
        foreground='#111827',
        muted='#4b5563',
        danger='#b91c1c',
        success='#047857',
        border='rgba(15,23,42,0.14)',
        style_tag='academic',
    ),
    'warm_editorial': _theme(
        'warm_editorial',
        'light',
        background='#fff7ed',
        surface='#fffaf2',
        surface_alt='#fee2c5',
        primary='#c2410c',
        secondary='#9a3412',
        accent='#ea580c',
        foreground='#292524',
        muted='#78716c',
        danger='#be123c',
        success='#15803d',
        border='rgba(194,65,12,0.2)',
        style_tag='editorial',
    ),
    'emerald_dark': _theme(
        'emerald_dark',
        'dark',
        background='#031a16',
        surface='#064e3b',
        surface_alt='#065f46',
        primary='#34d399',
        secondary='#10b981',
        accent='#34d399',
        foreground='#ecfdf5',
        muted='#9be7cf',
        danger='#f97316',
        success='#4ade80',
        border='rgba(155,231,207,0.24)',
        style_tag='data',
    ),
    'violet_neon': _theme(
        'violet_neon',
        'dark',
        background='#13071f',
        surface='#2e1065',
        surface_alt='#4c1d95',
        primary='#c084fc',
        secondary='#22d3ee',
        accent='#c084fc',
        foreground='#faf5ff',
        muted='#d8b4fe',
        danger='#fb7185',
        success='#5eead4',
        border='rgba(216,180,254,0.26)',
        style_tag='creative',
    ),
    'midnight_gold': _theme(
        'midnight_gold',
        'dark',
        background='#0a0a0a',
        surface='#1c1917',
        surface_alt='#292524',
        primary='#f59e0b',
        secondary='#fbbf24',
        accent='#f59e0b',
        foreground='#fafaf9',
        muted='#d6d3d1',
        danger='#ef4444',
        success='#84cc16',
        border='rgba(245,158,11,0.25)',
        style_tag='premium',
    ),
    'light_magazine': _theme(
        'light_magazine',
        'light',
        background='#f6f7fb',
        surface='#ffffff',
        surface_alt='#eceff5',
        primary='#4f46e5',
        secondary='#0ea5e9',
        accent='#4f46e5',
        foreground='#0f172a',
        muted='#64748b',
        danger='#dc2626',
        success='#16a34a',
        border='rgba(79,70,229,0.18)',
        style_tag='magazine',
    ),
}


SUPPORTED_HTML_DECK_THEMES = set(_THEME_REGISTRY.keys()) | {'auto'}

_THEME_ALIASES = {
    'default': 'auto',
    'adaptive': 'auto',
    'visual': 'auto',
    'tech': 'cyber_blue',
    'dark': 'dark_tech',
    'darktech': 'dark_tech',
    'corporate': 'corporate_blue',
    'business': 'corporate_blue',
    'academic': 'academic_light',
    'research': 'academic_light',
    'warm': 'warm_editorial',
    'editorial': 'warm_editorial',
    'emerald': 'emerald_dark',
    'green': 'emerald_dark',
    'violet': 'violet_neon',
    'purple': 'violet_neon',
    'gold': 'midnight_gold',
    'premium': 'midnight_gold',
    'magazine': 'light_magazine',
    'light': 'light_magazine',
}


def available_html_themes() -> Dict[str, Dict[str, Any]]:
    return {
        name: {
            'name': theme['name'],
            'mode': theme['mode'],
            'style_tag': theme['style_tag'],
            'background': theme['background'],
            'surface': theme['surface'],
            'accent': theme['accent'],
            'foreground': theme['foreground'],
        }
        for name, theme in _THEME_REGISTRY.items()
    }


def normalize_html_theme_name(value: Any) -> str:
    text = str(value or '').strip().lower().replace('-', '_').replace(' ', '_')
    if not text:
        return 'auto'
    text = _THEME_ALIASES.get(text, text)
    return text if text in SUPPORTED_HTML_DECK_THEMES else 'auto'


def _deck_blob(deck_schema: Mapping[str, Any] | None) -> str:
    if not deck_schema:
        return ''
    parts = [
        deck_schema.get('title'),
        deck_schema.get('subtitle'),
        deck_schema.get('audience'),
        deck_schema.get('style'),
        deck_schema.get('visual_style'),
    ]
    for slide in deck_schema.get('slides') or []:
        if isinstance(slide, Mapping):
            parts.extend([slide.get('title'), slide.get('subtitle'), slide.get('type'), slide.get('layout')])
    return ' '.join(str(x or '') for x in parts).lower()


def infer_html_theme_name(deck_schema: Mapping[str, Any] | None = None, style_hint: Any = None) -> str:
    chosen = normalize_html_theme_name(style_hint)
    if chosen != 'auto':
        return chosen

    blob = _deck_blob(deck_schema)
    audience = str((deck_schema or {}).get('audience') or '').lower()
    style = str((deck_schema or {}).get('style') or (deck_schema or {}).get('visual_style') or '').lower()

    if any(k in blob for k in ('论文', '学术', 'research', 'paper', 'academic', 'benchmark', '实验')) or audience == 'academic':
        return 'academic_light'
    if any(k in blob for k in ('产品', '商业', 'business', 'market', 'strategy', '融资', 'pitch')) or audience in {'business', 'product'}:
        return 'corporate_blue'
    if any(k in blob for k in ('warm', 'editorial', '观点', '叙事', '课程', '通识')) or 'editorial' in style:
        return 'warm_editorial'
    if any(k in blob for k in ('增长', 'data', 'science', 'bio', 'green', 'metrics heavy')):
        return 'emerald_dark'
    if any(k in blob for k in ('发布会', 'premium', 'gold', '战略发布')):
        return 'midnight_gold'
    if any(k in blob for k in ('创意', 'creative', 'neon', 'demo day')):
        return 'violet_neon'
    if any(k in blob for k in ('ai', 'agent', 'rag', 'llm', 'infra', 'architecture', '技术', '科技')) or audience in {'technical', 'demo'}:
        return 'cyber_blue'
    if 'dark' in style:
        return 'dark_tech'
    return 'light_magazine'


def _merge_palette(base: Dict[str, Any], palette: Mapping[str, Any]) -> Dict[str, Any]:
    allowed = {
        'canvas_width',
        'canvas_height',
        'background',
        'surface',
        'surface_alt',
        'primary',
        'secondary',
        'accent',
        'foreground',
        'muted',
        'danger',
        'success',
        'border',
        'font_zh',
        'font_en',
        'title_font_size',
        'body_font_size',
        'caption_font_size',
        'radius',
        'shadow',
        'spacing',
    }
    aliases = {
        'bg': 'background',
        'surface_alt_color': 'surface_alt',
        'text': 'foreground',
        'body': 'foreground',
        'subtle': 'muted',
    }
    for key, value in palette.items():
        if value in (None, ''):
            continue
        target = aliases.get(str(key), str(key))
        if target in allowed:
            base[target] = value
    return base


def resolve_html_theme(theme: Any = None, *, deck_schema: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    if isinstance(theme, Mapping):
        base_hint = theme.get('base') or theme.get('name') or theme.get('theme') or theme.get('style') or 'auto'
        base_name = infer_html_theme_name(deck_schema, base_hint)
        result = deepcopy(_THEME_REGISTRY[base_name])
        palette = theme.get('palette') if isinstance(theme.get('palette'), Mapping) else {}
        result = _merge_palette(result, palette)
        result = _merge_palette(result, theme)
        result['base_name'] = base_name
        custom_name = str(theme.get('custom_name') or '').strip()
        if custom_name:
            result['name'] = custom_name
        return result

    chosen = infer_html_theme_name(deck_schema, theme)
    resolved = deepcopy(_THEME_REGISTRY[chosen])
    resolved['base_name'] = chosen
    return resolved
