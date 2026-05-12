from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

_PLACEHOLDER_RE = re.compile(r'(lorem ipsum|placeholder|todo|tbd|xxxx|待补充)', re.IGNORECASE)
_PLACEHOLDER_LABEL_RE = re.compile(
    r'(?<!\w)(column\s*1|column\s*2|point\s*1|point\s*2|todo|tbd|lorem ipsum)(?!\w)|占位|待补充|待完善',
    re.IGNORECASE,
)
_PLACEHOLDER_HEADING_RE = re.compile(
    r'<h[1-6][^>]*>\s*(left|right|column\s*1|column\s*2|point\s*1|point\s*2)\s*</h[1-6]>',
    re.IGNORECASE,
)
_IMG_RE = re.compile(r'<img\s+[^>]*src=["\']([^"\']+)["\']', re.IGNORECASE)
_TITLE_TAG_RE = re.compile(r'<h[1-3][^>]*>(.*?)</h[1-3]>', re.IGNORECASE | re.DOTALL)
_TEXT_RE = re.compile(r'<[^>]+>')
_HEX_RE = re.compile(r'#[0-9a-fA-F]{3,8}')
_LAYOUT_ATTR_RE = re.compile(r'data-layout=["\']([^"\']+)["\']', re.IGNORECASE)
_LI_RE = re.compile(r'<li\b[^>]*>(.*?)</li>', re.IGNORECASE | re.DOTALL)
_TR_RE = re.compile(r'<tr\b[^>]*>', re.IGNORECASE)
_ARTICLE_RE = re.compile(r'<article\b[^>]*>', re.IGNORECASE)
_CDN_RE = re.compile(
    r'''<(?:script|link)[^>]+(?:src|href)=["']https?://[^"']+["']''',
    re.IGNORECASE,
)
_RELAXED_LAYOUTS = {'cover_hero', 'toc_numbered', 'section_divider', 'references'}
_STRUCTURAL_LAYOUTS = {
    'content_bullets',
    'summary',
    'metric_cards',
    'challenge_cards',
    'two_column',
    'comparison',
    'table',
    'process',
    'timeline',
}


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


def _extract_layout_id(content: str) -> str:
    match = _LAYOUT_ATTR_RE.search(content)
    if not match:
        return ''
    return str(match.group(1) or '').strip().lower()


def _extract_body_text(text: str, title: str) -> str:
    full = str(text or '').strip()
    if not full:
        return ''
    title_clean = str(title or '').strip()
    if title_clean:
        full = full.replace(title_clean, '', 1).strip()
    return full


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
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], bool]:
    issues: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    details: List[Dict[str, Any]] = []
    export_ready = False
    if not screenshot_result:
        return issues, warnings, details, export_ready
    fallback_used = bool(screenshot_result.get('fallback_used'))
    real_browser = screenshot_result.get('is_real_browser_render') is True
    can_export = screenshot_result.get('can_export_visual_pptx') is True
    if fallback_used:
        warnings.append(
            _entry(
                'warning',
                'fallback_screenshot_used',
                'Pillow fallback preview detected; this is not acceptable for formal visual_pptx export',
            )
        )
    if not can_export:
        warnings.append(
            _entry(
                'warning',
                'visual_export_not_ready',
                'screenshot result is not export-ready for visual_pptx',
            )
        )
    if not screenshot_result.get('success'):
        warnings.append(
            _entry(
                'warning',
                'screenshot_unavailable',
                screenshot_result.get('error_message') or 'screenshot rendering unavailable',
            )
        )
        return issues, warnings, details, export_ready

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
    export_ready = bool(
        screenshot_result.get('success')
        and real_browser
        and (not fallback_used)
        and can_export
        and not issues
    )
    return issues, warnings, details, export_ready


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
        body_text = _extract_body_text(text, title)
        image_refs = _IMG_RE.findall(content)
        missing_images = _missing_image_paths(path, content)
        has_external_cdn = bool(_CDN_RE.search(content))
        layout = _collect_layout_name(content)
        layout_id = _extract_layout_id(content) or layout
        list_item_count = len(_LI_RE.findall(content))
        table_row_count = max(0, len(_TR_RE.findall(content)) - 1)
        article_count = len(_ARTICLE_RE.findall(content))
        if layout:
            layout_names.add(layout)
        if layout_id:
            layout_names.add(layout_id)

        slide_detail.update(
            {
                'size_bytes': size_bytes,
                'html_length': len(content),
                'text_len': len(text),
                'body_text_len': len(body_text),
                'title': title,
                'image_ref_count': len(image_refs),
                'layout': layout,
                'layout_id': layout_id,
                'list_item_count': list_item_count,
                'table_row_count': table_row_count,
                'article_count': article_count,
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
        if _PLACEHOLDER_HEADING_RE.search(content) or _PLACEHOLDER_LABEL_RE.search(body_text):
            issue = _entry('error', 'placeholder_label', 'slide contains placeholder labels such as Left/Right/Point 1', idx)
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

        relaxed_layout = layout_id in _RELAXED_LAYOUTS
        if not relaxed_layout:
            if len(body_text) < 80:
                issue = _entry('error', 'sparse_rendered_slide', 'Rendered slide contains too little body text.', idx)
                issues.append(issue)
                slide_detail['issues'].append(issue)

            if layout_id == 'metric_cards':
                has_substantive_structure = bool(
                    article_count >= 2
                    or list_item_count >= 2
                    or len(body_text) >= 80
                )
            else:
                has_substantive_structure = bool(
                    list_item_count >= 3
                    or table_row_count >= 3
                    or article_count >= 3
                )
            if not has_substantive_structure:
                issue = _entry(
                    'error',
                    'too_few_list_items',
                    'Rendered body slide has too few list/table/card items to be substantive.',
                    idx,
                )
                issues.append(issue)
                slide_detail['issues'].append(issue)

            if layout_id in _STRUCTURAL_LAYOUTS and not has_substantive_structure:
                issue = _entry(
                    'error',
                    'empty_structural_slide',
                    'Slide uses structural layout but content is mostly empty.',
                    idx,
                )
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

    html_passed = len(issues) == 0
    shot_issues, shot_warnings, shot_details, export_ready = _check_screenshots(screenshot_result, len(paths))
    issues.extend(shot_issues)
    warnings.extend(shot_warnings)
    if shot_details:
        details.append({'screenshots': shot_details})

    return {
        'success': True,
        'passed': len(issues) == 0,
        'html_passed': html_passed,
        'export_ready': export_ready,
        'issues': issues,
        'warnings': warnings,
        'details': details,
        'summary': {
            'slide_count': len(paths),
            'issue_count': len(issues),
            'warning_count': len(warnings),
            'theme_used': theme_used or None,
            'layout_count': len(layout_names),
            'html_passed': html_passed,
            'export_ready': export_ready,
        },
    }
