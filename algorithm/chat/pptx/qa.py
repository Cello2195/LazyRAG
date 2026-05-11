from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .parser import parse_pptx
from .schema import normalize_deck_schema

_PLACEHOLDER_RE = re.compile(r'(lorem ipsum|placeholder|todo|tbd|xxxx|待补充)', re.IGNORECASE)
_MAX_TEXT_LEN_PER_SLIDE = 1500
_MAX_BULLETS_PER_SLIDE = 8
_MAX_LINE_LEN = 170
_MAX_SHAPES_PER_SLIDE = 45
_MIN_FONT_SIZE = 8.0
_MAX_TABLE_ROWS = 12
_MAX_TABLE_COLS = 7
_MIN_FILE_SIZE_BYTES = 4 * 1024


def _entry(level: str, code: str, message: str, slide_index: int | None = None, **extra: Any) -> Dict[str, Any]:
    payload = {
        'level': level,
        'code': code,
        'message': message,
        'slide_index': slide_index,
    }
    payload.update(extra)
    return payload


def _normalize_text(value: Any) -> str:
    text = str(value or '').strip().lower()
    return re.sub(r'\s+', ' ', text)


def _schema_expected_text(deck_schema: Any) -> List[Dict[str, Any]]:
    if not deck_schema:
        return []
    deck = normalize_deck_schema(deck_schema)
    expected: List[Dict[str, Any]] = []
    for idx, slide in enumerate(deck.get('slides') or [], start=1):
        texts = [
            slide.get('title') or '',
            slide.get('subtitle') or '',
        ]
        texts.extend(slide.get('bullets') or [])
        texts.extend(slide.get('items') or [])
        texts.extend(slide.get('takeaways') or [])
        if isinstance(slide.get('left'), dict):
            texts.append(slide['left'].get('title') or '')
            texts.extend(slide['left'].get('bullets') or [])
        if isinstance(slide.get('right'), dict):
            texts.append(slide['right'].get('title') or '')
            texts.extend(slide['right'].get('bullets') or [])
        if isinstance(slide.get('table'), dict):
            texts.extend(slide['table'].get('headers') or [])
            for row in slide['table'].get('rows') or []:
                texts.extend(row)
        expected.append({'index': idx, 'texts': [str(t).strip() for t in texts if str(t).strip()]})
    return expected


def _check_thumbnail_result(
    thumbnail_result: Dict[str, Any],
    *,
    expected_slides: int,
    issues: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]],
) -> None:
    if not isinstance(thumbnail_result, dict):
        return

    if not thumbnail_result.get('success'):
        warnings.append(
            _entry(
                'warning',
                'thumbnail_unavailable',
                thumbnail_result.get('error_message') or 'thumbnail generation unavailable',
            )
        )
        return

    paths = thumbnail_result.get('thumbnail_paths') or []
    page_count = int(thumbnail_result.get('page_count') or len(paths) or 0)

    if page_count == 0:
        warnings.append(_entry('warning', 'thumbnail_empty', 'thumbnail result contains zero pages'))

    if expected_slides > 0 and page_count != expected_slides:
        warnings.append(
            _entry(
                'warning',
                'thumbnail_page_count_mismatch',
                f'thumbnail page_count={page_count}, slide_count={expected_slides}',
            )
        )

    for path in paths:
        p = Path(str(path))
        if not p.exists() or not p.is_file():
            issues.append(_entry('error', 'thumbnail_missing_file', f'thumbnail missing: {p}'))
            continue
        if p.stat().st_size < 1024:
            warnings.append(_entry('warning', 'thumbnail_too_small', f'thumbnail may be invalid: {p}'))


