from __future__ import annotations

from functools import wraps
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

try:
    from lazyllm import fc_register
except Exception:  # pragma: no cover - local debug fallback.
    def fc_register(*_args, **_kwargs):
        def _decorator(func):
            return func
        return _decorator

from chat.html_deck.export_pptx import create_pptx_from_slide_images
from chat.html_deck.qa import run_html_deck_qa
from chat.html_deck.renderer import create_html_deck_from_schema
from chat.html_deck.schema import validate_html_deck_schema
from chat.html_deck.screenshot import render_html_deck_screenshots
from chat.html_deck.artifact import artifact_dir, save_artifact, save_html_deck_bundle, static_file_url


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


def _safe_stem(filename: Optional[str], default: str = 'visual_deck') -> str:
    raw = str(filename or default).strip().replace('..', '').replace('\\', '/')
    raw = raw.rsplit('/', 1)[-1] or default
    if raw.lower().endswith('.pptx') or raw.lower().endswith('.html'):
        raw = Path(raw).stem
    return ''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in raw).strip('._-') or default


def _resolve_index(index_path: Optional[str], deck_dir: Optional[str]) -> Path:
    if index_path:
        return Path(index_path).expanduser().resolve()
    if deck_dir:
        return (Path(deck_dir).expanduser().resolve() / 'index.html')
    raise ValueError('index_path or deck_dir is required')


@fc_register('tool', execute_in_sandbox=False)
@_handle_tool_errors
def html_deck_validate_schema(deck_schema: Any, theme: Optional[Any] = None) -> Dict[str, Any]:
    """Validate and normalize deck_schema for theme-aware HTML visual decks.

    Args:
        deck_schema: Structured deck schema.
        theme: Optional visual theme name or dict, e.g. auto, cyber_blue, academic_light, corporate_blue, or a custom palette dict.
    """
    return validate_html_deck_schema(deck_schema, theme=theme)


@fc_register('tool', execute_in_sandbox=False)
@_handle_tool_errors
def html_deck_create_from_schema(
    deck_schema: Any,
    deck_name: str = 'visual_deck',
    theme: Optional[Any] = None,
) -> Dict[str, Any]:
    """Create theme-aware fixed-size HTML slides from deck_schema.

    This creates slide-XX.html files and an index.html preview. It does not
    require Playwright or Node.
    """
    return create_html_deck_from_schema(deck_schema, theme=theme, deck_name=_safe_stem(deck_name))


@fc_register('tool', execute_in_sandbox=False)
@_handle_tool_errors
def html_deck_preview(
    deck_dir: Optional[str] = None,
    index_path: Optional[str] = None,
    persist_index_artifact: bool = False,
) -> Dict[str, Any]:
    """Resolve HTML deck preview location/URL.

    Args:
        deck_dir: Deck directory containing index.html.
        index_path: Explicit index file path.
        persist_index_artifact: If true, save index.html as an artifact for signed URL.
    """
    index = _resolve_index(index_path, deck_dir)
    if not index.exists() or not index.is_file():
        return {
            'success': False,
            'error_message': f'index.html not found: {index}',
            'index_path': str(index),
        }
    preview_url = static_file_url(index)
    artifact = {}
    if persist_index_artifact:
        saved = save_artifact(index, kind='html-deck', filename=index.name)
        artifact = saved.get('artifact') or saved
        preview_url = artifact.get('file_url') or preview_url
    return {
        'success': True,
        'index_path': str(index),
        'deck_dir': str(index.parent),
        'preview_url': preview_url,
        'local_path': str(index),
        'artifact': artifact,
    }


