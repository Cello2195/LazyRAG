from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from chat.pptx.artifact import resolve_signed_static_file, verify_static_file_signature

router = APIRouter()


def _as_download(value: str | None) -> bool:
    return str(value or '').strip().lower() in {'1', 'true', 'yes'}


def _content_disposition(filename: str, *, inline: bool) -> str:
    name = (filename or 'download').replace('\r', '').replace('\n', '').replace('"', '\\"')
    mode = 'inline' if inline else 'attachment'
    return f'{mode}; filename="{name}"; filename*=UTF-8\'\'{quote(name)}'


@router.get('/api/chat/artifacts/static-files/{path:path}', summary='Download signed chat artifact')
async def get_signed_chat_artifact(
    path: str,
    expires: int = Query(..., description='Signed URL expiration timestamp (unix seconds)'),
    sig: str = Query(..., description='Signed URL HMAC'),
    download: str | None = Query(None, description='Whether to force download'),
):
    ok, reason = verify_static_file_signature(path, expires, sig)
    if not ok:
        if reason in {'invalid_path'}:
            raise HTTPException(status_code=400, detail='invalid path')
        if reason in {'url_expired'}:
            raise HTTPException(status_code=403, detail='url expired')
        raise HTTPException(status_code=403, detail='invalid signature')

    try:
        full_path = resolve_signed_static_file(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail='file not found')

    media_type = mimetypes.guess_type(str(full_path))[0] or 'application/octet-stream'
    inline = not _as_download(download)
    response = FileResponse(path=str(full_path), media_type=media_type, filename=Path(full_path).name)
    response.headers['Cache-Control'] = 'private, max-age=300'
    response.headers['Content-Disposition'] = _content_disposition(Path(full_path).name, inline=inline)
    return response

