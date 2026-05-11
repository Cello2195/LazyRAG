from __future__ import annotations

from functools import wraps
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from lazyllm import fc_register
except Exception:  # pragma: no cover - local debug fallback.
    def fc_register(*_args, **_kwargs):
        def _decorator(func):
            return func

        return _decorator

from chat.pptx.artifact import artifact_dir, save_artifact
from chat.pptx.parser import parse_pptx
from chat.pptx.qa import run_pptx_qa
from chat.pptx.renderer_python import render_deck_to_pptx
from chat.pptx.schema import (
    normalize_deck_schema,
    repair_deck_schema_for_pptx,
    validate_deck_schema,
)
from chat.pptx.thumbnails import render_pptx_thumbnails


def _tool_failure(tool_name: str, exc: Exception) -> Dict[str, Any]:
    return {
        'success': False,
        'reason': f'{tool_name} failed: {exc}',
        'error': str(exc),
        'error_type': type(exc).__name__,
    }


def _handle_tool_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            return _tool_failure(func.__name__, exc)

    return wrapper


def _safe_filename(filename: Optional[str], default: str = 'presentation.pptx') -> str:
    raw = str(filename or default).strip().replace('..', '').replace('\\', '/')
    raw = raw.rsplit('/', 1)[-1] or default
    if not raw.lower().endswith('.pptx'):
        raw += '.pptx'
    return raw


def _trim_related_artifacts(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'pdf_path': payload.get('pdf_path') or '',
        'thumbnail_paths': payload.get('thumbnail_paths') or [],
    }


@fc_register('tool', execute_in_sandbox=False)
@_handle_tool_errors
def pptx_validate_schema(deck_schema: Any) -> Dict[str, Any]:
    """Validate and normalize deck_schema.

    Args:
        deck_schema: Structured schema input for deck generation.

    Returns issues/warnings plus a normalized_schema that can be rendered even
    if the original payload is slightly malformed.
    """
    return validate_deck_schema(deck_schema)


