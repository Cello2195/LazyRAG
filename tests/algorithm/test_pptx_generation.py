from __future__ import annotations

from pathlib import Path

from chat.tools import pptx as pptx_tools


def _sample_schema() -> dict:
    return {
        'title': 'LazyRAG Test Deck',
        'subtitle': 'PPTX generation test',
        'slides': [
            {'type': 'cover', 'title': '封面', 'subtitle': '测试'},
            {'type': 'toc', 'title': '目录', 'items': ['A', 'B', 'C']},
            {'type': 'content_bullets', 'title': '内容', 'bullets': ['点 1', '点 2', '点 3']},
            {
                'type': 'two_column',
                'title': '双栏',
                'left': {'title': '左侧', 'bullets': ['L1', 'L2']},
                'right': {'title': '右侧', 'bullets': ['R1', 'R2']},
            },
            {
                'type': 'comparison',
                'title': '比较',
                'left': {'title': '方案 A', 'bullets': ['快', '稳']},
                'right': {'title': '方案 B', 'bullets': ['灵活', '扩展']},
            },
            {
                'type': 'table',
                'title': '表格',
                'table': {
                    'headers': ['列 1', '列 2'],
                    'rows': [['A', 'B'], ['C', 'D']],
                },
            },
            {'type': 'summary', 'title': '总结', 'takeaways': ['可生成', '可解析', '可保存']},
        ],
    }


def test_sample_schema_generates_pptx_and_core_tools_work(tmp_path, monkeypatch):
    monkeypatch.setenv('LAZYRAG_UPLOAD_ROOT', str(tmp_path / 'uploads'))

    schema = _sample_schema()
    created = pptx_tools.pptx_create_from_schema(schema, filename='unit_demo.pptx')
    assert created.get('success') is True

    pptx_path = Path(created['file_path']).resolve()
    assert pptx_path.exists()
    assert pptx_path.suffix.lower() == '.pptx'

    parsed = pptx_tools.pptx_parse(str(pptx_path))
    assert parsed.get('success') is True
    assert int(parsed.get('slide_count') or 0) >= 7
    assert parsed.get('slides')

    qa = pptx_tools.pptx_qa(str(pptx_path), deck_schema=schema)
    assert qa.get('success') is True
    assert qa.get('passed') is True
    assert isinstance(qa.get('issues'), list)
    assert isinstance(qa.get('warnings'), list)

    saved = pptx_tools.artifact_save(str(pptx_path), kind='pptx', filename='unit_saved_demo.pptx')
    assert saved.get('success') is True
    saved_path = Path(saved['file_path']).resolve()
    assert saved_path.exists()
    assert saved.get('download_url')

    thumb = pptx_tools.pptx_render_thumbnails(str(pptx_path), dpi=96)
    assert isinstance(thumb, dict)
    if thumb.get('success'):
        assert int(thumb.get('page_count') or 0) >= 1
        assert len(thumb.get('thumbnail_paths') or []) >= 1
    else:
        assert thumb.get('error_message')
