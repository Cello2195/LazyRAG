from __future__ import annotations

import hashlib
import hmac
import os
import posixpath
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote, unquote
from urllib.parse import urlparse

try:
    import lazyllm
except Exception:  # pragma: no cover - fallback for local debug environments.
    lazyllm = None

_SAFE_PART_RE = re.compile(r'[^A-Za-z0-9._-]+')


def upload_root() -> Path:
    # Keep this aligned with backend/core/doc/task_storage.go uploadRoot().
    root = (
        os.getenv('LAZYRAG_UPLOAD_ROOT')
        or os.getenv('LAZYRAG_SHARED_UPLOAD_DIR')
        or os.getenv('LAZYRAG_UPLOAD_DIR')
        or '/var/lib/lazyrag/uploads'
    )
    return Path(root).expanduser().resolve()


def _safe_part(value: Any, default: str = 'artifact') -> str:
    text = str(value or '').strip().replace('..', '').replace('\\', '/')
    text = text.strip('/')
    text = _SAFE_PART_RE.sub('_', text)
    text = text.strip('._-')
    return text or default


def _session_id() -> str:
    globals_obj = getattr(lazyllm, 'globals', None)
    config = globals_obj.get('agentic_config') if globals_obj is not None and hasattr(globals_obj, 'get') else {}
    config = config or {}
    if isinstance(config, dict):
        for key in ('session_id', 'thread_id', 'conversation_id', 'request_id'):
            value = str(config.get(key) or '').strip()
            if value:
                return _safe_part(value, 'session')
    try:
        sid = str(getattr(globals_obj, '_sid', '') or '').strip() if globals_obj is not None else ''
        if sid:
            return _safe_part(sid, 'session')
    except Exception:
        pass
    return 'session'


def _agentic_config() -> Dict[str, Any]:
    if lazyllm is None:
        return {}
    globals_obj = getattr(lazyllm, 'globals', None)
    if globals_obj is None or not hasattr(globals_obj, 'get'):
        return {}
    config = globals_obj.get('agentic_config') or {}
    return config if isinstance(config, dict) else {}


def _core_api_base_url() -> str:
    base = (
        _agentic_config().get('core_api_url')
        or os.getenv('LAZYRAG_CORE_API_URL')
        or ''
    )
    return str(base).rstrip('/')


def _core_api_public_base_url() -> str:
    base = (
        _agentic_config().get('core_api_public_url')
        or os.getenv('LAZYRAG_CORE_API_PUBLIC_URL')
        or os.getenv('LAZYRAG_PUBLIC_BASE_URL')
        or ''
    )
    return str(base).rstrip('/')


def _looks_like_internal_host(base_url: str) -> bool:
    if not base_url:
        return False
    try:
        parsed = urlparse(base_url)
    except Exception:
        return False
    host = (parsed.hostname or '').strip().lower()
    return host in {'core', 'localhost', '127.0.0.1', '0.0.0.0', '::1'}


def _static_file_route_prefix() -> str:
    mode = _file_delivery_mode()
    if mode == 'chat_proxy':
        # Route through chat service to avoid depending on external /api/core forwarding.
        return '/api/chat/artifacts/static-files'

    # Allow explicit override first.
    cfg = _agentic_config()
    explicit = (
        cfg.get('static_file_route_prefix')
        or os.getenv('LAZYRAG_STATIC_FILE_ROUTE_PREFIX')
        or ''
    )
    prefix = str(explicit).strip()
    if prefix:
        if not prefix.startswith('/'):
            prefix = f'/{prefix}'
        return prefix.rstrip('/')

    base = _core_api_base_url()
    parsed = urlparse(base) if base else None
    base_host = (parsed.hostname or '').strip().lower() if parsed else ''
    base_path = (parsed.path or '').rstrip('/') if parsed else ''

    # If chat talks to core via internal service-name, returned links should be
    # browser-facing through Kong (/api/core/static-files/...).
    if base_host == 'core':
        return '/api/core/static-files'
    if base_path.endswith('/api/core'):
        return '/api/core/static-files'
    return '/static-files'


def _file_delivery_mode() -> str:
    cfg = _agentic_config()
    value = (
        cfg.get('file_delivery_mode')
        or os.getenv('LAZYRAG_FILE_DELIVERY_MODE')
        or ''
    )
    mode = str(value).strip().lower().replace('-', '_')
    if mode in {'core_static', 'chat_proxy'}:
        return mode
    # Prefer chat-proxy by default to avoid host-level /api/core proxy pitfalls.
    return 'chat_proxy'


def _absolute_url(path: str) -> str:
    if not path:
        return ''
    if path.startswith('http://') or path.startswith('https://'):
        return path
    # Prefer explicit public base when available.
    public_base = _core_api_public_base_url()
    base = public_base or _core_api_base_url()
    if not base:
        return path
    if not public_base and _looks_like_internal_host(base):
        # Avoid returning container-internal addresses such as http://core:8000.
        return ''
    return f'{base}{path if path.startswith("/") else "/" + path}'


def _static_secret() -> str:
    return os.getenv('LAZYRAG_FILE_URL_SIGN_SECRET') or 'lazyrag-file-url-secret'


def _expire_seconds() -> int:
    try:
        value = int(os.getenv('LAZYRAG_FILE_URL_EXPIRE_SECONDS') or '3600')
        return value if value > 0 else 3600
    except ValueError:
        return 3600


