from chat.components.lclm.text_sanitize import (
    contains_lclm_pollution,
    sanitize_lclm_text,
    sanitize_title,
)


def test_sanitize_lclm_text_strips_think_and_meta_prompt_echo():
    raw = (
        '<think>这是思考链</think>\n\n'
        '让我分析一下当前节点信息。\n\n'
        '用户要求我只写当前节点。\n\n'
        '## 正文\n\n'
        'LazyRAG 通过先大纲后写作来提升长文本可控性。'
    )
    cleaned = sanitize_lclm_text(raw)

    assert '<think>' not in cleaned.lower()
    assert '让我分析' not in cleaned
    assert '用户要求我' not in cleaned
    assert 'LazyRAG' in cleaned
    assert contains_lclm_pollution(cleaned) is False


def test_sanitize_title_falls_back_from_placeholder():
    title = sanitize_title('Survey on <QUERY>', 'LazyRAG 长文本生成技术路线', fallback='长文报告')
    assert '<QUERY>' not in title
    assert 'LazyRAG' in title