def run_pptx_qa(
    file_path: str | Path,
    deck_schema: Optional[Any] = None,
    parse_result: Optional[Dict[str, Any]] = None,
    thumbnail_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run deterministic QA checks for PPTX quality and structural health."""
    path = Path(file_path).expanduser().resolve()
    issues: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    details: List[Dict[str, Any]] = []

    if not path.exists() or not path.is_file():
        issues.append(_entry('error', 'file_not_found', f'PPTX file not found: {path}'))
        return {
            'success': False,
            'passed': False,
            'issues': issues,
            'warnings': warnings,
            'summary': {
                'slide_count': 0,
                'issue_count': len(issues),
                'warning_count': len(warnings),
            },
            'details': details,
            'file_path': str(path),
        }

    file_size = path.stat().st_size
    if file_size < _MIN_FILE_SIZE_BYTES:
        issues.append(_entry('error', 'file_too_small', f'PPTX file is suspiciously small: {file_size} bytes'))

    try:
        parsed = parse_result if isinstance(parse_result, dict) else parse_pptx(path)
    except Exception as exc:
        issues.append(_entry('error', 'open_failed', f'Failed to open PPTX with python-pptx: {exc}'))
        return {
            'success': False,
            'passed': False,
            'issues': issues,
            'warnings': warnings,
            'summary': {
                'slide_count': 0,
                'issue_count': len(issues),
                'warning_count': len(warnings),
            },
            'details': details,
            'file_path': str(path),
        }

    slides = parsed.get('slides') or []
    slide_count = int(parsed.get('slide_count') or len(slides))

    if slide_count <= 0:
        issues.append(_entry('error', 'no_slides', 'PPTX contains no slides'))

    expected = _schema_expected_text(deck_schema) if deck_schema is not None else []
    if expected and len(expected) != slide_count:
        issues.append(
            _entry(
                'error',
                'slide_count_mismatch',
                f'Expected {len(expected)} slides from schema, got {slide_count}',
            )
        )

    for slide in slides:
        idx = int(slide.get('index') or 0)
        title = str(slide.get('title') or '').strip()
        text = str(slide.get('text') or '')
        shape_count = int(slide.get('shape_count') or 0)
        bullet_count = int(slide.get('bullet_count') or 0)
        max_line_len = int(slide.get('max_line_len') or 0)
        min_font_size = slide.get('min_font_size')
        table_count = int(slide.get('table_count') or 0)
        max_table_rows = int(slide.get('max_table_rows') or 0)
        max_table_cols = int(slide.get('max_table_cols') or 0)

        slide_details = {
            'slide_index': idx,
            'title': title,
            'text_len': len(text),
            'shape_count': shape_count,
            'bullet_count': bullet_count,
            'max_line_len': max_line_len,
            'min_font_size': min_font_size,
            'table_count': table_count,
            'max_table_rows': max_table_rows,
            'max_table_cols': max_table_cols,
            'issues': [],
            'warnings': [],
        }

        if slide.get('is_empty'):
            issue = _entry('error', 'empty_slide', 'Slide is empty', idx)
            issues.append(issue)
            slide_details['issues'].append(issue)

        if not title:
            warning = _entry('warning', 'missing_title', 'Slide title is missing', idx)
            warnings.append(warning)
            slide_details['warnings'].append(warning)

        if _PLACEHOLDER_RE.search(text):
            issue = _entry('error', 'placeholder_residue', 'Slide still contains placeholder text', idx)
            issues.append(issue)
            slide_details['issues'].append(issue)

        if len(text) > _MAX_TEXT_LEN_PER_SLIDE:
            warning = _entry('warning', 'text_too_long', 'Slide text may be too dense for readability', idx)
            warnings.append(warning)
            slide_details['warnings'].append(warning)

        if bullet_count > _MAX_BULLETS_PER_SLIDE:
            warning = _entry('warning', 'too_many_bullets', f'Slide has {bullet_count} bullets', idx)
            warnings.append(warning)
            slide_details['warnings'].append(warning)

        if max_line_len > _MAX_LINE_LEN:
            warning = _entry('warning', 'line_too_long', f'Slide has an overlong line length={max_line_len}', idx)
            warnings.append(warning)
            slide_details['warnings'].append(warning)

        if min_font_size is not None and float(min_font_size) < _MIN_FONT_SIZE:
            warning = _entry('warning', 'font_too_small', f'Slide has very small text ({min_font_size}pt)', idx)
            warnings.append(warning)
            slide_details['warnings'].append(warning)

        if shape_count > _MAX_SHAPES_PER_SLIDE:
            warning = _entry('warning', 'too_many_shapes', f'Slide has {shape_count} shapes', idx)
            warnings.append(warning)
            slide_details['warnings'].append(warning)

        if table_count > 0 and (max_table_rows > _MAX_TABLE_ROWS or max_table_cols > _MAX_TABLE_COLS):
            warning = _entry(
                'warning',
                'table_too_dense',
                f'Table shape may be too dense (rows={max_table_rows}, cols={max_table_cols})',
                idx,
            )
            warnings.append(warning)
            slide_details['warnings'].append(warning)

        for shape in slide.get('shapes') or []:
            bbox = shape.get('bbox') or {}
            x = float(bbox.get('x') or 0)
            y = float(bbox.get('y') or 0)
            w = float(bbox.get('w') or 0)
            h = float(bbox.get('h') or 0)
            if w <= 0 or h <= 0:
                warning = _entry('warning', 'shape_invalid_size', 'Shape has non-positive width/height', idx, shape=shape.get('name'))
                warnings.append(warning)
                slide_details['warnings'].append(warning)
                break
            if bool(shape.get('is_out_of_bounds')):
                warning = _entry('warning', 'shape_out_of_bounds', 'Shape may exceed slide bounds', idx, shape=shape.get('name'))
                warnings.append(warning)
                slide_details['warnings'].append(warning)
                break

        details.append(slide_details)

    if expected:
        for item in expected[:slide_count]:
            slide_idx = int(item['index'])
            actual = slides[slide_idx - 1] if slide_idx - 1 < len(slides) else {}
            actual_text = _normalize_text(actual.get('text') or '')
            actual_title = _normalize_text(actual.get('title') or '')
            expected_title = _normalize_text(item['texts'][0]) if item.get('texts') else ''

            if expected_title and expected_title not in actual_title:
                warnings.append(
                    _entry(
                        'warning',
                        'title_mismatch',
                        f'Expected title fragment not found: {item["texts"][0][:40]}',
                        slide_idx,
                    )
                )

            for text in item.get('texts', [])[:12]:
                probe = _normalize_text(text)[:32]
                if len(probe) >= 6 and probe not in actual_text:
                    warnings.append(
                        _entry(
                            'warning',
                            'expected_text_not_found',
                            f'Expected text fragment not found: {probe}',
                            slide_idx,
                        )
                    )
                    break

    _check_thumbnail_result(
        thumbnail_result or {},
        expected_slides=slide_count,
        issues=issues,
        warnings=warnings,
    )

    passed = len(issues) == 0
    result = {
        'success': True,
        'passed': passed,
        'issues': issues,
        'warnings': warnings,
        'summary': {
            'slide_count': slide_count,
            'issue_count': len(issues),
            'warning_count': len(warnings),
        },
        'details': details,
        'file_path': str(parsed.get('file_path') or path),
    }

    # Keep backward-compatible fields for existing callers.
    result['slide_count'] = slide_count
    result['error_count'] = len(issues)
    result['warning_count'] = len(warnings)

    return result
