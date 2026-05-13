from chat.components.lclm.detector import (
    contains_lclm_intent,
    contains_pptx_intent,
    should_use_lclm,
)


def test_lclm_detector_matches_longform_request():
    query = '请详细调研一下大模型长文本写作现状，并形成结构化报告'
    enabled, reason = should_use_lclm(query, {'lclm_mode': 'auto'})

    assert contains_lclm_intent(query) is True
    assert enabled is True
    assert reason in {'keyword_match', 'mode_force'}


def test_lclm_detector_skips_pptx_request():
    query = '帮我生成一个 PPT，主题是大模型应用'
    enabled, reason = should_use_lclm(query, {'lclm_mode': 'auto'})

    assert contains_pptx_intent(query) is True
    assert enabled is False
    assert reason == 'pptx_intent'


def test_lclm_detector_skips_short_bug_question():
    enabled, reason = should_use_lclm('这个报错是什么意思', {'lclm_mode': 'auto'})

    assert enabled is False
    assert reason in {'not_longform', 'short_answer_intent'}


def test_lclm_detector_respects_env_off(monkeypatch):
    monkeypatch.setenv('LAZYRAG_LCLM_MODE', 'off')
    enabled, reason = should_use_lclm('请详细分析这个系统设计问题', {})

    assert enabled is False
    assert reason == 'mode_off'


def test_lclm_detector_respects_env_force(monkeypatch):
    monkeypatch.setenv('LAZYRAG_LCLM_MODE', 'force')
    enabled, reason = should_use_lclm('请给我做一个完整分析', {})

    assert enabled is True
    assert reason == 'mode_force'


def test_lclm_detector_force_still_respects_pptx_priority(monkeypatch):
    monkeypatch.setenv('LAZYRAG_LCLM_MODE', 'force')
    enabled, reason = should_use_lclm('请帮我生成PPT', {})

    assert enabled is False
    assert reason == 'pptx_intent'
