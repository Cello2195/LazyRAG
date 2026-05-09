from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, List

try:
    # Reuse project-wide upload root, signed URL, and artifact metadata behavior.
    from chat.pptx.artifact import artifact_dir as _pptx_artifact_dir
    from chat.pptx.artifact import save_artifact as _pptx_save_artifact
    from chat.pptx.artifact import static_file_url as _pptx_static_file_url
except Exception:  # pragma: no cover
    _pptx_artifact_dir = None
    _pptx_save_artifact = None
    _pptx_static_file_url = None


def artifact_dir(kind: str = 'html-deck-work') -> Path:
    if _pptx_artifact_dir:
        return _pptx_artifact_dir(kind)
    root = Path(
        os.getenv('LAZYRAG_UPLOAD_ROOT')
        or (Path.cwd() / 'tmp' / 'lazyrag_artifacts')
    ).resolve()
    path = root / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def static_file_url(path: str | Path, *, download: bool = False) -> str:
    if _pptx_static_file_url:
        return _pptx_static_file_url(path, download=download)
    p = Path(path).expanduser().resolve()
    return str(p)


def save_artifact(
    file_path: str | Path,
    *,
    kind: str = 'artifact',
    filename: str | None = None,
    related_artifacts: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    if _pptx_save_artifact:
        return _pptx_save_artifact(file_path, kind=kind, filename=filename, related_artifacts=related_artifacts)
    p = Path(file_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(str(p))
    return {
        'success': True,
        'artifact': {
            'kind': kind,
            'filename': filename or p.name,
            'file_path': str(p),
            'local_path': str(p),
            'file_url': str(p),
            'download_url': str(p),
            'size_bytes': p.stat().st_size,
            'related_artifacts': related_artifacts or {},
        },
    }


def save_html_deck_bundle(
    *,
    index_path: str | Path,
    slide_paths: Iterable[str],
    screenshot_paths: Iterable[str] | None = None,
    pptx_path: str | Path | None = None,
) -> Dict[str, Any]:
    index = Path(index_path).expanduser().resolve()
    slides = [Path(p).expanduser().resolve() for p in slide_paths or []]
    shots = [Path(p).expanduser().resolve() for p in screenshot_paths or []]

    bundle: Dict[str, Any] = {
        'html_index': {
            'file_path': str(index),
            'preview_url': static_file_url(index),
            'download_url': static_file_url(index, download=True),
        },
        'slides': [
            {
                'file_path': str(path),
                'url': static_file_url(path),
            }
            for path in slides
            if path.exists()
        ],
        'screenshots': [
            {
                'file_path': str(path),
                'url': static_file_url(path),
            }
            for path in shots
            if path.exists()
        ],
    }

    saved_pptx = None
    if pptx_path:
        try:
            saved_pptx = save_artifact(pptx_path, kind='visual-pptx', filename=Path(pptx_path).name)
        except Exception:
            saved_pptx = None

    if isinstance(saved_pptx, dict) and saved_pptx.get('success'):
        bundle['pptx'] = saved_pptx.get('artifact') or saved_pptx
    elif pptx_path:
        p = Path(pptx_path).expanduser().resolve()
        bundle['pptx'] = {
            'file_path': str(p),
            'download_url': static_file_url(p, download=True),
            'size_bytes': p.stat().st_size if p.exists() else 0,
        }

    return {'success': True, 'artifacts': bundle}
