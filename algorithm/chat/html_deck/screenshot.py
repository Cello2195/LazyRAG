from __future__ import annotations

import subprocess
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List


def _resolve_slide_paths(deck_dir: str | Path | None = None, slide_paths: Iterable[str] | None = None) -> List[Path]:
    if slide_paths:
        paths = [Path(p).expanduser().resolve() for p in slide_paths]
    elif deck_dir:
        paths = sorted(Path(deck_dir).expanduser().resolve().glob('slide-*.html'))
    else:
        paths = []
    return [p for p in paths if p.exists() and p.is_file()]


def _hex_to_rgb(value: str, default: tuple[int, int, int]) -> tuple[int, int, int]:
    text = str(value or '').strip().lstrip('#')
    if len(text) == 3:
        text = ''.join(ch * 2 for ch in text)
    if len(text) != 6:
        return default
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except Exception:
        return default


def _strip_html(text: str) -> str:
    text = re.sub(r'<script[\s\S]*?</script>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<style[\s\S]*?</style>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _pick_theme_colors(html_text: str) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    bg = '#0f172a'
    fg = '#f8fafc'
    accent = '#38bdf8'
    m_bg = re.search(r'background:\s*(#[0-9a-fA-F]{3,8})', html_text)
    m_fg = re.search(r'color:\s*(#[0-9a-fA-F]{3,8})', html_text)
    m_ac = re.search(r'title-rule[^}]+background:\s*(#[0-9a-fA-F]{3,8})', html_text)
    if m_bg:
        bg = m_bg.group(1)
    if m_fg:
        fg = m_fg.group(1)
    if m_ac:
        accent = m_ac.group(1)
    return _hex_to_rgb(bg, (15, 23, 42)), _hex_to_rgb(fg, (248, 250, 252)), _hex_to_rgb(accent, (56, 189, 248))


def _wrap_text(text: str, limit: int = 34) -> List[str]:
    value = str(text or '').strip()
    if not value:
        return []
    lines: List[str] = []
    while len(value) > limit:
        lines.append(value[:limit].rstrip())
        value = value[limit:].lstrip()
    if value:
        lines.append(value)
    return lines


def _load_font(size: int):
    try:
        from PIL import ImageFont  # type: ignore

        candidates = [
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        ]
        for path in candidates:
            p = Path(path)
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), size=size)
                except Exception:
                    continue
        return ImageFont.load_default()
    except Exception:
        return None


def _render_fallback_pngs(
    slides: List[Path],
    out_dir: Path,
    width: int,
    height: int,
) -> Dict[str, Any]:
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except Exception as exc:
        return {
            'success': False,
            'slide_paths': [str(p) for p in slides],
            'screenshot_paths': [],
            'page_count': 0,
            'warnings': ['Pillow unavailable for fallback screenshot rendering'],
            'error_message': f'fallback renderer unavailable: {exc}',
        }

    title_font = _load_font(40)
    body_font = _load_font(24)
    small_font = _load_font(16)

    screenshots: List[str] = []
    for idx, slide in enumerate(slides, start=1):
        html_text = slide.read_text(encoding='utf-8', errors='ignore')
        bg, fg, accent = _pick_theme_colors(html_text)
        title_match = re.search(r'<h[1-3][^>]*>(.*?)</h[1-3]>', html_text, re.IGNORECASE | re.DOTALL)
        title = _strip_html(title_match.group(1)) if title_match else f'Slide {idx:02d}'
        li_matches = re.findall(r'<li[^>]*>(.*?)</li>', html_text, re.IGNORECASE | re.DOTALL)
        bullets = [_strip_html(item) for item in li_matches if _strip_html(item)]
        subtitle_match = re.search(r'<p[^>]*class=["\'][^"\']*(?:subtitle|intro)[^"\']*["\'][^>]*>(.*?)</p>', html_text, re.IGNORECASE | re.DOTALL)
        subtitle = _strip_html(subtitle_match.group(1)) if subtitle_match else ''

        img = Image.new('RGB', (width, height), bg)
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, width, 58), fill=(max(bg[0] - 8, 0), max(bg[1] - 8, 0), max(bg[2] - 8, 0)))
        draw.rectangle((36, 88, 260, 95), fill=accent)
        draw.text((36, 112), title[:48], fill=fg, font=title_font)
        if subtitle:
            draw.text((36, 164), subtitle[:72], fill=fg, font=small_font)

        y = 220
        max_lines = 10
        used = 0
        lines_source = bullets or [_strip_html(html_text)[:300]]
        for item in lines_source[:8]:
            for line in _wrap_text(item, 34):
                if used >= max_lines:
                    break
                draw.text((58, y), f'• {line}', fill=fg, font=body_font)
                y += 30
                used += 1
            if used >= max_lines:
                break
        draw.text((width - 120, height - 30), f'{idx:02d}/{len(slides):02d}', fill=accent, font=small_font)

        target = out_dir / f'slide-{idx:02d}.png'
        img.save(target, format='PNG')
        screenshots.append(str(target))

    return {
        'success': True,
        'slide_paths': [str(p) for p in slides],
        'screenshot_paths': screenshots,
        'page_count': len(screenshots),
        'output_dir': str(out_dir),
        'viewport_width': int(width),
        'viewport_height': int(height),
        'device_scale_factor': 1.0,
        'warnings': [
            'Playwright screenshot fallback mode is used (Pillow renderer); visuals may differ from browser rendering.'
        ],
        'error_message': '',
        'fallback_used': True,
    }


