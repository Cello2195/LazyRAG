from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


def _ensure_import_path() -> None:
    root = Path(__file__).resolve().parents[1]
    algorithm_root = root / 'algorithm'
    if str(algorithm_root) not in sys.path:
        sys.path.insert(0, str(algorithm_root))


def _sample_schema(theme: str = 'auto'):
    return {
        'title': 'Visual Deck Test',
        'subtitle': 'theme-aware visual route',
        'language': 'zh',
        'audience': 'technical',
        'style': 'auto',
        'visual_theme': theme,
        'slides': [
            {'type': 'cover', 'title': '视觉化标题', 'subtitle': '测试'},
            {'type': 'toc', 'title': '目录', 'items': ['现状', '挑战', '结论']},
            {'type': 'section_divider', 'title': '现状', 'subtitle': '行业分析'},
            {
                'type': 'metric_cards',
                'title': '关键指标',
                'metrics': [
                    {'label': '效率', 'value': '55%', 'description': '显著提升'},
                    {'label': '质量', 'value': '+22%', 'description': '返工率下降'},
                ],
            },
            {'type': 'summary', 'title': '总结', 'bullets': ['结论一', '结论二']},
        ],
    }


def _setup_upload_root(tmp_path: Path) -> None:
    os.environ['LAZYRAG_UPLOAD_ROOT'] = str((tmp_path / 'uploads').resolve())


def test_normalize_visual_schema_missing_fields(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.schema import normalize_visual_deck_schema

    normalized = normalize_visual_deck_schema({'slides': [{}]})
    assert normalized['title']
    assert normalized['slides']
    assert normalized['visual_theme']['name']
    assert normalized['slides'][0]['title']


def test_validate_returns_normalized_schema(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.schema import validate_visual_deck_schema

    result = validate_visual_deck_schema(_sample_schema())
    assert result['success'] is True
    assert 'normalized_schema' in result
    assert result['normalized_schema']['slides']


def test_visual_theme_auto_resolves(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.schema import normalize_visual_deck_schema

    normalized = normalize_visual_deck_schema(_sample_schema(theme='auto'))
    assert normalized['theme_used'] in {
        'cyber_blue',
        'dark_tech',
        'corporate_blue',
        'academic_light',
        'warm_editorial',
        'emerald_dark',
        'violet_neon',
        'midnight_gold',
        'light_magazine',
    }


def test_palette_override_applies(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.schema import normalize_visual_deck_schema

    schema = _sample_schema(theme='corporate_blue')
    schema['palette'] = {'primary': '#7c3aed', 'background': '#faf5ff'}
    normalized = normalize_visual_deck_schema(schema)
    palette = normalized['palette_used']
    assert palette['primary'].lower() == '#7c3aed'
    assert palette['background'].lower() == '#faf5ff'


def test_html_deck_create_and_files_exist(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.renderer import create_html_deck_from_schema

    result = create_html_deck_from_schema(_sample_schema(), output_dir=tmp_path / 'deck', persist_index=False)
    assert result['success'] is True
    assert Path(result['index_path']).exists()
    assert all(Path(p).exists() for p in result['slide_paths'])
    assert result['slide_count'] == 5


def test_themes_generate_different_html(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.renderer import create_html_deck_from_schema

    r1 = create_html_deck_from_schema(_sample_schema(theme='corporate_blue'), output_dir=tmp_path / 'deck1', persist_index=False)
    r2 = create_html_deck_from_schema(_sample_schema(theme='academic_light'), output_dir=tmp_path / 'deck2', persist_index=False)
    h1 = Path(r1['slide_paths'][0]).read_text(encoding='utf-8')
    h2 = Path(r2['slide_paths'][0]).read_text(encoding='utf-8')
    assert h1 != h2


def test_html_deck_qa_passes_basic(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.renderer import create_html_deck_from_schema
    from chat.html_deck.qa import run_html_deck_qa

    result = create_html_deck_from_schema(_sample_schema(), output_dir=tmp_path / 'deck', persist_index=False)
    qa = run_html_deck_qa(deck_dir=result['deck_dir'], slide_paths=result['slide_paths'])
    assert qa['success'] is True
    assert qa['passed'] is True
    assert qa['summary']['slide_count'] == 5


def test_html_deck_qa_detects_placeholder(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.renderer import create_html_deck_from_schema
    from chat.html_deck.qa import run_html_deck_qa

    result = create_html_deck_from_schema(_sample_schema(), output_dir=tmp_path / 'deck', persist_index=False)
    first = Path(result['slide_paths'][0])
    first.write_text(first.read_text(encoding='utf-8') + '\n<!-- TODO placeholder -->\n', encoding='utf-8')
    qa = run_html_deck_qa(deck_dir=result['deck_dir'], slide_paths=result['slide_paths'])
    assert qa['passed'] is False
    assert any(item['code'] == 'placeholder_residue' for item in qa['issues'])


def test_html_deck_qa_marks_fallback_not_export_ready(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.renderer import create_html_deck_from_schema
    from chat.html_deck.qa import run_html_deck_qa

    result = create_html_deck_from_schema(_sample_schema(), output_dir=tmp_path / 'deck', persist_index=False)
    qa = run_html_deck_qa(
        deck_dir=result['deck_dir'],
        slide_paths=result['slide_paths'],
        screenshot_result={
            'success': False,
            'fallback_used': True,
            'is_real_browser_render': False,
            'can_export_visual_pptx': False,
            'error_message': 'playwright unavailable',
            'screenshot_paths': [],
        },
    )
    assert qa['success'] is True
    assert qa['summary']['export_ready'] is False
    codes = {item['code'] for item in qa['warnings']}
    assert 'fallback_screenshot_used' in codes
    assert 'visual_export_not_ready' in codes


def test_legacy_dark_layout_alias_compat(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.schema import normalize_visual_deck_schema

    schema = _sample_schema()
    schema['slides'][0]['layout'] = 'dark_cover_hero'
    schema['slides'][3]['visual_layout'] = 'dark_metric_cards'
    normalized = normalize_visual_deck_schema(schema)
    assert normalized['slides'][0]['layout'] == 'cover_hero'
    assert normalized['slides'][3]['layout'] == 'metric_cards'


def test_screenshots_and_image_pptx_if_playwright_available(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.export_pptx import create_pptx_from_slide_images
    from chat.html_deck.renderer import create_html_deck_from_schema
    from chat.html_deck.screenshot import render_html_deck_screenshots

    result = create_html_deck_from_schema(_sample_schema(), output_dir=tmp_path / 'deck', persist_index=False)
    shots = render_html_deck_screenshots(
        deck_dir=result['deck_dir'],
        slide_paths=result['slide_paths'],
        output_dir=tmp_path / 'shots',
    )
    if not shots.get('success'):
        pytest.skip(shots.get('error_message') or 'Playwright/Chromium unavailable')

    screenshot_paths = shots.get('screenshot_paths') or []
    assert len(screenshot_paths) == result['slide_count']
    assert all(Path(p).exists() for p in screenshot_paths)

    pptx_path = tmp_path / 'visual.pptx'
    pptx = create_pptx_from_slide_images(screenshot_paths, pptx_path)
    assert pptx['success'] is True
    assert Path(pptx['file_path']).exists()
    assert pptx['slide_count'] == result['slide_count']
