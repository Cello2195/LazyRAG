from __future__ import annotations

import os
import re
from typing import Any, Mapping, Tuple

_LCLM_KEYWORDS = (
    '详细调研',
    '深度调研',
    '综述',
    '长文本',
    '长文',
    '技术报告',
    '研究现状',
    '论文总结',
    '技术路线',
    '系统设计',
    '详细分析',
    '完整分析',
    '写一篇',
    '生成一份',
    '整理成文档',
    '白皮书',
    'project analysis',
    'literature review',
    'long-form',
    'long form',
    'survey',
    'proposal',
    'technical plan',
)

_PPTX_HARD_KEYWORDS = (
    'ppt',
    'pptx',
    'powerpoint',
    'slides',
    'deck',
    '幻灯片',
    '演示文稿',
)

_PPTX_SOFT_KEYWORDS = (
    '汇报',
    'slide',
)

_PPTX_ACTION_KEYWORDS = (
    '生成',
    '制作',
    '做一份',
    '给我做',
    'create',
    'make',
    'build',
    'design',
    '导出',
)

_SHORT_ANSWER_KEYWORDS = (
    '简短回答',
    '简单说',
    '一句话',
    '不用长文',
    '只要命令',
    '直接给命令',
    'just one line',
    'short answer',
    'brief answer',
)

_DEFAULT_MODE = 'auto'
_SUPPORTED_MODES = {'auto', 'off', 'force'}


def _normalize_text(value: Any) -> str:
    return str(value or '').strip().lower()


def _query_word_len(text: str) -> int:
    no_space = re.sub(r'\s+', '', text)
    return len(no_space)


def contains_lclm_intent(query: str) -> bool:
    text = _normalize_text(query)
    if not text:
        return False
    if any(keyword in text for keyword in _SHORT_ANSWER_KEYWORDS):
        return False
    if any(keyword in text for keyword in _LCLM_KEYWORDS):
        return True
    # Heuristic: longer request with explicit writing asks.
    if _query_word_len(text) >= 24 and any(k in text for k in ('报告', '方案', '调研', '分析', '总结')):
        return True
    return False


def contains_pptx_intent(query: str) -> bool:
    text = _normalize_text(query)
    if not text:
        return False
    if any(keyword in text for keyword in _PPTX_HARD_KEYWORDS):
        return True
    if any(keyword in text for keyword in _PPTX_SOFT_KEYWORDS):
        return any(action in text for action in _PPTX_ACTION_KEYWORDS)
    return False


def contains_short_answer_intent(query: str) -> bool:
    text = _normalize_text(query)
    if not text:
        return False
    return any(keyword in text for keyword in _SHORT_ANSWER_KEYWORDS)


def normalize_lclm_mode(value: Any, *, fallback: str = _DEFAULT_MODE) -> str:
    mode = _normalize_text(value)
    if mode in _SUPPORTED_MODES:
        return mode
    return fallback


def resolve_lclm_mode(runtime_params: Mapping[str, Any] | None = None) -> str:
    params = runtime_params or {}
    req_mode = None
    if isinstance(params, Mapping):
        req_mode = params.get('lclm_mode')
        filters = params.get('filters')
        if req_mode in (None, '') and isinstance(filters, Mapping):
            req_mode = filters.get('lclm_mode')

    env_mode = os.getenv('LAZYRAG_LCLM_MODE')
    if req_mode not in (None, ''):
        return normalize_lclm_mode(req_mode)
    return normalize_lclm_mode(env_mode)


def should_use_lclm(query: str, runtime_params: Mapping[str, Any] | None = None) -> Tuple[bool, str]:
    mode = resolve_lclm_mode(runtime_params)
    text = _normalize_text(query)

    if not text:
        return False, 'empty_query'

    if contains_pptx_intent(text):
        return False, 'pptx_intent'

    if mode == 'off':
        return False, 'mode_off'

    if contains_short_answer_intent(text):
        return False, 'short_answer_intent'

    if mode == 'force':
        return True, 'mode_force'

    if contains_lclm_intent(text):
        return True, 'keyword_match'

    return False, 'not_longform'
