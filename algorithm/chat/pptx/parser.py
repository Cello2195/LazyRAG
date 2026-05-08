from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from pptx import Presentation

EMU_PER_INCH = 914400


def _shape_text(shape: Any) -> str:
    try:
        if getattr(shape, 'has_text_frame', False):
            return shape.text_frame.text or ''
        if getattr(shape, 'has_table', False):
            parts: list[str] = []
            table = shape.table
            for row in table.rows:
                parts.append(' | '.join(cell.text for cell in row.cells))
            return '\n'.join(parts)
    except Exception:
        return ''
    return ''


def _looks_like_title_shape(shape: Any) -> bool:
    try:
        if getattr(shape, 'is_placeholder', False):
            placeholder = shape.placeholder_format
            placeholder_name = str(getattr(placeholder, 'type', '')).lower()
            if 'title' in placeholder_name:
                return True
    except Exception:
        pass

    name = str(getattr(shape, 'name', '')).lower()
    return 'title' in name


def _extract_slide_title(slide: Any, text_parts: List[str]) -> str:
    for shape in slide.shapes:
        if not _looks_like_title_shape(shape):
            continue
        text = _shape_text(shape).strip()
        if text:
            return text.splitlines()[0].strip()

    if text_parts:
        return text_parts[0].splitlines()[0].strip()
    return ''


def _shape_kind(shape: Any) -> str:
    if getattr(shape, 'has_table', False):
        return 'table'
    if getattr(shape, 'has_chart', False):
        return 'chart'
    if getattr(shape, 'shape_type', None) is not None:
        try:
            name = shape.shape_type.name.lower()
            if 'picture' in name:
                return 'picture'
            if 'placeholder' in name:
                return 'placeholder'
            if 'text' in name:
                return 'text'
            return name
        except Exception:
            pass
    if getattr(shape, 'has_text_frame', False):
        return 'text'
    return 'shape'


def _shape_bbox(shape: Any) -> Dict[str, float]:
    def _to_inch(value: Any) -> float:
        try:
            return round(float(value) / EMU_PER_INCH, 3)
        except Exception:
            return 0.0

    return {
        'x': _to_inch(getattr(shape, 'left', 0)),
        'y': _to_inch(getattr(shape, 'top', 0)),
        'w': _to_inch(getattr(shape, 'width', 0)),
        'h': _to_inch(getattr(shape, 'height', 0)),
    }


def parse_pptx(file_path: str | Path) -> Dict[str, Any]:
    """Extract slide text and lightweight layout metadata from a PPTX file."""
    path = Path(file_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f'pptx file not found: {path}')
    prs = Presentation(str(path))
    slides: List[Dict[str, Any]] = []
    all_text_parts: List[str] = []

    for idx, slide in enumerate(prs.slides, start=1):
        shapes: List[Dict[str, Any]] = []
        text_parts: List[str] = []
        picture_count = 0
        table_count = 0
        for shape in slide.shapes:
            kind = _shape_kind(shape)
            text = _shape_text(shape).strip()
            if text:
                text_parts.append(text)
            if kind == 'picture':
                picture_count += 1
            if kind == 'table':
                table_count += 1
            shapes.append({
                'kind': kind,
                'name': getattr(shape, 'name', ''),
                'bbox': _shape_bbox(shape),
                'text_len': len(text),
                'text_preview': text[:160],
            })
        slide_text = '\n'.join(text_parts).strip()
        all_text_parts.append(slide_text)
        title = _extract_slide_title(slide, text_parts)
        slides.append({
            'index': idx,
            'title': title,
            'text': slide_text,
            'text_len': len(slide_text),
            'shape_count': len(slide.shapes),
            'picture_count': picture_count,
            'image_count': picture_count,
            'table_count': table_count,
            'shapes': shapes,
            'is_empty': len(slide_text) == 0 and picture_count == 0 and table_count == 0,
        })

    return {
        'success': True,
        'file_path': str(path),
        'filename': path.name,
        'slide_count': len(slides),
        'slides': slides,
        'text': '\n\n'.join(part for part in all_text_parts if part),
    }
