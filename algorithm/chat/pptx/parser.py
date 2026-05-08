from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from pptx import Presentation

EMU_PER_INCH = 914400


def _to_inch(value: Any) -> float:
    try:
        return round(float(value) / EMU_PER_INCH, 3)
    except Exception:
        return 0.0


def _shape_bbox(shape: Any) -> Dict[str, float]:
    return {
        'x': _to_inch(getattr(shape, 'left', 0)),
        'y': _to_inch(getattr(shape, 'top', 0)),
        'w': _to_inch(getattr(shape, 'width', 0)),
        'h': _to_inch(getattr(shape, 'height', 0)),
    }


def _shape_kind(shape: Any) -> str:
    if getattr(shape, 'has_table', False):
        return 'table'
    if getattr(shape, 'has_chart', False):
        return 'chart'
    try:
        name = str(getattr(shape, 'shape_type', '')).lower()
        if 'picture' in name:
            return 'picture'
        if 'placeholder' in name:
            return 'placeholder'
        if 'text' in name:
            return 'text'
    except Exception:
        pass
    if getattr(shape, 'has_text_frame', False):
        return 'text'
    return 'shape'


def _extract_text_frame_metrics(shape: Any) -> Tuple[str, List[float], int, int]:
    if not getattr(shape, 'has_text_frame', False):
        return '', [], 0, 0

    parts: List[str] = []
    font_sizes: List[float] = []
    bullet_count = 0
    max_line_len = 0

    for para in shape.text_frame.paragraphs:
        text = (para.text or '').strip()
        if text:
            parts.append(text)
            bullet_count += 1
            max_line_len = max(max_line_len, max((len(line) for line in text.splitlines()), default=0))
        for run in para.runs:
            try:
                if run.font.size is not None:
                    font_sizes.append(round(float(run.font.size.pt), 2))
            except Exception:
                continue

    return '\n'.join(parts), font_sizes, bullet_count, max_line_len


def _extract_table_metrics(shape: Any) -> Tuple[str, int, int]:
    if not getattr(shape, 'has_table', False):
        return '', 0, 0

    try:
        table = shape.table
        rows = len(table.rows)
        cols = len(table.columns)
        table_lines = []
        for row in table.rows:
            table_lines.append(' | '.join((cell.text or '').strip() for cell in row.cells))
        return '\n'.join(table_lines), rows, cols
    except Exception:
        return '', 0, 0


def _looks_like_title_shape(shape: Any) -> bool:
    try:
        if getattr(shape, 'is_placeholder', False):
            placeholder_type = str(getattr(shape.placeholder_format, 'type', '')).lower()
            if 'title' in placeholder_type:
                return True
    except Exception:
        pass

    return 'title' in str(getattr(shape, 'name', '')).lower()


def _extract_slide_title(slide: Any, shape_payloads: List[Dict[str, Any]]) -> str:
    for shape, payload in zip(slide.shapes, shape_payloads):
        if not _looks_like_title_shape(shape):
            continue
        text = (payload.get('text') or '').strip()
        if text:
            return text.splitlines()[0].strip()

    for payload in shape_payloads:
        text = (payload.get('text') or '').strip()
        if text:
            return text.splitlines()[0].strip()

    return ''


def parse_pptx(file_path: str | Path) -> Dict[str, Any]:
    """Extract text, structure, and simple layout metrics from a PPTX file."""
    path = Path(file_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f'pptx file not found: {path}')

    prs = Presentation(str(path))
    slide_width = _to_inch(prs.slide_width)
    slide_height = _to_inch(prs.slide_height)

    slides: List[Dict[str, Any]] = []
    all_text_parts: List[str] = []

    for idx, slide in enumerate(prs.slides, start=1):
        shapes: List[Dict[str, Any]] = []
        text_parts: List[str] = []

        picture_count = 0
        table_count = 0
        total_bullet_count = 0
        max_line_len = 0
        font_sizes: List[float] = []
        table_cells = 0
        max_table_rows = 0
        max_table_cols = 0

        for shape in slide.shapes:
            kind = _shape_kind(shape)
            bbox = _shape_bbox(shape)
            text, text_font_sizes, bullet_count, shape_max_line_len = _extract_text_frame_metrics(shape)
            table_text, rows, cols = _extract_table_metrics(shape)

            merged_text = text
            if table_text:
                merged_text = '\n'.join(part for part in [text, table_text] if part).strip()

            if merged_text:
                text_parts.append(merged_text)

            if kind == 'picture':
                picture_count += 1
            if kind == 'table':
                table_count += 1
                table_cells += rows * cols
                max_table_rows = max(max_table_rows, rows)
                max_table_cols = max(max_table_cols, cols)

            total_bullet_count += bullet_count
            max_line_len = max(max_line_len, shape_max_line_len)
            font_sizes.extend(text_font_sizes)

            is_out_of_bounds = (
                bbox['x'] < -0.01
                or bbox['y'] < -0.01
                or bbox['w'] <= 0
                or bbox['h'] <= 0
                or bbox['x'] + bbox['w'] > slide_width + 0.01
                or bbox['y'] + bbox['h'] > slide_height + 0.01
            )

            shapes.append({
                'kind': kind,
                'name': getattr(shape, 'name', ''),
                'bbox': bbox,
                'text': merged_text,
                'text_len': len(merged_text),
                'text_preview': merged_text[:180],
                'font_sizes': text_font_sizes,
                'min_font_size': min(text_font_sizes) if text_font_sizes else None,
                'max_font_size': max(text_font_sizes) if text_font_sizes else None,
                'bullet_count': bullet_count,
                'max_line_len': shape_max_line_len,
                'table_rows': rows,
                'table_cols': cols,
                'is_out_of_bounds': is_out_of_bounds,
            })

        slide_text = '\n'.join(text_parts).strip()
        all_text_parts.append(slide_text)

        title = _extract_slide_title(slide, shapes)
        min_font_size = min(font_sizes) if font_sizes else None
        max_font_size = max(font_sizes) if font_sizes else None

        slides.append({
            'index': idx,
            'title': title,
            'text': slide_text,
            'text_len': len(slide_text),
            'shape_count': len(slide.shapes),
            'picture_count': picture_count,
            'image_count': picture_count,
            'table_count': table_count,
            'table_cells': table_cells,
            'max_table_rows': max_table_rows,
            'max_table_cols': max_table_cols,
            'bullet_count': total_bullet_count,
            'max_line_len': max_line_len,
            'min_font_size': min_font_size,
            'max_font_size': max_font_size,
            'shapes': shapes,
            'is_empty': len(slide_text) == 0 and picture_count == 0 and table_count == 0,
        })

    return {
        'success': True,
        'file_path': str(path),
        'filename': path.name,
        'file_size': path.stat().st_size,
        'slide_width': slide_width,
        'slide_height': slide_height,
        'slide_count': len(slides),
        'slides': slides,
        'text': '\n\n'.join(part for part in all_text_parts if part),
    }
