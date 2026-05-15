from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlparse


_THINK_BLOCK_RE = re.compile(r'<think>[\s\S]*?</think>', re.IGNORECASE)
_UNCLOSED_THINK_RE = re.compile(r'<think>[\s\S]*$', re.IGNORECASE)
_MD_FENCE_RE = re.compile(r'^\s*```(?:json|yaml|yml|javascript|js)?\s*[\s\S]*?```\s*$', re.IGNORECASE)
_META_KEYWORDS = (
    '让我分析',
    '用户要求我',
    '我将',
    '当前节点信息',
    '关键约束',
    '证据卡为空',
    '证据卡（evidence_cards）',
    'evidence_cards',
    '工具策略',
    'hard_controls',
    'soft_controls',
    'retrieval_queries',
    'tool_policy',
    'node_id',
    'expected_words',
    'citation_required',
    '不要输出json',
    '只写当前节点',
    'query 字段为空',
)
_TITLE_BAD_EXACT = {
    '',
    '...',
    '<query>',
    'untitled',
    'survey on <query>',
}
_REPEATED_DOTS_RE = re.compile(r'^\.+$')
_PLACEHOLDER_RE = re.compile(r'(<\s*query\s*>|survey\s+on\s*<\s*query\s*>)', re.IGNORECASE)
_JSON_LIKE_RE = re.compile(r'^\s*[\{\[][\s\S]*[\}\]]\s*$')
_ARTIFACT_PATH_RE = re.compile(r'(/api/chat/artifacts/static-files/[^\s\)]+)')


def word_units(text: str) -> int:
    raw = str(text or '')
    zh = len(re.findall(r'[\u4e00-\u9fff]', raw))
    en = len(re.findall(r'[A-Za-z0-9]+', raw))
    base = zh + en * 2
    non_space = len(re.sub(r'\s+', '', raw))
    return max(base, non_space)


def strip_model_thinking(text: Any) -> str:
    raw = str(text or '')
    if not raw:
        return ''
    cleaned = _THINK_BLOCK_RE.sub('', raw)
    cleaned = _UNCLOSED_THINK_RE.sub('', cleaned)
    cleaned = cleaned.replace('<think>', '').replace('</think>', '')
    return cleaned


def is_bad_placeholder_text(text: Any) -> bool:
    raw = str(text or '').strip()
    lower = raw.lower()
    if not raw:
        return True
    if lower in _TITLE_BAD_EXACT:
        return True
    if _REPEATED_DOTS_RE.fullmatch(raw):
        return True
    if _PLACEHOLDER_RE.search(lower):
        return True
    return False


def sanitize_title(title: Any, original_query: str, *, fallback: str = '长文报告') -> str:
    raw = strip_model_thinking(title).strip()
    raw = raw.replace('<QUERY>', '').replace('<query>', '').strip()
    if is_bad_placeholder_text(raw):
        candidate = str(original_query or '').strip()
        if not candidate:
            candidate = fallback
        if '报告' not in candidate and '方案' not in candidate:
            candidate = f'{candidate} - {fallback}'
        return candidate
    return raw


def contains_lclm_pollution(text: Any) -> bool:
    raw = str(text or '')
    if not raw:
        return False
    lower = raw.lower()
    if '<think>' in lower or '</think>' in lower:
        return True
    if _PLACEHOLDER_RE.search(lower):
        return True
    return any(keyword in lower for keyword in _META_KEYWORDS)


def _remove_meta_paragraphs(text: str) -> str:
    parts = re.split(r'\n\s*\n', str(text or ''))
    kept: list[str] = []
    for part in parts:
        block = str(part or '').strip()
        if not block:
            continue
        lower = block.lower()
        if _MD_FENCE_RE.match(block):
            continue
        if _JSON_LIKE_RE.match(block) and any(k in lower for k in _META_KEYWORDS):
            continue
        if any(keyword in lower for keyword in _META_KEYWORDS):
            continue
        if 'query 字段为空' in lower:
            continue
        kept.append(block)
    return '\n\n'.join(kept).strip()


def sanitize_lclm_text(text: Any) -> str:
    cleaned = strip_model_thinking(text)
    cleaned = cleaned.replace('<QUERY>', '').replace('<query>', '')
    cleaned = cleaned.replace('Survey on <QUERY>', '').replace('survey on <query>', '')
    cleaned = _remove_meta_paragraphs(cleaned)
    # Remove standalone placeholder lines after paragraph filtering.
    lines = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if is_bad_placeholder_text(stripped):
            continue
        if 'query 字段为空' in lower:
            continue
        if any(keyword in lower for keyword in _META_KEYWORDS):
            continue
        lines.append(line)
    return '\n'.join(lines).strip()


def extract_length_constraints(query: str) -> dict[str, Optional[int]]:
    text = str(query or '')
    lower = text.lower()
    result: dict[str, Optional[int]] = {
        'max_units': None,
        'min_units': None,
    }
    m = re.search(r'(\d{2,5})\s*字以内', text)
    if m:
        result['max_units'] = int(m.group(1))
    m = re.search(r'不少于\s*(\d{2,5})\s*字', text)
    if m:
        result['min_units'] = int(m.group(1))
    m = re.search(r'within\s+(\d{2,5})\s*words?', lower)
    if m and result['max_units'] is None:
        result['max_units'] = int(m.group(1)) * 2
    m = re.search(r'(\d{2,5})\s*words?', lower)
    if m and result['max_units'] is None and ('within' in lower or '以内' in text):
        result['max_units'] = int(m.group(1)) * 2
    return result


def trim_text_to_units(text: str, max_units: Optional[int]) -> str:
    if not max_units or max_units <= 0:
        return str(text or '').strip()
    src = str(text or '').strip()
    if not src:
        return ''
    if word_units(src) <= max_units:
        return src
    out = []
    used = 0
    for ch in src:
        if ch.isspace():
            ch_units = 0
        elif re.match(r'[\u4e00-\u9fff]', ch):
            ch_units = 1
        elif re.match(r'[A-Za-z0-9]', ch):
            ch_units = 2
        else:
            ch_units = 1
        if used + ch_units > max_units:
            break
        out.append(ch)
        used += ch_units
    trimmed = ''.join(out).rstrip()
    if not trimmed:
        return src[: max(40, min(len(src), 120))]
    return trimmed


def make_rule_fallback_text(original_query: str, *, max_units: Optional[int] = None) -> str:
    topic = sanitize_title(original_query, original_query, fallback='长文本任务')
    body = (
        f'本报告围绕“{topic}”展开。核心思路是先构建层级大纲，再按章节进行检索、写作、审查与修复，'
        '最后将结果保存为可下载文件。该流程把一次性回答转化为可控的多阶段工程过程，便于质量检查与迭代。'
    )
    return trim_text_to_units(body, max_units)


def normalize_artifact_link(url: str) -> str:
    raw = str(url or '').strip()
    if not raw:
        return ''
    if raw.startswith('/api/chat/artifacts/static-files/'):
        return raw
    parsed = urlparse(raw)
    if parsed.path.startswith('/api/chat/artifacts/static-files/'):
        out = parsed.path
        if parsed.query:
            out = f'{out}?{parsed.query}'
        return out
    m = _ARTIFACT_PATH_RE.search(raw)
    if m:
        return m.group(1)
    return raw
