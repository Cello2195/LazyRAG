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
        'subtitle': 'content-dense visual route',
        'language': 'zh',
        'audience': 'technical',
        'style': 'auto',
        'visual_theme': theme,
        'slides': [
            {'type': 'cover', 'title': 'AI时代程序员职业发展', 'subtitle': '视觉化测试'},
            {'type': 'toc', 'title': '目录', 'items': ['变化趋势', '核心挑战', '机会与风险', '能力升级路线', '行动建议']},
            {
                'type': 'content_bullets',
                'title': '开发重心从写码速度转向系统质量',
                'bullets': [
                    'AI显著压缩了样板代码与原型开发时间，团队价值重心转向需求澄清和架构决策。',
                    '当生成速度不再稀缺，边界条件分析、异常处理和上线稳定性成为核心竞争点。',
                    '开发者需要把更多时间投入测试设计、代码审查和跨团队协同，而不只是功能实现。',
                ],
            },
            {
                'type': 'challenge_cards',
                'title': '主要挑战',
                'cards': [
                    {'title': '低复杂度任务压缩', 'body': '简单模板化任务更易被工具替代，岗位议价能力下降。'},
                    {'title': '质量责任上移', 'body': 'AI生成内容可能隐藏缺陷，需要更严格的测试和审查流程。'},
                    {'title': '学习周期缩短', 'body': '框架和模型迭代加速，单一技术栈经验更快失效。'},
                ],
            },
            {
                'type': 'two_column',
                'title': '机会与挑战并存',
                'left': {
                    'title': '机会',
                    'bullets': [
                        '自动补全和代码生成提升原型验证速度，让开发者腾出时间处理高价值决策。',
                        'AI辅助阅读陌生代码库，降低新成员理解复杂系统调用链的时间成本。',
                        '测试生成和日志总结工具提升问题定位效率，缩短交付闭环。',
                    ],
                },
                'right': {
                    'title': '挑战',
                    'bullets': [
                        '如果缺少独立判断，开发者可能在复杂需求与边界场景中被错误输出误导。',
                        '低门槛工具扩大竞争范围，基础编码能力的稀缺性下降。',
                        '生成代码可能引入合规和可维护性风险，需要更完善的治理机制。',
                    ],
                },
            },
            {
                'type': 'metric_cards',
                'title': '关键指标',
                'metrics': [
                    {'label': '重复编码价值', 'value': 'Down', 'description': '模板化实现的人工优势正在下降。'},
                    {'label': '系统设计价值', 'value': 'Up', 'description': '复杂系统的架构取舍更依赖经验判断。'},
                    {'label': 'AI协作能力', 'value': 'Up', 'description': '会拆解任务并验证结果的工程师产出更稳定。'},
                ],
            },
            {
                'type': 'timeline',
                'title': '升级路线',
                'items': [
                    {'time': '0-3月', 'title': '建立协作流程', 'desc': '把提示词、审查和测试生成纳入日常开发。'},
                    {'time': '3-6月', 'title': '强化系统设计', 'desc': '提升边界建模、性能优化与稳定性设计能力。'},
                    {'time': '6-12月', 'title': '业务闭环实践', 'desc': '在真实场景完成从需求到上线的端到端交付。'},
                    {'time': '12月+', 'title': '形成复合竞争力', 'desc': '沉淀可复用工程方法论，构建长期职业护城河。'},
                ],
            },
            {
                'type': 'summary',
                'title': '总结',
                'bullets': [
                    '竞争焦点不应停留在基础编码速度，而应转向问题定义和系统治理能力。',
                    'AI是生产力放大器，但必须配套测试、审查和责任边界管理。',
                    '持续通过真实项目沉淀方法论，才能建立可迁移且长期有效的职业优势。',
                ],
            },
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
    assert result['issues'] == []


def test_validate_rejects_title_only_body_slide(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.schema import validate_visual_deck_schema

    schema = {
        'title': 'AI时代程序员职业发展',
        'slides': [
            {'type': 'cover', 'title': 'AI时代程序员职业发展'},
            {'type': 'content_bullets', 'title': '核心趋势'},
        ],
    }
    result = validate_visual_deck_schema(schema)
    codes = {item.get('code') for item in result.get('issues', [])}
    assert 'sparse_body_slide' in codes


def test_validate_rejects_sparse_bullets(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.schema import validate_visual_deck_schema

    schema = {
        'title': 'AI时代程序员职业发展',
        'slides': [
            {'type': 'cover', 'title': 'AI时代程序员职业发展'},
            {'type': 'content_bullets', 'title': '核心趋势', 'bullets': ['AI工具普及', '岗位变化']},
            {'type': 'summary', 'title': '总结', 'bullets': ['持续学习', '拥抱变化', '行动计划']},
        ],
    }
    result = validate_visual_deck_schema(schema)
    codes = {item.get('code') for item in result.get('issues', [])}
    assert 'sparse_body_slide' in codes


def test_validate_rejects_two_column_missing_content(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.schema import validate_visual_deck_schema

    schema = {
        'title': 'AI时代程序员职业发展',
        'slides': [
            {'type': 'cover', 'title': 'AI时代程序员职业发展'},
            {'type': 'two_column', 'title': '机会与挑战'},
            {'type': 'summary', 'title': '总结', 'bullets': ['要点一', '要点二', '要点三']},
        ],
    }
    result = validate_visual_deck_schema(schema)
    codes = {item.get('code') for item in result.get('issues', [])}
    assert 'sparse_body_slide' in codes


def test_validate_rejects_two_column_placeholder_titles(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.schema import validate_visual_deck_schema

    schema = {
        'title': 'AI时代程序员职业发展',
        'slides': [
            {'type': 'cover', 'title': 'AI时代程序员职业发展'},
            {
                'type': 'two_column',
                'title': '机会与挑战',
                'left': {'title': 'Left', 'bullets': []},
                'right': {'title': 'Right', 'bullets': []},
            },
            {'type': 'summary', 'title': '总结', 'bullets': ['要点一', '要点二', '要点三']},
        ],
    }
    result = validate_visual_deck_schema(schema)
    codes = {item.get('code') for item in result.get('issues', [])}
    assert 'placeholder_content' in codes


def test_validate_rejects_too_many_section_slides(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.schema import validate_visual_deck_schema

    schema = {
        'title': 'AI时代程序员职业发展',
        'slides': [
            {'type': 'cover', 'title': '封面'},
            {'type': 'toc', 'title': '目录', 'items': ['A', 'B', 'C', 'D']},
            {'type': 'section_divider', 'title': '第一章'},
            {'type': 'section_divider', 'title': '第二章'},
            {'type': 'section_divider', 'title': '第三章'},
            {'type': 'section_divider', 'title': '第四章'},
            {'type': 'summary', 'title': '总结', 'bullets': ['要点一', '要点二', '要点三']},
            {'type': 'summary', 'title': '行动', 'bullets': ['建议一', '建议二', '建议三']},
        ],
    }
    result = validate_visual_deck_schema(schema)
    codes = {item.get('code') for item in result.get('issues', [])}
    assert 'too_many_section_slides' in codes or 'too_few_substantive_slides' in codes


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
    assert result['slide_count'] == len(_sample_schema()['slides'])


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
    assert qa['summary']['slide_count'] == len(_sample_schema()['slides'])


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


def test_html_deck_qa_detects_sparse_and_placeholder_labels(tmp_path):
    _ensure_import_path()
    _setup_upload_root(tmp_path)
    from chat.html_deck.qa import run_html_deck_qa

    deck_dir = tmp_path / 'qa-deck'
    deck_dir.mkdir(parents=True, exist_ok=True)
    (deck_dir / 'index.html').write_text('<html><body>index</body></html>', encoding='utf-8')

    slide1 = '''
    <html><body><div class="slide-content" data-layout="content_bullets">
      <h2>核心趋势</h2>
    </div></body></html>
    '''
    slide2 = '''
    <html><body><div class="slide-content" data-layout="two_column">
      <h2>机会与挑战</h2>
      <article><h4>Left</h4><ul></ul></article>
      <article><h4>Right</h4><ul></ul></article>
    </div></body></html>
    '''
    slide3 = '''
    <html><body><div class="slide-content" data-layout="content_bullets">
      <h2>行动建议</h2>
      <ul><li>先学习</li><li>再实践</li></ul>
    </div></body></html>
    '''
    (deck_dir / 'slide-01.html').write_text(slide1, encoding='utf-8')
    (deck_dir / 'slide-02.html').write_text(slide2, encoding='utf-8')
    (deck_dir / 'slide-03.html').write_text(slide3, encoding='utf-8')

    qa = run_html_deck_qa(deck_dir=deck_dir)
    codes = {item['code'] for item in qa['issues']}
    assert 'sparse_rendered_slide' in codes
    assert 'placeholder_label' in codes
    assert 'too_few_list_items' in codes


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
    schema['slides'][5]['visual_layout'] = 'dark_metric_cards'
    normalized = normalize_visual_deck_schema(schema)
    assert normalized['slides'][0]['layout'] == 'cover_hero'
    assert normalized['slides'][5]['layout'] == 'metric_cards'


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
