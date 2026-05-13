from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from chat.pptx.artifact import artifact_dir, save_artifact


_SAFE_RE = re.compile(r'[^A-Za-z0-9._-]+')


def _safe_filename(name: str, ext: str) -> str:
    base = str(name or '').strip().replace('\\', '/').rsplit('/', 1)[-1]
    base = base.replace('..', '')
    if not base:
        base = 'longform-report'
    safe = _SAFE_RE.sub('-', base).strip('-._')
    if not safe:
        safe = 'longform-report'
    suffix = ext if ext.startswith('.') else f'.{ext}'
    if not safe.lower().endswith(suffix.lower()):
        safe = f'{safe}{suffix}'
    return safe


def _ext_for_format(output_format: str) -> str:
    fmt = str(output_format or 'markdown').strip().lower()
    if fmt == 'txt':
        return '.txt'
    if fmt == 'html':
        return '.html'
    return '.md'


def save_longform_artifact(
    *,
    content: str,
    title: str,
    output_format: str = 'markdown',
    related_artifacts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ext = _ext_for_format(output_format)
    out_dir = artifact_dir('lclm-longform-work')
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    filename = _safe_filename(f'{title}-{stamp}', ext)
    out_path = Path(out_dir) / filename
    out_path.write_text(str(content or ''), encoding='utf-8')

    return save_artifact(
        out_path,
        kind='lclm-longform',
        filename=filename,
        related_artifacts=related_artifacts,
    )