def _relative_to_upload_root(path: Path) -> str:
    root = upload_root()
    try:
        rel = path.resolve().relative_to(root)
    except ValueError:
        return ''
    return rel.as_posix()


def normalize_static_rel_path(raw_path: str) -> str:
    if raw_path is None:
        return ''
    decoded = unquote(str(raw_path).strip())
    if not decoded:
        return ''
    normalized = posixpath.normpath('/' + decoded.replace('\\', '/'))
    rel = normalized.lstrip('/')
    if not rel or rel == '.' or rel.startswith('../'):
        return ''
    return rel


def sign_static_file(rel_path: str, expires: int) -> str:
    mac = hmac.new(_static_secret().encode('utf-8'), digestmod=hashlib.sha256)
    mac.update(rel_path.encode('utf-8'))
    mac.update(b'\n')
    mac.update(str(int(expires)).encode('utf-8'))
    return mac.hexdigest()


def verify_static_file_signature(rel_path: str, expires: int, sig: str) -> tuple[bool, str]:
    rel = normalize_static_rel_path(rel_path)
    if not rel:
        return False, 'invalid_path'
    try:
        exp = int(expires)
    except Exception:
        return False, 'invalid_expires'
    if exp <= 0 or int(time.time()) > exp:
        return False, 'url_expired'
    expected = sign_static_file(rel, exp)
    if not hmac.compare_digest(str(sig or '').strip(), expected):
        return False, 'invalid_signature'
    return True, ''


def resolve_signed_static_file(rel_path: str) -> Path:
    rel = normalize_static_rel_path(rel_path)
    if not rel:
        raise ValueError('invalid path')
    root = upload_root()
    full = (root / Path(rel)).resolve()
    try:
        full.relative_to(root)
    except ValueError as exc:
        raise ValueError('path outside upload root') from exc
    return full


def static_file_url(path: str | Path, *, download: bool = False) -> str:
    target = Path(path).expanduser().resolve()
    rel = _relative_to_upload_root(target)
    if not rel:
        return ''
    expires = int(time.time()) + _expire_seconds()
    sig = sign_static_file(rel, expires)
    encoded = '/'.join(quote(part) for part in rel.split('/'))
    route_prefix = _static_file_route_prefix()
    url = f'{route_prefix}/{encoded}?expires={expires}&sig={sig}'
    if download:
        url += '&download=1'
    return url


def artifact_dir(kind: str = 'pptx') -> Path:
    return upload_root() / 'agent-results' / _session_id() / _safe_part(kind, 'artifact') / datetime.now(timezone.utc).strftime('%Y%m%d')


def _sha256_prefix(path: Path, size: int = 12) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()[:size]


def _build_payload(
    dst: Path,
    kind: str,
    rel: str,
    file_url: str,
    download_url: str,
    *,
    sha256: str,
    related_artifacts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    stat = dst.stat()
    local_path = str(dst)
    file_name = dst.name
    created_at = datetime.now(timezone.utc).isoformat()
    base: Dict[str, Any] = {
        'success': True,
        'kind': kind,
        'filename': file_name,
        'file_path': local_path,
        'local_path': local_path,
        'relative_path': rel,
        'size_bytes': stat.st_size,
        'sha256': sha256,
        'created_at': created_at,
        'file_url': file_url,
        'download_url': download_url,
        'content_url': file_url,
        'preview_url': file_url,
    }
    absolute_file_url = _absolute_url(file_url)
    absolute_download_url = _absolute_url(download_url)
    if absolute_file_url:
        base['absolute_file_url'] = absolute_file_url
    if absolute_download_url:
        base['absolute_download_url'] = absolute_download_url

    base['artifact'] = {
        'type': kind,
        'kind': kind,
        'filename': file_name,
        'file_path': local_path,
        'local_path': local_path,
        'relative_path': rel,
        'file_size': stat.st_size,
        'size_bytes': stat.st_size,
        'sha256': sha256,
        'created_at': created_at,
        'file_url': file_url,
        'download_url': download_url,
        'content_url': file_url,
        'preview_url': file_url,
        'absolute_file_url': absolute_file_url,
        'absolute_download_url': absolute_download_url,
    }
    if isinstance(related_artifacts, dict) and related_artifacts:
        base['related_artifacts'] = related_artifacts
        base['artifact']['related_artifacts'] = related_artifacts
    return base


def save_artifact(
    file_path: str | Path,
    kind: str = 'pptx',
    filename: Optional[str] = None,
    related_artifacts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Copy a generated artifact under LazyRAG's upload root and return signed URLs."""
    src = Path(file_path).expanduser().resolve()
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f'artifact file not found: {src}')

    out_dir = artifact_dir(kind)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_part(filename or src.name, f'artifact{src.suffix or ""}')
    if src.suffix and not safe_name.lower().endswith(src.suffix.lower()):
        safe_name = f'{safe_name}{src.suffix}'
    digest = _sha256_prefix(src)
    stem = Path(safe_name).stem
    suffix = Path(safe_name).suffix or src.suffix
    dst = out_dir / f'{stem}_{digest}{suffix}'
    if src != dst:
        shutil.copy2(src, dst)

    rel = _relative_to_upload_root(dst)
    if not rel:
        raise ValueError(f'artifact path is outside upload root: {dst}')

    file_url = static_file_url(dst)
    download_url = static_file_url(dst, download=True)
    return _build_payload(
        dst,
        kind,
        rel,
        file_url,
        download_url,
        sha256=digest,
        related_artifacts=related_artifacts,
    )