@fc_register('tool', execute_in_sandbox=False)
@_handle_tool_errors
def html_deck_qa(
    deck_dir: Optional[str] = None,
    slide_paths: Optional[list[str]] = None,
    screenshot_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run deterministic QA checks on generated HTML deck files.

    Args:
        deck_dir: Directory containing slide-XX.html files.
        slide_paths: Optional explicit HTML slide file paths.
        screenshot_result: Optional output from html_deck_render_screenshots.
    """
    return run_html_deck_qa(deck_dir=deck_dir, slide_paths=slide_paths, screenshot_result=screenshot_result)


@fc_register('tool', execute_in_sandbox=False)
@_handle_tool_errors
def html_deck_render_screenshots(
    deck_dir: Optional[str] = None,
    slide_paths: Optional[list[str]] = None,
    output_dir: Optional[str] = None,
    viewport_width: int = 960,
    viewport_height: int = 540,
    device_scale_factor: float = 2.0,
) -> Dict[str, Any]:
    """Render HTML slides into PNG screenshots via Playwright.

    If Playwright/browser runtime is not available, returns success=false while
    keeping the HTML deck usable.
    """
    return render_html_deck_screenshots(
        deck_dir=deck_dir,
        slide_paths=slide_paths,
        output_dir=output_dir,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        device_scale_factor=device_scale_factor,
    )


@fc_register('tool', execute_in_sandbox=False)
@_handle_tool_errors
def pptx_create_from_html_screenshots(
    screenshot_paths: list[str],
    filename: str = 'visual_deck.pptx',
) -> Dict[str, Any]:
    """Create image-based PPTX from full-slide HTML screenshots.

    Args:
        screenshot_paths: PNG screenshot paths in slide order.
        filename: Output PPTX filename.
    """
    stem = _safe_stem(filename, 'visual_deck')
    out_dir = artifact_dir('visual-pptx-work')
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'{stem}.pptx'
    return create_pptx_from_slide_images(screenshot_paths, out_path)


@fc_register('tool', execute_in_sandbox=False)
@_handle_tool_errors
def html_deck_generate_visual_pptx(
    deck_schema: Any,
    filename: str = 'visual_deck.pptx',
    theme: Optional[Any] = None,
    render_screenshots: bool = True,
) -> Dict[str, Any]:
    """Generate a theme-aware visual deck and optional image-based PPTX.

    Workflow:
      deck_schema -> HTML slides -> HTML QA -> Playwright screenshots -> PPTX images -> artifact_save

    If Playwright is unavailable, this still returns a persisted HTML deck and
    the screenshot/PPTX step reports a graceful warning.
    """
    stem = _safe_stem(filename, 'visual_deck')
    html_result = create_html_deck_from_schema(deck_schema, theme=theme, deck_name=stem)
    if not html_result.get('success'):
        return html_result

    preview_result = html_deck_preview(
        deck_dir=html_result.get('deck_dir'),
        index_path=html_result.get('index_path'),
        persist_index_artifact=False,
    )
    screenshot_result: Dict[str, Any] = {}
    pptx_result: Dict[str, Any] = {}
    saved_pptx: Dict[str, Any] = {}
    bundle_result: Dict[str, Any] = {}

    if render_screenshots:
        screenshot_result = render_html_deck_screenshots(
            deck_dir=html_result.get('deck_dir'),
            slide_paths=html_result.get('slide_paths') or [],
        )
        if screenshot_result.get('success'):
            pptx_result = pptx_create_from_html_screenshots(
                screenshot_result.get('screenshot_paths') or [],
                filename=f'{stem}.pptx',
            )
            if pptx_result.get('success'):
                related = {
                    'html_index_path': html_result.get('index_path'),
                    'deck_dir': html_result.get('deck_dir'),
                    'screenshot_paths': screenshot_result.get('screenshot_paths') or [],
                    'editable': False,
                    'generation_mode': 'html_screenshot_image_pptx',
                }
                saved_pptx = save_artifact(
                    pptx_result['file_path'],
                    kind='visual-pptx',
                    filename=f'{stem}.pptx',
                    related_artifacts=related,
                )

    qa_result = run_html_deck_qa(
        deck_dir=html_result.get('deck_dir'),
        slide_paths=html_result.get('slide_paths') or [],
        screenshot_result=screenshot_result if screenshot_result else None,
    )

    try:
        bundle_result = save_html_deck_bundle(
            index_path=html_result.get('index_path') or '',
            slide_paths=html_result.get('slide_paths') or [],
            screenshot_paths=screenshot_result.get('screenshot_paths') if screenshot_result else [],
            pptx_path=pptx_result.get('file_path') if pptx_result.get('success') else None,
        )
    except Exception as exc:
        bundle_result = {
            'success': False,
            'error_message': f'html deck bundle save failed: {exc}',
        }

    return {
        'success': True,
        'html_deck': html_result,
        'preview': preview_result,
        'html_qa': qa_result,
        'screenshot_result': screenshot_result,
        'pptx_result': pptx_result,
        'artifact': (saved_pptx.get('artifact') if isinstance(saved_pptx, dict) else {}) or saved_pptx,
        'artifacts': bundle_result.get('artifacts') if isinstance(bundle_result, dict) else {},
        'output_mode': 'visual_pptx',
        'editable': False,
        'warnings': [] if screenshot_result.get('success') else (screenshot_result.get('warnings') or ['visual PPTX screenshot export was skipped/unavailable']),
    }
