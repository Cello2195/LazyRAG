import json

from chat.components.lclm.schemas import (
    EvidenceCard,
    LongFormTaskSchema,
    OutlineNode,
    coerce_outline_nodes,
    coerce_task_schema,
)


def test_outline_node_is_json_serializable():
    card = EvidenceCard(
        evidence_id='ev-1',
        source_type='kb',
        title='Doc A',
        ref='[[1]]',
        snippet='证据片段',
        supported_claims=['claim-1'],
        confidence=0.9,
        metadata={'docid': 'd1'},
    )
    node = OutlineNode(
        node_id='1.1',
        title='技术机制',
        level=2,
        parent_id='1',
        goal='解释核心机制',
        expected_words=220,
        evidence_needs=['原理依据'],
        retrieval_queries=['机制 原理'],
        evidence_cards=[card],
        status='checked',
    )

    payload = node.to_dict()
    encoded = json.dumps(payload, ensure_ascii=False)
    decoded = json.loads(encoded)

    assert decoded['node_id'] == '1.1'
    assert decoded['evidence_cards'][0]['ref'] == '[[1]]'


def test_coerce_task_schema_and_outline_nodes():
    task = coerce_task_schema(
        '{"query":"写一份技术报告","language":"zh","genre":"report"}',
        query='写一份技术报告',
    )
    assert isinstance(task, LongFormTaskSchema)
    assert task.language == 'zh'
    assert task.genre == 'report'

    raw_outline = {
        'title': '测试大纲',
        'nodes': [
            {
                'node_id': '1',
                'title': '背景',
                'level': 1,
                'goal': '说明背景',
                'expected_words': 180,
                'retrieval_queries': ['背景 现状'],
            }
        ],
    }
    nodes = coerce_outline_nodes(
        raw_outline,
        max_nodes=8,
        max_depth=3,
        default_words=200,
    )
    assert len(nodes) == 1
    assert nodes[0].title == '背景'
    assert nodes[0].expected_words == 180
