#!/usr/bin/env python3
from __future__ import annotations

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


def _sample_phase2_schema() -> Dict[str, Any]:
    long_bullet = (
        '本页用于测试长文本处理与 QA 规则；当单条 bullet 过长时，系统应自动截断或在 notes 中保留溢出内容，'
        '避免投影场景下出现密集难读段落，同时保证页面结构不会因为文本超长而出现布局溢出。'
    )
    return {
        'title': 'LazyRAG PPTX Generation Phase2 Demo',
        'subtitle': 'Schema normalization + QA + repair loop',
        'language': 'zh',
        'audience': 'technical',
        'theme': 'academic',
        'slides': [
            {'type': 'cover', 'title': 'LazyRAG 阶段二演示', 'subtitle': '可编辑 PPTX 自动生成增强版'},
            {'type': 'toc', 'title': '目录', 'items': ['目标', '方案', '对比', '数据', '结论', '参考']},
            {'type': 'section_divider', 'title': '一、核心目标', 'subtitle': '从能跑通到更稳定可检查'},
            {
                'type': 'content_bullets',
                'title': '功能目标',
                'bullets': [
                    long_bullet,
                    '支持 deck_schema 的自动归一化与容错修复。',
                    '支持渲染后结构解析与规则 QA 检查。',
                    '支持可选缩略图预览与 artifact 保存。',
                    'TODO: 该项用于触发修复逻辑。',
                ],
                'evidence_refs': ['[KB] LazyRAG docs', 'https://example.com/spec'],
            },
            {
                'type': 'two_column',
                'title': '方案分层',
                'columns': [
                    {
                        'title': '生成层',
                        'bullets': ['schema 校验', '主题映射', 'slide 渲染', 'notes 注入', 'references 汇总'],
                    },
                    {
                        'title': '验证层',
                        'bullets': ['parse 提取', '规则 QA', '修复闭环', 'artifact 回传', '缩略图检查'],
                    },
                ],
            },
            {
                'type': 'comparison',
                'title': '阶段对比',
                'left': {
                    'title': 'Phase 1',
                    'bullets': ['主链路打通', '基础 parse/qa', '可保存 artifact'],
                },
                'right': {
                    'title': 'Phase 2',
                    'bullets': ['主题系统', '增强 QA', '规则修复闭环', '缩略图降级策略'],
                },
            },
            {
                'type': 'table',
                'title': '测试数据矩阵',
                'headers': ['模块', '输入', '输出', '状态', '风险', '备注', '负责人', '优先级'],
                'rows': [
                    ['schema', 'raw json', 'normalized', 'done', 'low', '兼容弱格式', 'A', 'P0'],
                    ['renderer', 'deck', 'pptx', 'done', 'medium', '表格裁剪', 'B', 'P0'],
                    ['parser', 'pptx', 'json', 'done', 'low', '提取字体', 'C', 'P1'],
                    ['qa', 'parse', 'report', 'done', 'medium', '规则持续迭代', 'D', 'P0'],
                    ['repair', 'qa', 'schema', 'done', 'medium', '只做规则修复', 'E', 'P1'],
                    ['thumb', 'pptx', 'png', 'pending', 'high', '依赖环境', 'F', 'P1'],
                    ['artifact', 'file', 'url', 'done', 'low', 'signed url', 'G', 'P0'],
                    ['agent', 'prompt', 'toolcalls', 'done', 'medium', '需线上观测', 'H', 'P1'],
                    ['extra1', 'x', 'y', 'n/a', 'low', 'row overflow test', 'I', 'P2'],
                    ['extra2', 'x', 'y', 'n/a', 'low', 'row overflow test', 'J', 'P2'],
                    ['extra3', 'x', 'y', 'n/a', 'low', 'row overflow test', 'K', 'P2'],
                ],
                'bullets': ['表格过密时应自动裁剪并在备注提示。'],
            },
            {
                'type': 'summary',
                'title': '结论',
                'takeaways': [
                    '阶段二已形成“生成-检查-修复-保存”闭环。',
                    '主流程在缺少缩略图依赖时仍可稳定产出 PPTX。',
                    '后续可扩展更强模板能力与视觉模型 QA。',
                ],
            },
            {
                'type': 'references',
                'title': '参考资料',
                'items': ['https://github.com/scanny/python-pptx', 'LazyRAG 内部设计文档'],
            },
        ],
        'sources': ['https://python-pptx.readthedocs.io/en/latest/'],
    }


def _require_dict(payload: Any, step: str) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError(f'{step} returned non-dict payload: {type(payload).__name__}')
    return payload


def _check_success(payload: Dict[str, Any], step: str) -> Dict[str, Any]:
    if not payload.get('success'):
        raise RuntimeError(f'{step} failed: {json.dumps(payload, ensure_ascii=False)}')
    return payload