def _missing_playwright_result(error_message: str, slides: List[Path]) -> Dict[str, Any]:
    warnings = [
        'Playwright/Chromium unavailable. HTML deck generation is still valid.',
    ]
    if 'missing system libraries' in str(error_message):
        warnings.append(
            'Chromium is installed but OS libraries are missing. Try: python -m playwright install-deps chromium'
        )
    else:
        warnings.append(
            'Install runtime with: python -m playwright install chromium (or playwright install chromium)'
        )
    return {
        'success': False,
        'slide_paths': [str(p) for p in slides],
        'screenshot_paths': [],
        'page_count': len(slides),
        'warnings': warnings,
        'error_message': error_message,
    }


def _find_chromium_binaries() -> List[Path]:
    base = Path.home() / '.cache' / 'ms-playwright'
    candidates: List[Path] = []
    if not base.exists():
        return candidates
    patterns = [
        'chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell',
        'chromium-*/chrome-linux/chrome',
    ]
    for pattern in patterns:
        for item in sorted(base.glob(pattern)):
            if item.exists() and item.is_file():
                candidates.append(item)
    return candidates


def _preflight_browser_runtime_error() -> str:
    binaries = _find_chromium_binaries()
    if not binaries:
        return 'Playwright Chromium runtime not found. Run: python -m playwright install chromium'
    target = binaries[0]
    try:
        proc = subprocess.run(
            ['ldd', str(target)],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
    except Exception:
        return ''
    output = f'{proc.stdout}\n{proc.stderr}'
    missing = []
    for line in output.splitlines():
        line = line.strip()
        if '=> not found' in line:
            missing.append(line.split('=>', 1)[0].strip())
    if missing:
        top = ', '.join(missing[:6])
        return f'Chromium runtime missing system libraries: {top}'
    return ''


def render_html_deck_screenshots(
    deck_dir: str | Path | None = None,
    slide_paths: Iterable[str] | None = None,
    output_dir: str | Path | None = None,
    *,
    viewport_width: int = 960,
    viewport_height: int = 540,
    device_scale_factor: float = 2.0,
    timeout_ms: int = 20000,
    allow_fallback: bool = True,
) -> Dict[str, Any]:
    slides = _resolve_slide_paths(deck_dir, slide_paths)
    if not slides:
        return {
            'success': False,
            'slide_paths': [],
            'screenshot_paths': [],
            'page_count': 0,
            'warnings': ['no HTML slides found for screenshot rendering'],
            'error_message': 'no HTML slides found',
        }

    out_dir = Path(output_dir).expanduser().resolve() if output_dir else slides[0].parent / 'screenshots'
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover
        if allow_fallback:
            fallback = _render_fallback_pngs(slides, out_dir, int(viewport_width), int(viewport_height))
            if fallback.get('success'):
                fallback['warnings'] = [f'Playwright import failed: {exc}'] + (fallback.get('warnings') or [])
                return fallback
        return _missing_playwright_result(f'playwright import failed: {exc}', slides)

    preflight_error = _preflight_browser_runtime_error()
    if preflight_error:
        if allow_fallback:
            fallback = _render_fallback_pngs(slides, out_dir, int(viewport_width), int(viewport_height))
            if fallback.get('success'):
                fallback['warnings'] = [preflight_error] + (fallback.get('warnings') or [])
                return fallback
        return _missing_playwright_result(preflight_error, slides)

    screenshot_paths: List[Path] = []
    warnings: List[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, timeout=15000)
            context = browser.new_context(
                viewport={'width': int(viewport_width), 'height': int(viewport_height)},
                device_scale_factor=float(device_scale_factor),
            )
            page = context.new_page()
            for idx, slide in enumerate(slides, start=1):
                target = out_dir / f'slide-{idx:02d}.png'
                page.goto(slide.as_uri(), wait_until='domcontentloaded', timeout=timeout_ms)
                page.wait_for_timeout(120)
                page.screenshot(
                    path=str(target),
                    type='png',
                    full_page=False,
                    clip={
                        'x': 0,
                        'y': 0,
                        'width': int(viewport_width),
                        'height': int(viewport_height),
                    },
                )
                screenshot_paths.append(target)
            context.close()
            browser.close()
    except Exception as exc:  # pragma: no cover
        if allow_fallback:
            fallback = _render_fallback_pngs(slides, out_dir, int(viewport_width), int(viewport_height))
            if fallback.get('success'):
                fallback['warnings'] = [f'Playwright rendering failed: {exc}'] + (fallback.get('warnings') or [])
                return fallback
        return _missing_playwright_result(f'html screenshot rendering failed: {exc}', slides)

    for shot in screenshot_paths:
        if not shot.exists() or shot.stat().st_size < 1024:
            warnings.append(f'screenshot may be invalid: {shot}')

    return {
        'success': True,
        'slide_paths': [str(p) for p in slides],
        'screenshot_paths': [str(p) for p in screenshot_paths],
        'page_count': len(screenshot_paths),
        'output_dir': str(out_dir),
        'viewport_width': int(viewport_width),
        'viewport_height': int(viewport_height),
        'device_scale_factor': float(device_scale_factor),
        'warnings': warnings,
        'error_message': '',
        'fallback_used': False,
    }
