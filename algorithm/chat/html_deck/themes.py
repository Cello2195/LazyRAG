from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

"""Theme registry for the visual HTML-deck route.

The previous v3 implementation exposed many theme names, but most of them
shared the same dark template and only changed a few colors.  This module keeps
backward-compatible names while consolidating the visual system around one
coherent Guizang/MiniMax-like family: magazine slides, strong framing, large
numbering, editorial cards, SVG ornaments, and theme-specific composition
rules.

`dark_tech`, `corporate_blue`, etc. are still accepted for compatibility, but
internally each theme carries richer design tokens than color values only.
Layouts should read these tokens instead of hard-coding a single palette.
"""

DEFAULT_HTML_DECK_THEME = 'auto'

_FONT_ZH = 'Microsoft YaHei, PingFang SC, Noto Sans CJK SC, Source Han Sans SC, SimHei, Arial, sans-serif'
_FONT_EN = 'Inter, Segoe UI, Calibri, Arial, Helvetica, sans-serif'
_FONT_SERIF = 'Georgia, Times New Roman, Noto Serif CJK SC, serif'


def _theme(
    name: str,
    mode: str,
    *,
    background: str,
    canvas: str,
    surface: str,
    surface_alt: str,
    foreground: str,
    muted: str,
    primary: str,
    secondary: str,
    accent: str,
    danger: str,
    success: str,
    border: str,
    style_tag: str,
    background_variant: str,
    layout_frame: str,
    title_treatment: str,
    card_style: str,
    ornament: str,
    density: str = 'balanced',
    radius: int = 18,
    shadow: str | None = None,
) -> Dict[str, Any]:
    return {
        'name': name,
        'mode': mode,
        'style_tag': style_tag,
        'canvas_width': 960,
        'canvas_height': 540,
        'background': background,
        'canvas': canvas,
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
        'font_serif': _FONT_SERIF,
        'title_font_size': 42,
        'body_font_size': 18,
        'caption_font_size': 12,
        'radius': radius,
        'shadow': shadow or ('0 22px 50px rgba(0,0,0,0.35)' if mode == 'dark' else '0 18px 42px rgba(15,23,42,0.14)'),
        'spacing': 24,
        # Design-language tokens.  These are the important part of v4.
        'background_variant': background_variant,
        'layout_frame': layout_frame,
        'title_treatment': title_treatment,
        'card_style': card_style,
        'ornament': ornament,
        'density': density,
    }