def main() -> int:
    phase2_root = Path('./tmp/lazyrag_pptx_phase2').resolve()
    os.environ.setdefault('LAZYRAG_UPLOAD_ROOT', str(phase2_root / 'uploads'))

    _ensure_import_path()

    from chat.pptx.schema import normalize_deck_schema, repair_deck_schema_for_pptx, validate_deck_schema
    from chat.tools.pptx import artifact_save, pptx_create_from_schema, pptx_parse, pptx_qa, pptx_render_thumbnails

    raw_schema = _sample_phase2_schema()

    normalized = normalize_deck_schema(raw_schema)
    if not isinstance(normalized, dict) or not normalized.get('slides'):
        raise RuntimeError('normalize_deck_schema returned invalid result')
    print('Normalized schema: success', flush=True)

    validation = _check_success(_require_dict(validate_deck_schema(normalized), 'validate_deck_schema'), 'validate_deck_schema')
    working_schema = validation.get('normalized_schema') or normalized

    create_result = _check_success(_require_dict(pptx_create_from_schema(working_schema, filename='lazyrag_pptx_phase2_demo.pptx'), 'pptx_create_from_schema'), 'pptx_create_from_schema')
    pptx_path = Path(str(create_result.get('file_path') or '')).expanduser().resolve()
    if not pptx_path.exists():
        raise RuntimeError(f'PPTX output file not found: {pptx_path}')
    print(f'PPTX created: {pptx_path}', flush=True)

    parse_result = _check_success(_require_dict(pptx_parse(str(pptx_path)), 'pptx_parse'), 'pptx_parse')
    slide_count = int(parse_result.get('slide_count') or 0)
    print(f'Slide count: {slide_count}', flush=True)
    print(f"Parse success: {str(bool(parse_result.get('success'))).lower()}", flush=True)

    thumbnail_result = _require_dict(pptx_render_thumbnails(str(pptx_path), dpi=120), 'pptx_render_thumbnails')

    qa_result = _check_success(
        _require_dict(
            pptx_qa(
                str(pptx_path),
                deck_schema=working_schema,
                thumbnail_result=thumbnail_result,
            ),
            'pptx_qa',
        ),
        'pptx_qa',
    )

    # One light repair round if QA is not passed.
    final_pptx_path = pptx_path
    final_schema = working_schema
    final_parse = parse_result
    final_qa = qa_result
    final_thumbnail = thumbnail_result

    if not qa_result.get('passed'):
        repair = _check_success(
            _require_dict(repair_deck_schema_for_pptx(working_schema, qa_result), 'repair_deck_schema_for_pptx'),
            'repair_deck_schema_for_pptx',
        )
        repaired_schema = repair.get('repaired_schema')
        if not repaired_schema:
            raise RuntimeError('repair_deck_schema_for_pptx returned empty repaired_schema')

        create_result = _check_success(
            _require_dict(pptx_create_from_schema(repaired_schema, filename='lazyrag_pptx_phase2_demo_repaired.pptx'), 'pptx_create_from_schema(repair)'),
            'pptx_create_from_schema(repair)',
        )
        final_pptx_path = Path(str(create_result.get('file_path') or '')).expanduser().resolve()
        final_schema = repaired_schema
        final_parse = _check_success(_require_dict(pptx_parse(str(final_pptx_path)), 'pptx_parse(repair)'), 'pptx_parse(repair)')
        final_thumbnail = _require_dict(pptx_render_thumbnails(str(final_pptx_path), dpi=120), 'pptx_render_thumbnails(repair)')
        final_qa = _check_success(
            _require_dict(
                pptx_qa(
                    str(final_pptx_path),
                    deck_schema=final_schema,
                    thumbnail_result=final_thumbnail,
                ),
                'pptx_qa(repair)',
            ),
            'pptx_qa(repair)',
        )

    issue_count = int((final_qa.get('summary') or {}).get('issue_count') or 0)
    warning_count = int((final_qa.get('summary') or {}).get('warning_count') or 0)

    print(f"QA passed: {str(bool(final_qa.get('passed'))).lower()}", flush=True)
    print(f'Issue count: {issue_count}', flush=True)
    print(f'Warning count: {warning_count}', flush=True)

    if not final_qa.get('passed'):
        raise RuntimeError(f'Final QA did not pass: {json.dumps(final_qa, ensure_ascii=False)}')

    related = {}
    if isinstance(final_thumbnail, dict) and final_thumbnail.get('success'):
        related = {
            'pdf_path': final_thumbnail.get('pdf_path') or '',
            'thumbnail_paths': final_thumbnail.get('thumbnail_paths') or [],
        }

    artifact = _check_success(
        _require_dict(
            artifact_save(
                str(final_pptx_path),
                kind='pptx',
                filename='lazyrag_pptx_phase2_demo.pptx',
                related_artifacts=related or None,
            ),
            'artifact_save',
        ),
        'artifact_save',
    )

    artifact_path = Path(str(artifact.get('file_path') or '')).expanduser().resolve()
    if not artifact_path.exists():
        raise RuntimeError(f'Artifact saved path does not exist: {artifact_path}')

    download_url = artifact.get('absolute_download_url') or artifact.get('download_url') or ''

    print(f'Artifact saved: {artifact_path}', flush=True)
    print(f'Download URL: {download_url}', flush=True)

    thumb_status = 'success' if isinstance(final_thumbnail, dict) and final_thumbnail.get('success') else 'skipped'
    print(f'Thumbnail status: {thumb_status}', flush=True)
    print(f'Final PPTX path: {final_pptx_path}', flush=True)

    if isinstance(final_thumbnail, dict) and final_thumbnail.get('success'):
        print(f"PDF path: {final_thumbnail.get('pdf_path')}", flush=True)
        print(f"Thumbnail count: {len(final_thumbnail.get('thumbnail_paths') or [])}", flush=True)

    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr, flush=True)
        raise SystemExit(1) from exc
