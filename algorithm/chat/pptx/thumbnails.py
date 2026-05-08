from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

from .artifact import save_artifact, static_file_url

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover - graceful degradation path.
    fitz = None


def _expected_pdf_path(source: Path) -> Path:
    return source.with_name(f'{source.stem}.pdf')


def _ensure_output_dir(source: Path, output_dir: str | Path | None) -> Path:
    if output_dir is None:
        return source.with_name(f'{source.stem}_thumbnails')
    return Path(output_dir).expanduser().resolve()


def _convert_with_service(source: Path, service_url: str) -> Path:
    response = requests.post(service_url, json={'source_path': str(source)}, timeout=240)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload.get('data'), dict):
        payload = payload['data']

    pdf_path = payload.get('pdf_path') or payload.get('path') or payload.get('output_path')
    if not pdf_path:
        raise RuntimeError(f'office convert response missing pdf_path: {payload}')

    resolved = Path(str(pdf_path)).expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(f'converted PDF not found: {resolved}')
    return resolved


def _convert_with_libreoffice(source: Path) -> Path:
    target = _expected_pdf_path(source)
    if target.exists() and target.stat().st_mtime >= source.stat().st_mtime and target.stat().st_size > 0:
        return target

    executable = shutil.which('libreoffice') or shutil.which('soffice')
    if not executable:
        raise RuntimeError('LibreOffice executable not found')

    with tempfile.TemporaryDirectory(dir=str(source.parent)) as tmpdir:
        command = [
            executable,
            '--headless',
            '--convert-to',
            'pdf',
            str(source),
            '--outdir',
            tmpdir,
        ]
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=240)
        if completed.returncode != 0:
            raise RuntimeError(f'LibreOffice convert failed: {completed.stderr or completed.stdout}')

        temp_pdf = Path(tmpdir) / f'{source.stem}.pdf'
        if not temp_pdf.exists() or temp_pdf.stat().st_size <= 0:
            raise RuntimeError(f'LibreOffice did not generate expected PDF: {temp_pdf}')
        shutil.move(str(temp_pdf), str(target))

    return target


def _pptx_to_pdf(source: Path) -> Tuple[Path, str]:
    service_url = (
        os.getenv('LAZYRAG_OFFICE_CONVERT_URL')
        or os.getenv('LAZYRAG_PPTX_OFFICE_CONVERT_URL')
        or ''
    ).strip()

    if service_url:
        try:
            return _convert_with_service(source, service_url), 'office-convert-service'
        except Exception:
            # Fall through to local LibreOffice.
            pass

    return _convert_with_libreoffice(source), 'libreoffice'


def _render_pdf_pages(pdf_path: Path, output_dir: Path, dpi: int = 144, max_pages: int = 120) -> List[Path]:
    if fitz is None:
        raise RuntimeError('PyMuPDF (fitz) is not available')

    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    scale = dpi / 72.0
    matrix = fitz.Matrix(scale, scale)

    paths: List[Path] = []
    try:
        for page_index in range(min(len(doc), max_pages)):
            page = doc.load_page(page_index)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            output = output_dir / f'slide_{page_index + 1:02d}.png'
            pixmap.save(str(output))
            paths.append(output)
    finally:
        doc.close()

    return paths


def _fail(source: Path, error_message: str, warnings: List[str] | None = None, pdf_path: str = '') -> Dict[str, Any]:
    return {
        'success': False,
        'file_path': str(source),
        'pdf_path': pdf_path,
        'thumbnail_paths': [],
        'page_count': 0,
        'thumbnail_count': 0,
        'warnings': warnings or ['thumbnail rendering unavailable; pptx generation is still valid'],
        'error_message': error_message,
    }


def render_pptx_thumbnails(
    file_path: str | Path,
    dpi: int = 144,
    save_outputs: bool = True,
    output_dir: str | Path | None = None,
) -> Dict[str, Any]:
    """Convert PPTX to PDF and render per-page PNG thumbnails.

    The function is best-effort. Failure returns success=False without affecting
    the main PPTX generation flow.
    """
    source = Path(file_path).expanduser().resolve()
    if not source.exists() or not source.is_file():
        return _fail(source, f'pptx file not found: {source}')

    if fitz is None:
        return _fail(source, 'PyMuPDF (fitz) is not installed in current environment')

    try:
        pdf_path, provider = _pptx_to_pdf(source)
    except Exception as exc:
        return _fail(source, f'PPTX->PDF conversion failed: {exc}')

    out_dir = _ensure_output_dir(source, output_dir)

    try:
        thumbnail_paths = _render_pdf_pages(pdf_path, out_dir, dpi=dpi)
    except Exception as exc:
        return _fail(source, f'PDF->PNG rendering failed: {exc}', pdf_path=str(pdf_path))

    warnings: List[str] = []
    missing = [str(p) for p in thumbnail_paths if not p.exists()]
    if missing:
        warnings.append(f'missing rendered thumbnails: {missing[:3]}')

    too_small = [str(p) for p in thumbnail_paths if p.exists() and p.stat().st_size < 1024]
    if too_small:
        warnings.append('some thumbnails are unexpectedly small')

    pdf_payload: Dict[str, Any] = {
        'file_path': str(pdf_path),
        'file_url': static_file_url(pdf_path),
        'download_url': static_file_url(pdf_path, download=True),
    }

    thumbnail_items: List[Dict[str, Any]] = []
    if save_outputs:
        try:
            saved_pdf = save_artifact(pdf_path, kind='pptx-preview', filename=pdf_path.name)
            pdf_payload = saved_pdf.get('artifact') or saved_pdf
        except Exception:
            warnings.append('failed to persist preview PDF artifact')

    for thumb in thumbnail_paths:
        item: Dict[str, Any]
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
                warnings.append(f'failed to persist thumbnail artifact: {thumb.name}')
        else:
            item = {
                'filename': thumb.name,
                'file_path': str(thumb),
                'local_path': str(thumb),
                'file_url': static_file_url(thumb),
                'download_url': static_file_url(thumb, download=True),
            }
        thumbnail_items.append(item)

    return {
        'success': True,
        'file_path': str(source),
        'pdf_path': str(pdf_path),
        'pdf': pdf_payload,
        'thumbnail_paths': [str(path) for path in thumbnail_paths],
        'thumbnails': thumbnail_items,
        'page_count': len(thumbnail_paths),
        'thumbnail_count': len(thumbnail_items),
        'warnings': warnings,
        'convert_provider': provider,
    }
