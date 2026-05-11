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


def _sample_deck_schema() -> Dict[str, Any]:
    return {
        'title': 'LazyRAG PPTX Generation Demo',
        'subtitle': 'First-stage integration self-check',
        'language': 'zh',
        'theme': {
            'name': 'lazyrag_demo',
            'primary': '1F2937',
            'secondary': '4B5563',
            'accent': '0EA5E9',
            'background': 'FFFFFF',
            'muted_background': 'F1F5F9',
            'font_face': 'Microsoft YaHei',
        },
        'slides': [
            {
                'type': 'cover',
                'title': 'LazyRAG PPTX Demo',
                'subtitle': '可编辑的演示文稿自动生成',
            },
            {
                'type': 'toc',
                'title': '目录',
                'items': [
                    '需求与目标',
                    '技术路线',
                    '能力对比',
                    '里程碑计划',
                    '总结',
                ],
            },
            {
                'type': 'content_bullets',
                'title': '需求与目标',
                'bullets': [
                    '支持从 deck_schema 直接生成可编辑 PPTX',
                    '支持基础解析与质量检查',
                    '支持 Artifact 保存并返回路径/链接',
                ],
            },
            {
                'type': 'two_column',
                'title': '技术路线',
                'left': {
                    'title': '第一阶段',
                    'bullets': [
                        'Python 技术栈',
                        'python-pptx 渲染',
                        '轻量规则 QA',
                    ],
                },
                'right': {
                    'title': '后续阶段',
                    'bullets': [
                        '模板体系与主题升级',
                        '增强视觉 QA',
                        '多渲染器扩展',
                    ],
                },
            },
            {
                'type': 'comparison',
                'title': '方案比较',
                'left': {
                    'title': '当前 MVP',
                    'bullets': [
                        '依赖轻量，易部署',
                        '端到端可运行',
                        '适合快速验证',
                    ],
                },
                'right': {
                    'title': '复杂模板方案',
                    'bullets': [
                        '视觉表达更丰富',
                        '实现复杂度更高',
                        '维护成本更高',
                    ],
                },
            },
            {
                'type': 'table',
                'title': '里程碑计划',
                'table': {
                    'headers': ['阶段', '目标', '交付'],
                    'rows': [
                        ['Phase 1', '主流程可用', 'PPTX/Parse/QA/Artifact'],
                        ['Phase 2', '模板增强', '主题化模板库'],
                        ['Phase 3', '体验完善', '缩略图与可视化 QA'],
                    ],
                },
                'bullets': ['注：里程碑可按项目节奏调整。'],
            },
            {
                'type': 'summary',
                'title': '总结',
                'takeaways': [
                    '第一阶段已打通真实 PPTX 生成链路',
                    '输出文件可解析、可 QA、可持久化',
                    '缩略图能力在缺少转换环境时可优雅降级',
                ],
            },
        ],
    }


def _require_success(result: Dict[str, Any], step: str) -> Dict[str, Any]:
    if not isinstance(result, dict):
        raise RuntimeError(f'{step} returned non-dict result: {type(result).__name__}')
    if not result.get('success'):
        raise RuntimeError(f'{step} failed: {json.dumps(result, ensure_ascii=False)}')
    return result


def main() -> int:
    debug_root = Path('./tmp/lazyrag_pptx_debug').resolve()
    os.environ.setdefault('LAZYRAG_UPLOAD_ROOT', str(debug_root / 'uploads'))

    _ensure_import_path()
    from chat.tools.pptx import (  # pylint: disable=import-outside-toplevel
        artifact_save,
        pptx_create_from_schema,
        pptx_parse,
        pptx_qa,
        pptx_render_thumbnails,
    )

    schema = _sample_deck_schema()

    created = _require_success(
        pptx_create_from_schema(schema, filename='lazyrag_pptx_demo.pptx'),
        'pptx_create_from_schema',
    )
    pptx_path = Path(str(created.get('file_path') or '')).expanduser().resolve()
    if not pptx_path.exists():
        raise RuntimeError(f'generated pptx does not exist: {pptx_path}')

    parsed = _require_success(pptx_parse(str(pptx_path)), 'pptx_parse')
    qa_result = _require_success(
        pptx_qa(str(pptx_path), deck_schema=schema),
        'pptx_qa',
    )
    if not qa_result.get('passed'):
        raise RuntimeError(f'qa did not pass: {json.dumps(qa_result, ensure_ascii=False)}')

    saved = _require_success(
        artifact_save(str(pptx_path), kind='pptx', filename='lazyrag_pptx_demo.pptx'),
        'artifact_save',
    )
    artifact_path = Path(str(saved.get('file_path') or '')).expanduser().resolve()
    if not artifact_path.exists():
        raise RuntimeError(f'saved artifact does not exist: {artifact_path}')

    thumb_result = pptx_render_thumbnails(str(pptx_path), dpi=120)
    thumbnail_status = 'success' if thumb_result.get('success') else 'skipped'
    if not thumb_result.get('success'):
        print(
            f"Thumbnail warning: {thumb_result.get('error_message') or thumb_result.get('reason')}",
            flush=True,
        )

    download_url = (
        saved.get('absolute_download_url')
        or saved.get('download_url')
        or (saved.get('artifact') or {}).get('download_url')
        or ''
    )

    print(f'PPTX created: {pptx_path}', flush=True)
    print(f"Slide count: {parsed.get('slide_count')}", flush=True)
    print(f"QA passed: {str(bool(qa_result.get('passed'))).lower()}", flush=True)
    print(f'Artifact path: {artifact_path}', flush=True)
    print(f'Download URL: {download_url}', flush=True)
    print(f'Thumbnail status: {thumbnail_status}', flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr, flush=True)
        raise SystemExit(1) from exc
