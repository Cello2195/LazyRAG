import asyncio
import importlib.util
import re
from pathlib import Path

import pytest

from chat.components.lclm.evidence import EvidenceCollector
from chat.components.lclm.pipeline import OutlineLongFormPipeline
from chat.components.lclm.planner import LCLMPlanner
from chat.components.lclm.schemas import LongFormTaskSchema, OutlineNode


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

    def fake_run_lclm_pipeline(*, query, history, runtime_params):
        assert query == '请做长文分析'
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
    assert any(frame.get('text') for frame in frames)
    assert any(frame.get('artifact') or frame.get('download_link') for frame in frames)