@fc_register('tool', execute_in_sandbox=False)
@_handle_tool_errors
def pptx_repair_schema(deck_schema: Any, qa_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Apply rule-based repairs for a deck schema using optional QA feedback.

    Args:
        deck_schema: Current deck schema to be repaired.
        qa_result: Optional QA output used to guide repairs.
    """
    return repair_deck_schema_for_pptx(deck_schema, qa_result)


@fc_register('tool', execute_in_sandbox=False)
@_handle_tool_errors
def pptx_create_from_schema(deck_schema: Any, filename: str = 'presentation.pptx') -> Dict[str, Any]:
    """Create an editable PPTX file from a structured deck schema.

    Args:
        deck_schema: Structured schema input for deck generation.
        filename: Output pptx filename.
    """
    validated = validate_deck_schema(deck_schema)
    normalized = validated.get('normalized_schema') or normalize_deck_schema(deck_schema)

    out_dir = artifact_dir('pptx-work')
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / _safe_filename(filename)

    result = render_deck_to_pptx(normalized, out_path)
    result['deck_schema'] = normalized
    result['schema_validation'] = {
        'valid': bool(validated.get('valid')),
        'issues': validated.get('issues') or [],
        'warnings': validated.get('warnings') or [],
    }
    return result


@fc_register('tool', execute_in_sandbox=False)
@_handle_tool_errors
def pptx_parse(file_path: str) -> Dict[str, Any]:
    """Extract slide count, text, tables, image counts, and shape metadata from a PPTX file.

    Args:
        file_path: Absolute or relative path to a pptx file.
    """
    return parse_pptx(file_path)


@fc_register('tool', execute_in_sandbox=False)
@_handle_tool_errors
def pptx_qa(
    file_path: str,
    deck_schema: Optional[Any] = None,
    thumbnail_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run deterministic content/layout QA checks on a PPTX file.

    Args:
        file_path: Absolute or relative path to a pptx file.
        deck_schema: Optional schema used for consistency checks.
        thumbnail_result: Optional thumbnail-render output for visual QA signals.
    """
    return run_pptx_qa(file_path, deck_schema=deck_schema, thumbnail_result=thumbnail_result)


@fc_register('tool', execute_in_sandbox=False)
@_handle_tool_errors
def pptx_render_thumbnails(file_path: str, dpi: int = 144) -> Dict[str, Any]:
    """Render PPTX pages to PDF and PNG thumbnails for visual inspection.

    Args:
        file_path: Absolute or relative path to a pptx file.
        dpi: Render resolution for generated thumbnails.
    """
    return render_pptx_thumbnails(file_path, dpi=dpi, save_outputs=True)


@fc_register('tool', execute_in_sandbox=False)
@_handle_tool_errors
def artifact_save(
    file_path: str,
    kind: str = 'pptx',
    filename: Optional[str] = None,
    related_artifacts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist a generated file and return signed LazyRAG static-file URLs.

    Args:
        file_path: Absolute or relative path to artifact file.
        kind: Artifact category label.
        filename: Optional display filename for download.
        related_artifacts: Optional metadata for side artifacts.
    """
    return save_artifact(Path(file_path), kind=kind, filename=filename, related_artifacts=related_artifacts)


@fc_register('tool', execute_in_sandbox=False)
@_handle_tool_errors
def pptx_generate_with_qa_loop(
    deck_schema: Any,
    filename: str = 'presentation.pptx',
    max_repair_rounds: int = 1,
    render_thumbnails: bool = True,
    thumbnail_dpi: int = 144,
) -> Dict[str, Any]:
    """Run deck_schema -> render -> parse -> qa -> optional repair -> artifact flow.

    Args:
        deck_schema: Structured schema input for deck generation.
        filename: Output pptx filename.
        max_repair_rounds: Max schema-repair retries when QA fails.
        render_thumbnails: Whether to render thumbnails for QA.
        thumbnail_dpi: Thumbnail render resolution.
    """
    validation = validate_deck_schema(deck_schema)
    if not validation.get('success'):
        return validation

    working_schema = validation.get('normalized_schema') or normalize_deck_schema(deck_schema)
    rounds = max(0, int(max_repair_rounds))
    attempts: list[Dict[str, Any]] = []

    final_create: Dict[str, Any] = {}
    final_parse: Dict[str, Any] = {}
    final_qa: Dict[str, Any] = {}
    final_thumb: Dict[str, Any] = {}

    for round_idx in range(rounds + 1):
        create_result = pptx_create_from_schema(working_schema, filename=filename)
        if not create_result.get('success'):
            return create_result

        parse_result = pptx_parse(create_result['file_path'])
        if not parse_result.get('success'):
            return parse_result

        thumb_result: Dict[str, Any] = {}
        if render_thumbnails:
            thumb_result = pptx_render_thumbnails(create_result['file_path'], dpi=thumbnail_dpi)

        qa_result = pptx_qa(
            create_result['file_path'],
            deck_schema=working_schema,
            thumbnail_result=thumb_result if isinstance(thumb_result, dict) else None,
        )

        attempts.append(
            {
                'round': round_idx,
                'file_path': create_result['file_path'],
                'qa_passed': bool(qa_result.get('passed')),
                'issue_count': (qa_result.get('summary') or {}).get('issue_count', 0),
                'warning_count': (qa_result.get('summary') or {}).get('warning_count', 0),
            }
        )

        final_create = create_result
        final_parse = parse_result
        final_qa = qa_result
        final_thumb = thumb_result if isinstance(thumb_result, dict) else {}

        if qa_result.get('passed'):
            break

        if round_idx < rounds:
            repair_result = pptx_repair_schema(working_schema, qa_result)
            repaired_schema = repair_result.get('repaired_schema') if isinstance(repair_result, dict) else None
            if not repaired_schema:
                break
            working_schema = repaired_schema

    related = _trim_related_artifacts(final_thumb) if isinstance(final_thumb, dict) and final_thumb.get('success') else {}
    saved = artifact_save(
        final_create.get('file_path', ''),
        kind='pptx',
        filename=filename,
        related_artifacts=related or None,
    )
    if not saved.get('success'):
        return saved

    return {
        'success': True,
        'normalized_schema': validation.get('normalized_schema') or working_schema,
        'final_schema': working_schema,
        'create_result': final_create,
        'parse_result': final_parse,
        'qa_result': final_qa,
        'thumbnail_result': final_thumb,
        'artifact': saved.get('artifact') or saved,
        'attempts': attempts,
    }
