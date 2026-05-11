from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _ensure_import_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    algorithm_root = root / 'algorithm'
    if str(algorithm_root) not in sys.path:
        sys.path.insert(0, str(algorithm_root))
    return root


def _setup_upload_root(tmp_path: Path) -> None:
    os.environ['LAZYRAG_UPLOAD_ROOT'] = str((tmp_path / 'uploads').resolve())


def _sample_schema(slide_count: int = 6) -> dict:
    slides = [
        {'type': 'cover', 'title': 'AI 时代程序员职业路线图', 'subtitle': 'visual route'},
        {'type': 'toc', 'title': '目录', 'items': ['背景', '挑战', '策略', '行动']},
        {'type': 'section_divider', 'title': '第一部分', 'subtitle': '现状'},
        {'type': 'metric_cards', 'title': '关键指标', 'metrics': [{'label': '效率', 'value': '55%', 'description': 'AI 协作'}]},
        {'type': 'content_bullets', 'title': '建议', 'bullets': ['拥抱 AI', '系统思维', '业务理解']},
        {'type': 'summary', 'title': '总结', 'bullets': ['持续学习', '构建差异化']},
    ]
    return {
        'title': 'AI 时代程序员职业路线图',
        'subtitle': 'visual skill integration',
        'language': 'zh',
        'audience': 'technical',
        'style': 'auto',
        'visual_theme': 'auto',
        'slides': slides[:slide_count],
    }


def test_visual_skill_file_exists_and_contains_required_sections():
    root = _ensure_import_path()
    skill_path = root / 'skills/.curated/visual-pptx-generation/SKILL.md'
    assert skill_path.exists()
    text = skill_path.read_text(encoding='utf-8')
    lowered = text.lower()
    assert 'route' in lowered
    assert 'deck_schema' in lowered
    assert 'final answer' in lowered or 'final response' in lowered
    assert 'download' in lowered
    assert 'do not' in lowered and 'outline' in lowered


def test_pptx_prompt_contains_tool_and_no_outline_requirement():
    _ensure_import_path()
    from chat.prompts.agentic import PPTX_GENERATION_GUIDANCE

    guidance = str(PPTX_GENERATION_GUIDANCE).lower()
    assert 'html_deck_generate_visual_pptx' in guidance
    assert 'do not only return an outline' in guidance
    assert 'deck_schema' in guidance
    assert 'download' in guidance


def test_pptx_intent_adds_visual_skill():
    _ensure_import_path()
    from chat.components.agentic.config import _augment_skills_for_request

    skills = _augment_skills_for_request(
        [],
        query='请帮我生成一份科技感PPT并给下载链接',
        available_tools=['html_deck_generate_visual_pptx', 'artifact_save'],
    )
    assert 'visual-pptx-generation' in skills


def test_parse_deck_schema_input_accepts_dict_json_double_and_fenced(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.schema import parse_deck_schema_input

    schema = _sample_schema()

    parsed_dict = parse_deck_schema_input(schema)
    assert isinstance(parsed_dict, dict)
    assert isinstance(parsed_dict.get('slides'), list)

    parsed_json = parse_deck_schema_input(json.dumps(schema, ensure_ascii=False))
    assert isinstance(parsed_json, dict)
    assert len(parsed_json['slides']) == len(schema['slides'])

    double_encoded = json.dumps(json.dumps(schema, ensure_ascii=False), ensure_ascii=False)
    parsed_double = parse_deck_schema_input(double_encoded)
    assert isinstance(parsed_double, dict)
    assert parsed_double['title'] == schema['title']

    fenced = f"```json\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n```"
    parsed_fenced = parse_deck_schema_input(fenced)
    assert isinstance(parsed_fenced, dict)
    assert isinstance(parsed_fenced['slides'], list)


def test_parse_deck_schema_input_rejects_non_list_slides(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.schema import parse_deck_schema_input

    bad_schema = {'title': 'Bad', 'slides': 'not-a-list'}
    try:
        parse_deck_schema_input(bad_schema)
    except ValueError as exc:
        assert 'slides' in str(exc).lower()
    else:  # pragma: no cover - defensive
        raise AssertionError('expected ValueError for non-list slides')


def test_html_deck_generate_visual_pptx_one_shot_flow(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.tools.html_deck import html_deck_generate_visual_pptx

    result = html_deck_generate_visual_pptx(
        deck_schema=_sample_schema(slide_count=6),
        filename='one_shot_demo.pptx',
        output_dir=str(tmp_path / 'one-shot'),
        require_screenshots=False,
    )
    assert result.get('success') is True
    assert result.get('html_deck', {}).get('slide_count') == 6

    screenshots = result.get('screenshot_result') or {}
    if screenshots.get('success') and result.get('can_export_visual_pptx') is True:
        pptx_result = result.get('pptx_result') or {}
        assert pptx_result.get('success') is True
        assert Path(pptx_result.get('file_path')).exists()
    else:
        assert result.get('can_export_visual_pptx') is False
        warnings = result.get('warnings') or []
        assert warnings
        assert result.get('html_deck', {}).get('index_path')