_THEME_REGISTRY: Dict[str, Dict[str, Any]] = {
    # Core Guizang-style family.  Start from one design language, not a bag of
    # unrelated templates.
    'guizang_ink': _theme(
        'guizang_ink',
        'dark',
        background='#090b0f',
        canvas='#0e1117',
        surface='#171b22',
        surface_alt='#222832',
        foreground='#f3efe4',
        muted='#b8b0a2',
        primary='#f6c55c',
        secondary='#7dd3fc',
        accent='#f6c55c',
        danger='#ff6b6b',
        success='#7dd87d',
        border='rgba(246,197,92,0.24)',
        style_tag='guizang_ink',
        background_variant='ink_radial',
        layout_frame='magazine_frame',
        title_treatment='editorial_serif',
        card_style='ink_card',
        ornament='rings_and_rules',
        density='balanced',
        radius=16,
    ),
    'guizang_aurora': _theme(
        'guizang_aurora',
        'dark',
        background='#07111f',
        canvas='#081a2c',
        surface='#0e2a45',
        surface_alt='#123a5f',
        foreground='#edf7ff',
        muted='#a8c2d8',
        primary='#38bdf8',
        secondary='#a78bfa',
        accent='#fbbf24',
        danger='#fb7185',
        success='#34d399',
        border='rgba(56,189,248,0.24)',
        style_tag='guizang_aurora',
        background_variant='aurora_mesh',
        layout_frame='tech_frame',
        title_treatment='wide_sans',
        card_style='glass_card',
        ornament='circuit_dots',
        density='compact',
        radius=18,
    ),
    'guizang_paper': _theme(
        'guizang_paper',
        'light',
        background='#f3eadb',
        canvas='#fff7ea',
        surface='#fffdf6',
        surface_alt='#eadfcf',
        foreground='#2a2118',
        muted='#746653',
        primary='#9a4d19',
        secondary='#c48a44',
        accent='#c25a1a',
        danger='#b42318',
        success='#287a42',
        border='rgba(154,77,25,0.23)',
        style_tag='guizang_paper',
        background_variant='paper_grid',
        layout_frame='editorial_margin',
        title_treatment='editorial_serif',
        card_style='paper_card',
        ornament='print_marks',
        density='airy',
        radius=10,
        shadow='0 16px 34px rgba(80,50,20,0.12)',
    ),
    'guizang_blueprint': _theme(
        'guizang_blueprint',
        'light',
        background='#e9f0fb',
        canvas='#f8fbff',
        surface='#ffffff',
        surface_alt='#dfe9f8',
        foreground='#102034',
        muted='#50647d',
        primary='#2155a6',
        secondary='#0ea5e9',
        accent='#2155a6',
        danger='#cf2e2e',
        success='#12805c',
        border='rgba(33,85,166,0.20)',
        style_tag='guizang_blueprint',
        background_variant='blueprint_grid',
        layout_frame='blueprint_frame',
        title_treatment='structured_sans',
        card_style='blueprint_card',
        ornament='axis_lines',
        density='balanced',
        radius=14,
        shadow='0 14px 30px rgba(16,32,52,0.12)',
    ),
    'guizang_business': _theme(
        'guizang_business',
        'light',
        background='#f6f4ef',
        canvas='#ffffff',
        surface='#ffffff',
        surface_alt='#eee9df',
        foreground='#1f2933',
        muted='#5c6672',
        primary='#274060',
        secondary='#b38b59',
        accent='#b38b59',
        danger='#b42318',
        success='#26734d',
        border='rgba(39,64,96,0.18)',
        style_tag='guizang_business',
        background_variant='executive_wash',
        layout_frame='business_frame',
        title_treatment='executive_sans',
        card_style='executive_card',
        ornament='thin_rules',
        density='airy',
        radius=12,
        shadow='0 18px 38px rgba(31,41,51,0.12)',
    ),
    'guizang_noir': _theme(
        'guizang_noir',
        'dark',
        background='#0b0a09',
        canvas='#11100e',
        surface='#1f1b16',
        surface_alt='#2b251e',
        foreground='#fbf7ef',
        muted='#d4c5ae',
        primary='#d6a85c',
        secondary='#a78bfa',
        accent='#d6a85c',
        danger='#ef4444',
        success='#84cc16',
        border='rgba(214,168,92,0.25)',
        style_tag='guizang_noir',
        background_variant='noir_spotlight',
        layout_frame='keynote_frame',
        title_treatment='premium_serif',
        card_style='noir_card',
        ornament='spotlight_rules',
        density='balanced',
        radius=16,
    ),
    # Backward-compatible public names.  They intentionally map into the same
    # visual family but keep visibly different composition tokens.
    'dark_tech': None,          # filled below
    'cyber_blue': None,
    'corporate_blue': None,
    'academic_light': None,
    'warm_editorial': None,
    'emerald_dark': None,
    'violet_neon': None,
    'midnight_gold': None,
    'light_magazine': None,
}

# Populate compatibility themes as deep copies with their public names.  This
# keeps existing schemas/tests stable while using the new design system.
_COMPAT_BASES = {
    'dark_tech': 'guizang_ink',
    'cyber_blue': 'guizang_aurora',
    'corporate_blue': 'guizang_blueprint',
    'academic_light': 'guizang_paper',
    'warm_editorial': 'guizang_paper',
    'emerald_dark': 'guizang_ink',
    'violet_neon': 'guizang_aurora',
    'midnight_gold': 'guizang_noir',
    'light_magazine': 'guizang_business',
}
_COMPAT_OVERRIDES = {
    'warm_editorial': {'primary': '#c25a1a', 'accent': '#d97706', 'secondary': '#9a4d19', 'background_variant': 'paper_warm', 'title_treatment': 'editorial_serif'},
    'emerald_dark': {'primary': '#34d399', 'accent': '#34d399', 'secondary': '#10b981', 'background': '#061a16', 'canvas': '#071f1a', 'surface': '#0e332b', 'surface_alt': '#15493d', 'style_tag': 'guizang_emerald', 'background_variant': 'botanic_mesh'},
    'violet_neon': {'primary': '#c084fc', 'accent': '#22d3ee', 'secondary': '#fb7185', 'background': '#150a22', 'canvas': '#1d1030', 'surface': '#2c1550', 'surface_alt': '#43206f', 'style_tag': 'guizang_violet', 'background_variant': 'aurora_mesh'},
    'light_magazine': {'primary': '#4f46e5', 'accent': '#ec4899', 'secondary': '#0ea5e9', 'background': '#f6f7fb', 'canvas': '#ffffff', 'style_tag': 'guizang_magazine', 'background_variant': 'paper_grid'},
}
for public_name, base_name in _COMPAT_BASES.items():
    item = deepcopy(_THEME_REGISTRY[base_name])
    item['name'] = public_name
    item.update(_COMPAT_OVERRIDES.get(public_name, {}))
    _THEME_REGISTRY[public_name] = item

