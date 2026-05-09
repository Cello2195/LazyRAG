#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_import_path() -> None:
    algorithm_root = _repo_root() / 'algorithm'
    if str(algorithm_root) not in sys.path:
        sys.path.insert(0, str(algorithm_root))


def _sample_visual_schema(theme: str, palette: Dict[str, Any]) -> Dict[str, Any]:
    schema: Dict[str, Any] = {
        'title': 'AI时代下程序员该何去何从',
        'subtitle': '职业发展、技能升级与行动策略（2026）',
        'language': 'zh',
        'audience': 'technical',
        'style': 'auto',
        'visual_theme': theme,
        'slides': [
            {
                'type': 'cover',
                'title': 'AI时代下程序员该何去何从',
                'subtitle': '职业发展、技能升级与行动策略',
                'date': '2026-05',
                'evidence_refs': ['WEF Future of Jobs 2025', 'Stack Overflow Developer Survey 2025'],
            },
            {
                'type': 'toc',
                'title': '目录',
                'items': [
                    '行业变化与核心趋势',
                    '挑战：岗位与能力结构变化',
                    '机会：新角色与新价值',
                    '行动：6个月能力重塑方案',
                    '结论与下一步',
                ],
            },
            {
                'type': 'section_divider',
                'section_number': '01',
                'title': '行业变化与核心趋势',
                'subtitle': '从写代码到交付系统价值',
            },
            {
                'type': 'metric_cards',
                'title': '关键指标：变化正在发生',
                'subtitle': '效率提升与岗位结构重塑并存',
                'metrics': [
                    {'label': '编码效率提升', 'value': '35-55%', 'description': 'AI辅助编码在常见任务上提效明显'},
                    {'label': '招聘要求变化', 'value': '72%', 'description': '岗位描述增加AI工具与系统能力要求'},
                    {'label': '跨职能协作占比', 'value': '+28%', 'description': '产品、数据、工程融合更紧密'},
                ],
                'bullets': [
                    '重复实现类工作持续自动化',
                    '复杂系统设计与业务理解价值上升',
                    '工程师需要提升“定义问题+验证结果”能力',
                ],
            },
            {
                'type': 'challenge_cards',
                'title': '主要挑战：旧优势正在失效',
                'cards': [
                    {'title': '同质化竞争', 'body': '仅靠框架熟练度的优势在缩小', 'accent': 'danger'},
                    {'title': '知识更新过慢', 'body': 'AI工具链迭代快，学习滞后会被拉开差距', 'accent': 'primary'},
                    {'title': '业务理解不足', 'body': '不会定义问题，工具再强也难产出高价值', 'accent': 'secondary'},
                    {'title': '协作能力短板', 'body': '跨团队沟通与推动落地成为关键门槛', 'accent': 'danger'},
                ],
            },
            {
                'type': 'content_bullets',
                'title': '机会：从执行者升级为设计者',
                'subtitle': '以AI工具为杠杆，构建新的个人护城河',
                'bullets': [
                    '从“写更多代码”转向“交付更好结果”：关注业务指标与系统稳定性',
                    '建立个人AI工作流：检索、生成、评审、测试、回归一体化',
                    '深耕垂直场景：金融风控、医疗数据、制造优化等领域知识',
                    '主动承担架构与协作职责：成为连接需求、技术与落地的关键节点',
                ],
                'evidence_refs': ['McKinsey AI report 2025'],
            },
            {
                'type': 'two_column',
                'title': '能力模型：被替代风险 vs 增值能力',
                'left': {
                    'title': '高替代风险能力',
                    'bullets': ['机械CRUD', '模板化脚本拼接', '只会单点实现', '缺乏验证与复盘'],
                },
                'right': {
                    'title': '高增值能力',
                    'bullets': ['系统架构与取舍', '业务抽象与需求澄清', 'AI协作与质量评估', '跨团队推动交付'],
                },
            },
            {
                'type': 'comparison',
                'title': '路线对比：传统开发路径 vs AI增强路径',
                'headers': ['维度', '传统路径', 'AI增强路径'],
                'rows': [
                    ['目标', '按需求完成功能', '以业务结果为导向的持续交付'],
                    ['工作方式', '人力堆砌与重复劳动', '自动化链路 + 人工决策'],
                    ['核心能力', '语法与框架熟练', '架构思维 + 验证能力 + 协作能力'],
                    ['成长速度', '线性积累', '工具杠杆下的非线性成长'],
                ],
            },
            {
                'type': 'table',
                'title': '90天行动计划（可执行）',
                'headers': ['阶段', '重点目标', '关键动作', '验收标准'],
                'rows': [
                    ['第1-30天', '搭建AI开发工作流', '统一检索/生成/测试工具链', '核心任务提效>20%'],
                    ['第31-60天', '补强系统能力', '完成1个架构升级或性能优化项目', '关键指标提升可量化'],
                    ['第61-90天', '沉淀影响力', '输出技术复盘/分享/模板', '形成可复用方法论'],
                ],
                'evidence_refs': ['GitHub Octoverse 2025'],
            },
            {
                'type': 'quote',
                'title': '关键观点',
                'quote': 'AI 不会取代程序员，但会取代不会使用 AI 的程序员。',
                'author': '工程实践共识',
            },
            {
                'type': 'summary',
                'title': '总结与下一步',
                'bullets': [
                    '先用起来：把AI纳入每日开发与评审流程',
                    '做深一点：补齐系统设计、质量与业务抽象能力',
                    '做出成果：用真实项目证明“AI增强型工程师”价值',
                    '持续迭代：每月复盘一次工具链与能力模型',
                ],
            },
        ],
    }
    if palette:
        schema['palette'] = palette
    return schema


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Debug visual html_deck generation pipeline.')
    parser.add_argument('--theme', default='auto', help='auto/cyber_blue/corporate_blue/academic_light/warm_editorial/dark_tech/...')
    parser.add_argument('--palette-json', default='', help='JSON dict for palette override')
    parser.add_argument('--require-screenshots', action='store_true', help='fail if screenshot export is unavailable')
    parser.add_argument(
        '--output-dir',
        default=str((_repo_root() / 'tmp' / 'lazyrag_visual_deck_debug').resolve()),
        help='output root directory',
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = Path(args.output_dir).expanduser().resolve()
    os.environ.setdefault('LAZYRAG_UPLOAD_ROOT', str(root / 'uploads'))

    palette: Dict[str, Any] = {}
    if args.palette_json.strip():
        try:
            palette = json.loads(args.palette_json)
            if not isinstance(palette, dict):
                raise ValueError('palette-json must be a JSON object')
        except Exception as exc:
            raise SystemExit(f'Invalid --palette-json: {exc}')

    _ensure_import_path()
    from chat.html_deck.artifact import save_artifact, save_html_deck_bundle
    from chat.html_deck.export_pptx import create_pptx_from_slide_images
    from chat.html_deck.qa import run_html_deck_qa
    from chat.html_deck.renderer import create_html_deck_from_schema
    from chat.html_deck.schema import (
        normalize_visual_deck_schema,
        resolve_visual_theme,
        validate_visual_deck_schema,
    )
    from chat.html_deck.screenshot import render_html_deck_screenshots
    from chat.tools.html_deck import html_deck_preview

    schema = _sample_visual_schema(args.theme, palette)
    visual_pptx_path = root / 'visual.pptx'
    if visual_pptx_path.exists():
        visual_pptx_path.unlink()

    normalized = normalize_visual_deck_schema(schema)
    print('Normalized schema: success')

    validated = validate_visual_deck_schema(schema)
    if not validated.get('success'):
        raise RuntimeError(json.dumps(validated, ensure_ascii=False))
    print(f"Schema valid: {validated.get('valid')} warnings={len(validated.get('warnings') or [])}")

    theme_used = resolve_visual_theme(normalized)
    print(f"Theme used: {theme_used.get('name')}")
    palette_used = {k: theme_used.get(k) for k in ('background', 'surface', 'primary', 'accent', 'foreground', 'muted')}
    print(f"Palette used: {json.dumps(palette_used, ensure_ascii=False)}")

    deck_dir = root / 'deck'
    html_result = create_html_deck_from_schema(schema, output_dir=deck_dir, theme=args.theme, deck_name='visual')
    if not html_result.get('success'):
        raise RuntimeError(json.dumps(html_result, ensure_ascii=False, indent=2))

    print(f"HTML deck created: {html_result['deck_dir']}")
    print(f"Index path: {html_result['index_path']}")
    print(f"Slide count: {html_result['slide_count']}")
    print(f"Layout summary: {json.dumps(html_result.get('layout_summary') or {}, ensure_ascii=False)}")

    preview = html_deck_preview(deck_dir=html_result['deck_dir'], index_path=html_result['index_path'])
    if not preview.get('success'):
        raise RuntimeError(json.dumps(preview, ensure_ascii=False, indent=2))
    print(f"Preview URL/local path: {preview.get('preview_url') or preview.get('local_path')}")

    qa_before = run_html_deck_qa(deck_dir=html_result['deck_dir'], slide_paths=html_result['slide_paths'])
    print(f"HTML QA passed: {qa_before.get('passed')}")
    print(f"Issue count: {qa_before.get('summary', {}).get('issue_count')}")
    print(f"Warning count: {qa_before.get('summary', {}).get('warning_count')}")
    if not qa_before.get('passed'):
        raise RuntimeError(json.dumps(qa_before, ensure_ascii=False, indent=2))

    screenshots = render_html_deck_screenshots(
        deck_dir=html_result['deck_dir'],
        slide_paths=html_result['slide_paths'],
        output_dir=Path(html_result['deck_dir']) / 'screenshots',
        viewport_width=960,
        viewport_height=540,
        device_scale_factor=2.0,
        allow_fallback_preview=not args.require_screenshots,
    )
    screenshot_success = bool(screenshots.get('success'))
    fallback_used = bool(screenshots.get('fallback_used'))
    real_browser_render = screenshots.get('is_real_browser_render') is True
    can_export_visual_pptx = screenshots.get('can_export_visual_pptx') is True
    real_screenshot_success = bool(
        screenshot_success
        and real_browser_render
        and (not fallback_used)
        and can_export_visual_pptx
    )
    screenshot_status = 'real-browser-success'
    if fallback_used:
        screenshot_status = 'fallback-preview'
    elif not screenshot_success:
        screenshot_status = 'skipped'
    print(f"Screenshots: {screenshot_status}")
    print(f"Screenshot count: {len(screenshots.get('screenshot_paths') or [])}")
    print(f"Fallback used: {str(fallback_used).lower()}")
    print(f"Real browser render: {str(real_browser_render).lower()}")
    print(f"Can export visual PPTX: {str(can_export_visual_pptx).lower()}")
    if screenshots.get('warnings'):
        print(f"Screenshot warnings: {json.dumps(screenshots.get('warnings'), ensure_ascii=False)}")

    if args.require_screenshots and not real_screenshot_success:
        print(f"Screenshot error: {screenshots.get('error_message')}")
        return 2

    pptx_result: Dict[str, Any] = {}
    artifact_result: Dict[str, Any] = {}
    if real_screenshot_success:
        pptx_result = create_pptx_from_slide_images(screenshots.get('screenshot_paths') or [], visual_pptx_path)
        if not pptx_result.get('success'):
            raise RuntimeError(json.dumps(pptx_result, ensure_ascii=False, indent=2))
        print(f"Visual PPTX created: {pptx_result['file_path']}")
        print(f"Visual PPTX size: {pptx_result.get('size_bytes')}")

        artifact_result = save_artifact(
            pptx_result['file_path'],
            kind='visual-pptx',
            filename='visual.pptx',
            related_artifacts={
                'deck_dir': html_result['deck_dir'],
                'index_path': html_result['index_path'],
                'screenshot_paths': screenshots.get('screenshot_paths') or [],
                'editable': False,
                'generation_mode': 'html_screenshot_image_pptx',
            },
        )
        artifact_payload = artifact_result.get('artifact') or artifact_result
        print(f"Artifact saved: {artifact_payload.get('file_path')}")
        print(f"Final visual PPTX path: {artifact_payload.get('file_path')}")
        print(f"Download URL: {artifact_payload.get('download_url')}")
    else:
        print('Visual PPTX skipped: screenshots are not real-browser export-ready')

    bundle = save_html_deck_bundle(
        index_path=html_result['index_path'],
        slide_paths=html_result['slide_paths'],
        screenshot_paths=screenshots.get('screenshot_paths') or [],
        pptx_path=pptx_result.get('file_path') if pptx_result.get('success') else None,
    )
    if bundle.get('success'):
        print(f"Artifact bundle: success ({len((bundle.get('artifacts') or {}).get('slides') or [])} slides)")

    qa_after = run_html_deck_qa(
        deck_dir=html_result['deck_dir'],
        slide_paths=html_result['slide_paths'],
        screenshot_result=screenshots,
    )
    print(f"Post QA passed: {qa_after.get('passed')}")
    print(f"Post QA issues: {qa_after.get('summary', {}).get('issue_count')}")
    print(f"Post QA warnings: {qa_after.get('summary', {}).get('warning_count')}")

    if real_screenshot_success and not Path(pptx_result['file_path']).exists():
        raise RuntimeError('visual.pptx not found after export')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
