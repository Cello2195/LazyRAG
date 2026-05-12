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


def _sample_schema(slide_count: int = 8) -> dict:
    slides = [
        {'type': 'cover', 'title': 'AI 时代程序员职业路线图', 'subtitle': 'visual route'},
        {'type': 'toc', 'title': '目录', 'items': ['变化趋势', '核心挑战', '机会风险', '升级路线', '行动建议']},
        {
            'type': 'content_bullets',
            'title': '开发工作重心持续迁移',
            'bullets': [
                'AI显著缩短样板代码和原型开发时间，开发者价值重心转向需求澄清与架构判断。',
                '当生成速度不再稀缺，边界条件分析、异常处理与上线稳定性成为核心竞争点。',
                '团队协作标准从个人编码效率转向端到端交付质量、可观测性与持续迭代能力。',
            ],
        },
        {
            'type': 'challenge_cards',
            'title': '程序员面临的主要挑战',
            'cards': [
                {'title': '低复杂度任务压缩', 'body': '模板化和重复性任务被自动化覆盖，基础岗位竞争加剧。'},
                {'title': '质量责任上移', 'body': 'AI生成内容可能存在隐蔽缺陷，必须加强测试和代码审查。'},
                {'title': '学习周期缩短', 'body': '工具链迭代速度提升，单一技术经验的保质期不断缩短。'},
            ],
        },
        {
            'type': 'two_column',
            'title': '机会与挑战并存',
            'left': {
                'title': '机会',
                'bullets': [
                    'AI辅助生成和代码解释降低了原型验证门槛，让开发者更快试错。',
                    '陌生代码库理解速度加快，帮助团队更快完成新人融入和跨模块协作。',
                    '测试生成和日志总结能力提升，缩短问题发现与修复闭环。',
                ],
            },
            'right': {
                'title': '挑战',
                'bullets': [
                    '过度依赖模型输出会削弱独立判断，在复杂场景下放大误判风险。',
                    '低门槛工具让基础编码能力的稀缺性下降，竞争向系统能力迁移。',
                    '生成代码可能带来合规和维护风险，需要更严格的工程治理机制。',
                ],
            },
        },
        {
            'type': 'metric_cards',
            'title': '能力价值重估',
            'metrics': [
                {'label': '重复编码价值', 'value': 'Down', 'description': '模板化实现环节的人工优势正在下降。'},
                {'label': '系统设计价值', 'value': 'Up', 'description': '复杂系统取舍与稳定性设计更加依赖经验判断。'},
                {'label': 'AI协作能力', 'value': 'Up', 'description': '会拆解任务并验证结果的工程师拥有更高杠杆。'},
            ],
        },
        {
            'type': 'timeline',
            'title': '能力升级路线图',
            'items': [
                {'time': '0-3月', 'title': '建立AI协作流程', 'desc': '把提示词、测试生成与审查流程嵌入日常开发。'},
                {'time': '3-6月', 'title': '强化系统设计能力', 'desc': '重点提升边界建模、性能优化和稳定性设计。'},
                {'time': '6-12月', 'title': '完成业务闭环交付', 'desc': '在真实场景完成从需求到上线的端到端项目。'},
                {'time': '12月+', 'title': '沉淀复合竞争力', 'desc': '固化可复用工程方法论，构建长期职业护城河。'},
            ],
        },
        {
            'type': 'summary',
            'title': '总结',
            'bullets': [
                '竞争焦点不再是基础编码速度，而是问题定义和系统治理能力。',
                '把AI作为生产力放大器，同时保持测试、审查和责任意识。',
                '通过真实项目持续沉淀方法论，形成长期稳定的职业差异化优势。',
            ],
        },
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
        deck_schema=_sample_schema(slide_count=8),
        filename='one_shot_demo.pptx',
        output_dir=str(tmp_path / 'one-shot'),
        require_screenshots=False,
    )
    assert result.get('success') is True
    assert result.get('html_deck', {}).get('slide_count') == 8

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


def test_html_deck_generate_visual_pptx_rejects_sparse_schema(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.tools.html_deck import html_deck_generate_visual_pptx

    sparse_schema = {
        'title': 'AI时代程序员职业发展',
        'slides': [
            {'type': 'cover', 'title': 'AI时代程序员职业发展'},
            {'type': 'content_bullets', 'title': '核心趋势'},
        ],
    }
    result = html_deck_generate_visual_pptx(
        deck_schema=sparse_schema,
        filename='sparse_demo.pptx',
        output_dir=str(tmp_path / 'sparse'),
        require_screenshots=False,
    )
    assert result.get('success') is False
    assert result.get('error_code') == 'schema_validation_failed'