SUPPORTED_HTML_DECK_THEMES = set(_THEME_REGISTRY.keys()) | {'auto'}

_THEME_ALIASES = {
    'default': 'auto',
    'adaptive': 'auto',
    'visual': 'auto',
    'guizang': 'guizang_ink',
    'ink': 'guizang_ink',
    '电子墨水': 'guizang_ink',
    'aurora': 'guizang_aurora',
    'paper': 'guizang_paper',
    'blueprint': 'guizang_blueprint',
    'business_guizang': 'guizang_business',
    'noir': 'guizang_noir',
    'tech': 'guizang_aurora',
    'dark': 'guizang_ink',
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
            'canvas': theme.get('canvas'),
            'surface': theme['surface'],
            'accent': theme['accent'],
            'foreground': theme['foreground'],
            'layout_frame': theme.get('layout_frame'),
            'background_variant': theme.get('background_variant'),
            'card_style': theme.get('card_style'),
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
    # Audience is stronger than incidental words inside slide titles.  For example,
    # a technical deck may contain a slide called "关键观点", but that should not
    # force the whole deck into editorial warm style.
    if audience in {'technical', 'demo'} or any(k in blob for k in ('ai', 'agent', 'rag', 'llm', 'infra', 'architecture', '技术', '科技', '系统')):
        return 'cyber_blue'
    if any(k in blob for k in ('产品', '商业', 'business', 'market', 'strategy', '融资', 'pitch')) or audience in {'business', 'product'}:
        return 'corporate_blue'
    if any(k in blob for k in ('增长', 'data', 'science', 'bio', 'drug', 'green', 'metrics heavy', '药物', '生物')):
        return 'emerald_dark'
    if any(k in blob for k in ('发布会', 'premium', 'gold', '战略发布', 'keynote')):
        return 'midnight_gold'
    if any(k in blob for k in ('创意', 'creative', 'neon', 'demo day', '未来感')):
        return 'violet_neon'
    if any(k in blob for k in ('warm', 'editorial', '观点', '叙事', '课程', '通识', '思想')) or 'editorial' in style:
        return 'warm_editorial'
    if 'dark' in style:
        return 'dark_tech'
    if 'light' in style:
        return 'light_magazine'
    return 'guizang_ink'


def _normalize_palette(palette: Any) -> Dict[str, Any]:
    if not isinstance(palette, Mapping):
        return {}
    allowed = {
        'background', 'canvas', 'surface', 'surface_alt', 'primary', 'secondary',
        'accent', 'foreground', 'muted', 'danger', 'success', 'border',
    }
    out: Dict[str, Any] = {}
    for key, value in palette.items():
        if key in allowed and value not in (None, ''):
            out[str(key)] = str(value)
    return out


def resolve_html_theme(theme: Any = None, *, deck_schema: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """Return a full theme dict.

    `theme` can be a string, or a dict like:
      {"base":"guizang_ink", "palette":{"accent":"#ff7a00"}}
    """
    palette: Dict[str, Any] = {}
    style_hint: Any = theme
    if isinstance(theme, Mapping):
        style_hint = theme.get('name') or theme.get('base') or theme.get('theme') or theme.get('visual_theme') or 'auto'
        palette = _normalize_palette(theme.get('palette') or theme)

    theme_name = infer_html_theme_name(deck_schema, style_hint)
    base = deepcopy(_THEME_REGISTRY.get(theme_name) or _THEME_REGISTRY['guizang_ink'])
    base.update(palette)
    base['name'] = theme_name
    base['resolved_from'] = str(style_hint or 'auto')
    if palette:
        base['palette_override'] = palette
    return base
