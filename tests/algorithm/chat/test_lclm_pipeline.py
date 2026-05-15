import asyncio
import importlib.util
import re
from pathlib import Path

import pytest

from chat.components.lclm.evidence import EvidenceCollector
from chat.components.lclm.pipeline import OutlineLongFormPipeline
from chat.components.lclm.planner import LCLMPlanner
from chat.components.lclm.schemas import LongFormTaskSchema, OutlineNode, is_story_task


def test_planner_fallback_when_outline_json_invalid():
    def fake_llm(prompt: str):
        if 'Long-Form 任务解析器' in prompt:
            return '{"query":"测试任务","language":"zh","genre":"report","source_policy":"kb_first"}'
        if 'Outline Planner' in prompt:
            return '{"nodes":[{"node_id":"1","title":"bad"'
        if '请修复下面内容为合法 JSON' in prompt:
            return 'not json'
        return ''

    planner = LCLMPlanner(llm_callable=fake_llm)
    task, title, nodes, warnings = planner.plan('请详细分析系统设计', {'lclm_mode': 'auto'})

    assert isinstance(task, LongFormTaskSchema)
    assert title
    assert nodes
    assert any('fallback' in warning for warning in warnings)


def test_evidence_card_keeps_kb_ref(monkeypatch):
    def kb_search(**kwargs):
        del kwargs
        return {
            'success': True,
            'items': [
                {
                    'file_name': 'doc-a',
                    'text': '证据内容',
                    'score': 1.3,
                    'ref': '[[3]]',
                    'docid': 'd1',
                    'uid': 'u1',
                }
            ],
        }

    collector = EvidenceCollector(llm_callable=None)
    task = LongFormTaskSchema(query='测试', source_policy='kb_first')
    node = OutlineNode(
        node_id='1',
        title='背景',
        level=1,
        parent_id=None,
        goal='说明背景',
        expected_words=200,
        retrieval_queries=['测试 背景'],
    )
    cards, _warnings = collector.collect(
        task=task,
        node=node,
        runtime_params={
            'kb_id': 'ds_test',
            'lclm_node_evidence_topk': 5,
            'lclm_kb_search': kb_search,
        },
    )

    assert cards
    assert cards[0].ref == '[[3]]'


def test_pipeline_warns_when_citation_required_but_no_evidence():
    runtime = {
        'lclm_mode': 'force',
        'lclm_save_artifact': False,
        'lclm_use_llm': False,
        'lclm_section_min_words': 120,
        'lclm_section_max_words': 280,
    }
    pipeline = OutlineLongFormPipeline(runtime_params=runtime)
    task = LongFormTaskSchema(
        query='测试任务',
        language='zh',
        genre='report',
        citation_required=True,
        source_policy='kb_first',
    )
    outline = [
        OutlineNode(
            node_id='1',
            title='背景',
            level=1,
            parent_id=None,
            goal='说明背景',
            expected_words=180,
            retrieval_queries=['背景'],
        )
    ]
    pipeline.planner.plan = lambda query, runtime_params: (task, '测试报告', outline, [])
    pipeline.collector.collect = lambda **kwargs: ([], ['章节 1 未检索到可用证据卡。'])

    result, state = pipeline.run(query='测试任务', history=[])

    assert result['lclm']['enabled'] is True
    assert state.warnings
    assert any('证据' in warning for warning in state.warnings)
    assert 'TBD' not in state.final_markdown
    assert '待补充' not in state.final_markdown
    assert re.search(r'\[\[\d+\]\]', state.final_markdown) is None


def test_lclm_pipeline_emits_progress_events():
    events = []

    runtime = {
        'lclm_mode': 'force',
        'lclm_save_artifact': False,
        'lclm_use_llm': False,
        'lclm_max_outline_nodes': 1,
        'lclm_max_depth': 1,
        'lclm_node_evidence_topk': 0,
        'lclm_enable_evidence': False,
        'lclm_section_min_words': 80,
        'lclm_section_max_words': 120,
    }
    pipeline = OutlineLongFormPipeline(runtime_params=runtime, progress_callback=events.append)
    task = LongFormTaskSchema(
        query='测试长文本任务',
        original_query='测试长文本任务',
        language='zh',
        genre='report',
        citation_required=False,
        source_policy='kb_first',
    )
    outline = [
        OutlineNode(
            node_id='1',
            title='背景',
            level=1,
            parent_id=None,
            goal='说明背景',
            expected_words=100,
            retrieval_queries=['测试长文本任务 背景'],
        )
    ]
    pipeline.planner.plan = lambda query, runtime_params: (task, '测试报告', outline, [])
    pipeline.collector.collect = lambda **kwargs: ([], ['章节 1 已跳过证据检索：lclm_enable_evidence=false'])

    result, _state = pipeline.run(query='测试长文本任务', history=[])

    assert result['lclm']['enabled'] is True
    stages = [str(event.get('stage')) for event in events if isinstance(event, dict)]
    assert 'start' in stages
    assert 'planning_start' in stages
    assert 'planning_end' in stages
    assert 'writer_start' in stages
    assert 'writer_end' in stages
    assert 'compose_start' in stages
    assert 'compose_end' in stages
    assert stages[-1] == 'done'


