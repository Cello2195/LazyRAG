from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

_PLACEHOLDER_RE = re.compile(r'(lorem ipsum|placeholder|todo|tbd|xxxx|待补充)', re.IGNORECASE)
_IMG_RE = re.compile(r'<img\s+[^>]*src=["\']([^"\']+)["\']', re.IGNORECASE)
_TITLE_TAG_RE = re.compile(r'<h[1-3][^>]*>(.*?)</h[1-3]>', re.IGNORECASE | re.DOTALL)
_TEXT_RE = re.compile(r'<[^>]+>')
_HEX_RE = re.compile(r'#[0-9a-fA-F]{3,8}')
_CDN_RE = re.compile(
    r'''<(?:script|link)[^>]+(?:src|href)=["']https?://[^"']+["']''',
    re.IGNORECASE,
)


def _entry(level: str, code: str, message: str, slide: int | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {'level': level, 'code': code, 'message': message}
    if slide is not None:
        payload['slide_index'] = slide
    return payload


def _resolve_slide_paths(
    deck_dir: str | Path | None = None,
    slide_paths: Iterable[str] | None = None,
) -> List[Path]:
    if slide_paths:
        return [Path(p).expanduser().resolve() for p in slide_paths]
    if deck_dir:
        directory = Path(deck_dir).expanduser().resolve()
        return sorted(p for p in directory.glob('slide-*.html') if p.is_file())
    return []


def _extract_text(content: str) -> str:
    no_script = re.sub(r'<script[\s\S]*?</script>', ' ', content, flags=re.IGNORECASE)
    no_style = re.sub(r'<style[\s\S]*?</style>', ' ', no_script, flags=re.IGNORECASE)
    plain = _TEXT_RE.sub(' ', no_style)
    return re.sub(r'\s+', ' ', plain).strip()


def _extract_title(content: str) -> str:
    match = _TITLE_TAG_RE.search(content)
    if not match:
        return ''
    title = _extract_text(match.group(1))
    return title[:120]


def _missing_image_paths(html_path: Path, content: str) -> List[str]:
    missing: List[str] = []
    for src in _IMG_RE.findall(content):
        if src.startswith(('http://', 'https://', 'data:')):
            continue
        candidate = (html_path.parent / src).resolve()
        if not candidate.exists():
            missing.append(src)
    return missing


def _has_slide_container(content: str) -> bool:
    return ('class="slide-content"' in content) or ("class='slide-content'" in content)


def _looks_blank(text: str, image_count: int) -> bool:
    return len(text.strip()) < 12 and image_count == 0


def _collect_layout_name(content: str) -> str:
    m = re.search(r'<small>([^<]+)</small>', content)
    if m:
        return _extract_text(m.group(1)).strip()
    return ''


def _is_mostly_monochrome(slide_contents: List[str]) -> bool:
    colors = set()
    for content in slide_contents[:3]:
        for item in _HEX_RE.findall(content):
            colors.add(item.lower())
    if not colors:
        return True
    # If only black/white-ish values appear, visual richness is likely weak.
    dark_light = {
        '#000',
        '#000000',
        '#111',
        '#111111',
        '#fff',
        '#ffffff',
        '#f8f8f8',
        '#f9f9f9',
        '#fafafa',
    }
    return colors.issubset(dark_light) and len(colors) <= 4


def _load_manifest(deck_dir: Path | None) -> Dict[str, Any]:
    if deck_dir is None:
        return {}
    manifest = deck_dir / 'manifest.json'
    if not manifest.exists():
        return {}
    try:
        return json.loads(manifest.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _check_screenshot_blank(path: Path) -> bool:
    try:
        from PIL import Image, ImageStat  # type: ignore

        with Image.open(path) as img:
            gray = img.convert('L')
            stat = ImageStat.Stat(gray)
            if not stat.stddev:
                return True
            # Very low contrast can indicate nearly blank rendering.
            return float(stat.stddev[0]) < 1.2
    except Exception:
        # Fallback: tiny files are suspicious.
        return path.stat().st_size < 16_000


def _check_screenshots(
    screenshot_result: Dict[str, Any] | None,
    slide_count: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    issues: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    details: List[Dict[str, Any]] = []
    if not screenshot_result:
        return issues, warnings, details
    if not screenshot_result.get('success'):
        warnings.append(
            _entry(
                'warning',
                'screenshot_unavailable',
                screenshot_result.get('error_message') or 'screenshot rendering unavailable',
            )
        )
        return issues, warnings, details

    paths = [Path(p).expanduser().resolve() for p in screenshot_result.get('screenshot_paths') or []]
    if len(paths) != slide_count:
        warnings.append(
            _entry(
                'warning',
                'screenshot_count_mismatch',
                f'screenshot count={len(paths)} but slide count={slide_count}',
            )
        )
    for idx, path in enumerate(paths, start=1):
        item = {'slide_index': idx, 'file_path': str(path), 'issues': [], 'warnings': []}
        if not path.exists():
            issue = _entry('error', 'missing_screenshot', f'screenshot not found: {path}', idx)
            issues.append(issue)
            item['issues'].append(issue)
            details.append(item)
            continue
        size_bytes = path.stat().st_size
        item['size_bytes'] = size_bytes
        if size_bytes < 16_000:
            warning = _entry('warning', 'screenshot_too_small', f'screenshot too small: {path.name}', idx)
            warnings.append(warning)
            item['warnings'].append(warning)
        if _check_screenshot_blank(path):
            warning = _entry('warning', 'screenshot_near_blank', f'screenshot may be near blank: {path.name}', idx)
            warnings.append(warning)
            item['warnings'].append(warning)
        details.append(item)
    return issues, warnings, details


def run_html_deck_qa(
    deck_dir: str | Path | None = None,
    slide_paths: Iterable[str] | None = None,
    screenshot_result: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    resolved_deck_dir: Path | None = Path(deck_dir).expanduser().resolve() if deck_dir else None
    paths = _resolve_slide_paths(deck_dir, slide_paths)
    issues: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    details: List[Dict[str, Any]] = []
    raw_slides: List[str] = []
    layout_names: set[str] = set()

    if resolved_deck_dir and not resolved_deck_dir.exists():
        issues.append(_entry('error', 'missing_deck_dir', f'deck_dir not found: {resolved_deck_dir}'))

    if resolved_deck_dir:
        index_path = resolved_deck_dir / 'index.html'
        if not index_path.exists():
            issues.append(_entry('error', 'missing_index', f'index.html not found under {resolved_deck_dir}'))
        elif index_path.stat().st_size < 800:
            warnings.append(_entry('warning', 'index_too_small', 'index.html is unexpectedly small'))

    if not paths:
        issues.append(_entry('error', 'no_slides', 'no slide HTML files found'))

    manifest = _load_manifest(resolved_deck_dir)
    theme_used = manifest.get('theme_used') or ''
    manifest_layouts = manifest.get('layout_summary') if isinstance(manifest.get('layout_summary'), dict) else {}
    for key in manifest_layouts.keys():
        key_text = str(key).strip()
        if key_text:
            layout_names.add(key_text)

    for idx, path in enumerate(paths, start=1):
        slide_detail: Dict[str, Any] = {'slide_index': idx, 'file_path': str(path), 'issues': [], 'warnings': []}
        if not path.exists():
            issue = _entry('error', 'missing_slide_file', f'slide file not found: {path}', idx)
            issues.append(issue)
            slide_detail['issues'].append(issue)
            details.append(slide_detail)
            continue

        content = path.read_text(encoding='utf-8', errors='ignore')
        raw_slides.append(content)
        size_bytes = path.stat().st_size
        text = _extract_text(content)
        title = _extract_title(content)
        image_refs = _IMG_RE.findall(content)
        missing_images = _missing_image_paths(path, content)
        has_external_cdn = bool(_CDN_RE.search(content))
        layout = _collect_layout_name(content)
        if layout:
            layout_names.add(layout)

        slide_detail.update(
            {
                'size_bytes': size_bytes,
                'html_length': len(content),
                'text_len': len(text),
                'title': title,
                'image_ref_count': len(image_refs),
                'layout': layout,
            }
        )

        if size_bytes < 1200:
            warning = _entry('warning', 'slide_html_too_small', 'slide HTML is unexpectedly small', idx)
            warnings.append(warning)
            slide_detail['warnings'].append(warning)
        if not _has_slide_container(content):
            issue = _entry('error', 'missing_slide_container', 'slide lacks .slide-content container', idx)
            issues.append(issue)
            slide_detail['issues'].append(issue)
        if _PLACEHOLDER_RE.search(content):
            issue = _entry('error', 'placeholder_residue', 'slide contains placeholder-like text', idx)
            issues.append(issue)
            slide_detail['issues'].append(issue)
        if missing_images:
            issue = _entry(
                'error',
                'missing_image_asset',
                f'missing image assets: {missing_images[:3]}',
                idx,
            )
            issues.append(issue)
            slide_detail['issues'].append(issue)
        if has_external_cdn:
            warning = _entry(
                'warning',
                'external_cdn_reference',
                'external CDN/script reference found; offline rendering may break',
                idx,
            )
            warnings.append(warning)
            slide_detail['warnings'].append(warning)
        if not title:
            warning = _entry('warning', 'missing_title', 'slide title heading not found', idx)
            warnings.append(warning)
            slide_detail['warnings'].append(warning)
        if _looks_blank(text, len(image_refs)):
            issue = _entry('error', 'blank_slide', 'slide appears blank', idx)
            issues.append(issue)
            slide_detail['issues'].append(issue)
        if len(text) > 1400:
            warning = _entry('warning', 'text_too_long', f'slide text is too long ({len(text)} chars)', idx)
            warnings.append(warning)
            slide_detail['warnings'].append(warning)
        # Very rough density signal for heavy slides.
        line_max = max((len(line.strip()) for line in text.split(' ') if line.strip()), default=0)
        if line_max > 180:
            warning = _entry('warning', 'long_token', 'slide contains unusually long unbroken text', idx)
            warnings.append(warning)
            slide_detail['warnings'].append(warning)

        details.append(slide_detail)

    if not theme_used:
        warnings.append(_entry('warning', 'theme_missing', 'theme_used is not recorded in manifest'))

    if len(paths) > 2 and len(layout_names) <= 1:
        warnings.append(_entry('warning', 'layout_repetition', 'all slides use almost the same layout'))

    if raw_slides and _is_mostly_monochrome(raw_slides):
        warnings.append(
            _entry(
                'warning',
                'visual_monotone',
                'visual style may be too monotone (near white/black-only color usage)',
            )
        )

    shot_issues, shot_warnings, shot_details = _check_screenshots(screenshot_result, len(paths))
    issues.extend(shot_issues)
    warnings.extend(shot_warnings)
    if shot_details:
        details.append({'screenshots': shot_details})

    return {
        'success': True,
        'passed': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'details': details,
        'summary': {
            'slide_count': len(paths),
            'issue_count': len(issues),
            'warning_count': len(warnings),
            'theme_used': theme_used or None,
            'layout_count': len(layout_names),
        },
    }
