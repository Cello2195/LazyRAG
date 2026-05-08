from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .parser import parse_pptx
from .schema import normalize_deck_schema

_PLACEHOLDER_RE = re.compile(r'(lorem ipsum|placeholder|待补充|TODO|TBD|xxxx|\[\[TODO\]\])', re.IGNORECASE)
_MAX_TEXT_LEN_PER_SLIDE = 1250


def _add_entry(
    entries: List[Dict[str, Any]],
    *,
    level: str,
    code: str,
    message: str,
    slide_index: int | None = None,
) -> None:
    entries.append({
        'level': level,
        'code': code,
        'message': message,
        'slide_index': slide_index,
    })


def _schema_expected_text(deck_schema: Any) -> List[Dict[str, Any]]:
    if not deck_schema:
        return []
    deck = normalize_deck_schema(deck_schema)
    expected: List[Dict[str, Any]] = []
    for idx, slide in enumerate(deck['slides'], start=1):
        texts = [slide.get('title') or '', slide.get('subtitle') or '']
        texts.extend(slide.get('bullets') or [])
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


def _normalize_text_for_match(value: Any) -> str:
    text = str(value or '').strip().lower()
    if not text:
        return ''
    return re.sub(r'\s+', ' ', text)


def _make_result(
    *,
    file_path: str,
    slide_count: int,
    issues: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]],
    parse_ok: bool,
) -> Dict[str, Any]:
    passed = parse_ok and not issues
    summary = (
        'QA passed.'
        if passed
        else f'QA found {len(issues)} issue(s) and {len(warnings)} warning(s).'
    )
    return {
        'success': parse_ok,
        'passed': passed,
        'file_path': file_path,
        'slide_count': slide_count,
        'issues': issues,
        'warnings': warnings,
        'error_count': len(issues),
        'warning_count': len(warnings),
        'summary': summary,
    }


def run_pptx_qa(file_path: str | Path, deck_schema: Optional[Any] = None, parse_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run a lightweight QA pass over a generated PPTX.

    This is intentionally deterministic and cheap. It catches common artifact
    failures before optional thumbnail/vision QA is introduced: empty slides,
    missing titles, placeholder residue, excessive text, and schema mismatch.
    """
    path = Path(file_path).expanduser().resolve()
    issues: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    if not path.exists() or not path.is_file():
        _add_entry(
            issues,
            level='error',
            code='file_not_found',
            message=f'PPTX file not found: {path}',
        )
        return _make_result(
            file_path=str(path),
            slide_count=0,
            issues=issues,
            warnings=warnings,
            parse_ok=False,
        )

    try:
        parsed = parse_result if isinstance(parse_result, dict) else parse_pptx(path)
    except Exception as exc:
        _add_entry(
            issues,
            level='error',
            code='open_failed',
            message=f'Failed to open PPTX with python-pptx: {exc}',
        )
        return _make_result(
            file_path=str(path),
            slide_count=0,
            issues=issues,
            warnings=warnings,
            parse_ok=False,
        )

    slides = parsed.get('slides') or []
    if not slides:
        _add_entry(
            issues,
            level='error',
            code='no_slides',
            message='PPTX contains no slides.',
        )

    if deck_schema is not None:
        expected = _schema_expected_text(deck_schema)
        if len(expected) != len(slides):
            _add_entry(
                issues,
                level='error',
                code='slide_count_mismatch',
                message=f'Expected {len(expected)} slides from schema, got {len(slides)} slides in PPTX.',
            )

        for item in expected[:len(slides)]:
            slide_idx = item['index']
            actual_title = (
                str(slides[slide_idx - 1].get('title') or '').strip()
                if slide_idx - 1 < len(slides)
                else ''
            )
            actual_text = (
                _normalize_text_for_match(slides[slide_idx - 1].get('text') or '')
                if slide_idx - 1 < len(slides)
                else ''
            )

            expected_title = str(item.get('texts', [''])[0]).strip() if item.get('texts') else ''
            if expected_title and actual_title and _normalize_text_for_match(expected_title) not in _normalize_text_for_match(actual_title):
                _add_entry(
                    warnings,
                    level='warning',
                    code='title_mismatch',
                    message=f'Expected title "{expected_title[:48]}" not matched by slide title "{actual_title[:48]}".',
                    slide_index=slide_idx,
                )

            for expected_text in item['texts'][:12]:
                probe = _normalize_text_for_match(expected_text)[:32]
                if len(probe) >= 6 and probe not in actual_text:
                    _add_entry(
                        warnings,
                        level='warning',
                        code='expected_text_not_found',
                        message=f'Expected text fragment not found: {probe}',
                        slide_index=slide_idx,
                    )

    for slide in slides:
        idx = int(slide.get('index') or 0)
        text = slide.get('text') or ''
        if slide.get('is_empty'):
            _add_entry(
                issues,
                level='error',
                code='empty_slide',
                message='Slide is empty.',
                slide_index=idx,
            )
        if not slide.get('title'):
            _add_entry(
                warnings,
                level='warning',
                code='missing_title',
                message='Slide has no detected title.',
                slide_index=idx,
            )
        if _PLACEHOLDER_RE.search(text):
            _add_entry(
                issues,
                level='error',
                code='placeholder_residue',
                message='Slide contains placeholder/TODO text.',
                slide_index=idx,
            )
        if len(text) > _MAX_TEXT_LEN_PER_SLIDE:
            _add_entry(
                warnings,
                level='warning',
                code='too_much_text',
                message='Slide may contain too much text for presentation use.',
                slide_index=idx,
            )
        for shape in slide.get('shapes') or []:
            bbox = shape.get('bbox') or {}
            x, y = float(bbox.get('x') or 0), float(bbox.get('y') or 0)
            w, h = float(bbox.get('w') or 0), float(bbox.get('h') or 0)
            if x < -0.05 or y < -0.05 or x + w > 13.5 or y + h > 7.7:
                _add_entry(
                    warnings,
                    level='warning',
                    code='shape_out_of_bounds',
                    message='A shape may exceed slide bounds.',
                    slide_index=idx,
                )
                break

    return _make_result(
        file_path=str(parsed.get('file_path') or path),
        slide_count=int(parsed.get('slide_count') or len(slides)),
        issues=issues,
        warnings=warnings,
        parse_ok=True,
    )