def test_lclm_pipeline_formats_download_as_markdown_link():
    runtime = {
        'lclm_mode': 'force',
        'lclm_save_artifact': True,
        'lclm_use_llm': False,
        'lclm_max_outline_nodes': 1,
        'lclm_max_depth': 1,
        'lclm_node_evidence_topk': 0,
        'lclm_enable_evidence': False,
        'lclm_section_min_words': 80,
        'lclm_section_max_words': 120,
    }
    pipeline = OutlineLongFormPipeline(runtime_params=runtime)
    task = LongFormTaskSchema(
        query='测试长文本任务',
        original_query='测试长文本任务',
        language='zh',
        genre='report',
        citation_required=False,
        source_policy='kb_first',
    )
    outline = [
        OutlineNode(
            node_id='1',
            title='背景',
            level=1,
            parent_id=None,
            goal='说明背景',
            expected_words=100,
            retrieval_queries=['测试长文本任务 背景'],
        )
    ]
    pipeline.planner.plan = lambda query, runtime_params: (task, '测试报告', outline, [])
    pipeline.collector.collect = lambda **kwargs: ([], ['章节 1 已跳过证据检索：lclm_enable_evidence=false'])
    pipeline._save_artifact = lambda state, title: {
        'artifact': {
            'download_link': '/api/chat/artifacts/static-files/agent-results/test/report.md?sig=s&download=1',
            'download_url': '/api/chat/artifacts/static-files/agent-results/test/report.md?sig=s&download=1',
        },
        'download_link': '/api/chat/artifacts/static-files/agent-results/test/report.md?sig=s&download=1',
        'download_url': '/api/chat/artifacts/static-files/agent-results/test/report.md?sig=s&download=1',
    }

    result, _state = pipeline.run(query='测试长文本任务', history=[])

    assert '下载：[点击下载](/api/chat/artifacts/static-files/agent-results/test/report.md?sig=s&download=1)' in result['text']
    assert result['download_link'].startswith('/api/chat/artifacts/static-files/')


def test_story_query_uses_fiction_workflow_without_evidence():
    query = '请以“世界上的最后一个人类”为主题，写一篇至少有两个主人公、有对话、有剧情的长文本短篇小说'
    runtime = {
        'lclm_mode': 'force',
        'lclm_save_artifact': False,
        'lclm_use_llm': False,
        'lclm_max_outline_nodes': 4,
        'lclm_max_depth': 1,
        'lclm_section_min_words': 100,
        'lclm_section_max_words': 220,
    }
    pipeline = OutlineLongFormPipeline(runtime_params=runtime)

    result, state = pipeline.run(query=query, history=[])

    bad_terms = [
        '长文报告',
        '背景与问题定义',
        '方法路线总览',
        '关键分析维度',
        '对 LazyRAG 的启发',
        '推荐实施方案',
        '风险与测试建议',
        'KB 证据不足',
        '未检索到可用证据卡',
        '目前证据不足以支持更强结论',
    ]
    combined = result['text'] + '\n' + state.final_markdown
    assert is_story_task(state.task)
    assert state.task.genre == 'story'
    assert state.task.citation_required is False
    assert state.task.evidence_required is False
    assert result['lclm']['genre'] == 'story'
    assert result['lclm']['output_type'] == 'short_story'
    assert '已生成长文本小说' in result['text']
    assert all(term not in combined for term in bad_terms)
    assert re.search(r'\[\[\d+\]\]', combined) is None
    assert '“' in state.final_markdown or '"' in state.final_markdown
    assert '林岚' in state.final_markdown
    assert '黎明之声' in state.final_markdown


def test_lclm_stream_mode_outputs_text_and_artifact(monkeypatch):
    helper_path = Path(__file__).with_name('test_pipeline_agentic.py')
    spec = importlib.util.spec_from_file_location('agentic_test_helper', helper_path)
    helper = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(helper)
    try:
        agentic = helper._import_agentic_module(monkeypatch)
    except Exception as exc:  # pragma: no cover - environment compatibility fallback
        pytest.skip(f'agentic fake import unavailable in current env: {exc}')

    def fake_run_lclm_pipeline(*, query, history, runtime_params, progress_callback=None):
        assert query == '请做长文分析'
        if callable(progress_callback):
            progress_callback({'stage': 'planning_start', 'text': '正在规划大纲...'})
            progress_callback({'stage': 'planning_end', 'text': '已完成大纲规划，共 1 个章节。', 'outline_nodes': 1})
        return {
            'think': 'outline done',
            'text': '已生成长文本报告。\n\n下面是正文预览：\n这是预览内容。',
            'download_link': 'https://example.com/signed',
            'artifact': {'download_link': 'https://example.com/signed'},
        }

    monkeypatch.setattr(agentic, '_run_lclm_pipeline', fake_run_lclm_pipeline)
    monkeypatch.setattr(agentic, '_agentic_forward_stream', lambda **kwargs: ())

    class _FakeGlobals:
        _sid = 'lclm-stream-test'

        def get(self, key, default=None):
            return {}

        def _init_sid(self, sid):
            self._sid = sid

        def __setitem__(self, key, value):
            return None

    fake_globals = _FakeGlobals()
    agentic.lazyllm.globals = fake_globals
    agentic.lazyllm.locals = type(
        '_Locals',
        (),
        {
            '_sid': 'lclm-stream-test',
            '_init_sid': staticmethod(lambda sid: None),
            'get': staticmethod(lambda key, default=None: {}),
        },
    )()

    async def _collect():
        frames = []
        async for frame in agentic._lclm_forward_stream(
            query='请做长文分析',
            history=[],
            runtime_params={'stream_chunk_size': 12},
            global_sid='lclm-stream-test',
            local_sid='lclm-stream-test',
        ):
            frames.append(frame)
        return frames

    frames = asyncio.run(_collect())

    assert frames
    final_frame = frames[-1]
    progress_frames = frames[:-1]
    assert any(frame.get('think') for frame in progress_frames)
    assert all(frame.get('text') == '' for frame in progress_frames)
    assert final_frame.get('text')
    assert any(frame.get('artifact') or frame.get('download_link') for frame in frames)
    assert all(isinstance(frame.get('text'), str) for frame in frames)
    assert final_frame.get('finish_reason') == 'FINISH_REASON_STOP'
