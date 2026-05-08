from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import requests

from .artifact import save_artifact, static_file_url

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover - handled by graceful degradation.
    fitz = None


def _expected_pdf_path(source: Path) -> Path:
    return source.with_name(f'{source.stem}.pdf')


def _convert_with_service(source: Path, service_url: str) -> Path:
    resp = requests.post(service_url, json={'source_path': str(source)}, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data.get('data'), dict):
        data = data['data']
    pdf_path = data.get('pdf_path') or data.get('path') or data.get('output_path')
    if not pdf_path:
        raise RuntimeError(f'office convert response missing pdf_path: {data}')
    pdf = Path(pdf_path).expanduser().resolve()
    if not pdf.exists() or not pdf.is_file():
        raise FileNotFoundError(f'converted PDF not found: {pdf}')
    return pdf


def _convert_with_libreoffice(source: Path) -> Path:
    target = _expected_pdf_path(source)
    if target.exists() and target.stat().st_mtime >= source.stat().st_mtime and target.stat().st_size > 0:
        return target
    exe = shutil.which('libreoffice') or shutil.which('soffice')
    if not exe:
        raise RuntimeError('LibreOffice executable not found and LAZYRAG_OFFICE_CONVERT_URL is not configured')
    with tempfile.TemporaryDirectory(dir=str(source.parent)) as tmpdir:
        cmd = [exe, '--headless', '--convert-to', 'pdf', str(source), '--outdir', tmpdir]
        completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
        if completed.returncode != 0:
            raise RuntimeError(f'LibreOffice convert failed: {completed.stderr or completed.stdout}')
        tmp_pdf = Path(tmpdir) / f'{source.stem}.pdf'
        if not tmp_pdf.exists() or tmp_pdf.stat().st_size <= 0:
            raise RuntimeError(f'LibreOffice did not create expected PDF: {tmp_pdf}')
        shutil.move(str(tmp_pdf), str(target))
    return target


def _pptx_to_pdf(source: Path) -> tuple[Path, str]:
    service_url = (os.getenv('LAZYRAG_OFFICE_CONVERT_URL') or os.getenv('LAZYRAG_PPTX_OFFICE_CONVERT_URL') or '').strip()
    if service_url:
        try:
            return _convert_with_service(source, service_url), 'office-convert-service'
        except Exception:
            # Fallback to local LibreOffice when running tests or dev environments.
            pass
    return _convert_with_libreoffice(source), 'libreoffice'


def _render_pdf_pages(pdf_path: Path, output_dir: Path, dpi: int = 144, max_pages: int = 80) -> List[Path]:
    if fitz is None:
        raise RuntimeError('PyMuPDF (fitz) is not available in the current environment')

    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    paths: List[Path] = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    try:
        for page_index in range(min(len(doc), max_pages)):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            out = output_dir / f'slide_{page_index + 1:02d}.png'
            pix.save(str(out))
            paths.append(out)
    finally:
        doc.close()
    return paths


def _failure(file_path: Path, message: str, *, pdf_path: str = '') -> Dict[str, Any]:
    return {
        'success': False,
        'file_path': str(file_path),
        'pdf_path': pdf_path,
        'page_count': 0,
        'thumbnail_paths': [],
        'thumbnail_count': 0,
        'error_message': message,
    }


def render_pptx_thumbnails(file_path: str | Path, dpi: int = 144, save_outputs: bool = True) -> Dict[str, Any]:
    """Convert PPTX to PDF and per-slide PNG thumbnails."""
    source = Path(file_path).expanduser().resolve()
    if not source.exists() or not source.is_file():
        return _failure(source, f'pptx file not found: {source}')

    if fitz is None:
        return _failure(
            source,
            'thumbnail generation is unavailable because PyMuPDF (fitz) is not installed',
        )

    try:
        pdf_path, convert_provider = _pptx_to_pdf(source)
    except Exception as exc:
        return _failure(
            source,
            'thumbnail generation is unavailable because PPTX->PDF conversion failed: '
            f'{exc}',
        )

    thumb_dir = source.with_name(f'{source.stem}_thumbs')
    try:
        thumbnails = _render_pdf_pages(pdf_path, thumb_dir, dpi=dpi)
    except Exception as exc:
        return _failure(
            source,
            f'thumbnail generation failed when rendering PDF pages: {exc}',
            pdf_path=str(pdf_path),
        )

    pdf_artifact = None
    if save_outputs:
        try:
            pdf_artifact = save_artifact(pdf_path, kind='pptx-preview', filename=pdf_path.name)
        except Exception:
            pdf_artifact = None

    thumbnail_paths = [str(path) for path in thumbnails]
    thumb_items = []
    for thumb in thumbnails:
        if save_outputs:
            try:
                saved = save_artifact(thumb, kind='pptx-thumbnails', filename=thumb.name)
                item = saved.get('artifact') or saved
            except Exception:
                item = {
                    'filename': thumb.name,
                    'file_path': str(thumb),
                    'local_path': str(thumb),
                    'file_url': static_file_url(thumb),
                    'download_url': static_file_url(thumb, download=True),
                }
        else:
            item = {
                'filename': thumb.name,
                'file_path': str(thumb),
                'local_path': str(thumb),
                'file_url': static_file_url(thumb),
                'download_url': static_file_url(thumb, download=True),
            }
        thumb_items.append(item)

    pdf_payload = (
        (pdf_artifact.get('artifact') or pdf_artifact)
        if isinstance(pdf_artifact, dict)
        else {
            'file_path': str(pdf_path),
            'file_url': static_file_url(pdf_path),
            'download_url': static_file_url(pdf_path, download=True),
        }
    )

    return {
        'success': True,
        'file_path': str(source),
        'pdf_path': str(pdf_path),
        'convert_provider': convert_provider,
        'pdf': pdf_payload,
        'page_count': len(thumbnails),
        'thumbnail_paths': thumbnail_paths,
        'thumbnail_count': len(thumb_items),
        'thumbnails': thumb_items,
    }
