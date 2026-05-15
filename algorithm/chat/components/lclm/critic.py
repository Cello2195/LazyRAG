from __future__ import annotations

import json
import re
from typing import Any, Callable, List, Mapping, Optional

from chat.components.lclm.schemas import LongFormTaskSchema, OutlineNode, is_story_task, parse_json_text
from chat.prompts.lclm import SECTION_CRITIC_PROMPT


_PLACEHOLDER_RE = re.compile(
    r'\b(tbd|todo|n/a|na)\b|待补充|示例内容|占位|lorem ipsum',
    re.IGNORECASE,
)
_CITATION_RE = re.compile(r'\[\[\d+\]\]')
_HEADING_RE = re.compile(r'^\s{0,3}#{1,6}\s+\S+', re.MULTILINE)
_REPORT_TERMS = (
    '本报告',
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
)


def _runtime_int(runtime_params: Mapping[str, Any], key: str, default: int) -> int:
    value = runtime_params.get(key)
    if value in (None, ''):
        return default
    try:
        return int(value)
    except Exception:
        return default


def _runtime_bool(runtime_params: Mapping[str, Any], key: str, default: bool) -> bool:
    value = runtime_params.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {'1', 'true', 'yes', 'on'}:
        return True
    if text in {'0', 'false', 'no', 'off'}:
        return False
    return default


def _word_units(text: str) -> int:
    zh = len(re.findall(r'[\u4e00-\u9fff]', text))
    en = len(re.findall(r'[A-Za-z0-9]+', text))
    return zh + en * 2


def _fill_prompt(template: str, **kwargs: Any) -> str:
    text = str(template)
    for key, value in kwargs.items():
        text = text.replace(f'{{{key}}}', str(value))
    return text


def _normalized_paragraphs(text: str) -> List[str]:
    parts = []
    for paragraph in re.split(r'\n\s*\n', text):
        normalized = re.sub(r'\s+', ' ', paragraph).strip().lower()
        if normalized:
            parts.append(normalized)
    return parts


def _build_result(
    *,
    passed: bool,
    issues: list[str],
    repair_instructions: list[str],
    scores: Optional[dict[str, int]] = None,
) -> dict[str, Any]:
    default_scores = {
        'task_completion': 5 if passed else 3,
        'evidence_grounding': 5 if passed else 3,
        'coherence': 5 if passed else 3,
        'style': 5 if passed else 3,
        'redundancy': 5 if passed else 3,
    }
    if isinstance(scores, dict):
        default_scores.update(
            {
                key: int(max(1, min(5, int(value))))
                for key, value in scores.items()
                if key in default_scores
            }
        )
    return {
        'passed': bool(passed),
        'scores': default_scores,
        'issues': issues,
        'repair_instructions': repair_instructions,
    }


def _has_dialogue(text: str) -> bool:
    return bool(re.search(r'[“"].+?[”"]', str(text or '')) or re.search(r'^[\u4e00-\u9fffA-Za-z]{1,12}[:：].+', str(text or ''), re.MULTILINE))


def _story_critic(
    *,
    section_text: str,
    task: LongFormTaskSchema,
    node: OutlineNode,
    runtime_params: Mapping[str, Any],
) -> dict[str, Any]:
    issues: list[str] = []
    repairs: list[str] = []
    text = str(section_text or '').strip()
    if not text:
        return _build_result(
            passed=False,
            issues=['场景内容为空。'],
            repair_instructions=['补写小说正文，包含人物行动、场景描写和剧情推进。'],
        )
    if any(term in text for term in _REPORT_TERMS):
        issues.append('场景混入报告/证据/RAG 话术。')
        repairs.append('删除报告分析语言，只保留小说正文。')
    if _CITATION_RE.search(text):
        issues.append('小说场景不应包含 citation 占位符。')
        repairs.append('移除 [[n]] 引用。')
    if not _has_dialogue(text):
        issues.append('场景缺少真实对话。')
        repairs.append('加入至少一段角色之间的直接对话。')
    units = _word_units(text)
    min_words = _runtime_int(runtime_params, 'lclm_section_min_words', 120)
    if units < max(60, int(min_words * 0.5)):
        issues.append(f'场景长度偏短（约 {units} 字）。')
        repairs.append('补充动作、环境和人物选择。')
    topic = task.original_query or task.query
    if '最后一个人类' in topic and '最后' not in text and '人类' not in text:
        issues.append('场景没有贴合“世界上的最后一个人类”主题。')
        repairs.append('明确呈现最后一个人类的处境或选择。')
    return _build_result(passed=not issues, issues=issues, repair_instructions=repairs)


def _rule_critic(
    *,
    section_text: str,
    task: LongFormTaskSchema,
    node: OutlineNode,
    runtime_params: Mapping[str, Any],
) -> dict[str, Any]:
    if is_story_task(task):
        return _story_critic(
            section_text=section_text,
            task=task,
            node=node,
            runtime_params=runtime_params,
        )

    issues: list[str] = []
    repairs: list[str] = []
    text = str(section_text or '').strip()

    if not text:
        issues.append('章节内容为空。')
        repairs.append('补齐本节正文，至少包含背景、分析和结论三部分。')
        return _build_result(passed=False, issues=issues, repair_instructions=repairs)

    content_without_headings = '\n'.join(
        line for line in text.splitlines() if not line.strip().startswith('#')
    ).strip()
    if not content_without_headings:
        issues.append('章节只有标题没有正文。')
        repairs.append('补充实质段落内容，不要只保留标题。')

    min_words = _runtime_int(runtime_params, 'lclm_section_min_words', 180)
    max_words = _runtime_int(runtime_params, 'lclm_section_max_words', 900)
    units = _word_units(text)
    if units < max(60, int(min_words * 0.6)):
        issues.append(f'章节长度偏短（约 {units} 字）。')
        repairs.append('补充证据解释、场景边界与结论。')
    if units > int(max_words * 1.6):
        issues.append(f'章节长度过长（约 {units} 字）。')
        repairs.append('压缩重复内容，保留核心论点和关键证据。')

    if _PLACEHOLDER_RE.search(text):
        issues.append('章节包含占位符（如 TBD/待补充/N/A）。')
        repairs.append('移除占位符并替换为可用内容。')

    paragraphs = _normalized_paragraphs(text)
    if len(paragraphs) >= 2 and len(set(paragraphs)) < len(paragraphs):
        issues.append('章节存在重复段落。')
        repairs.append('合并或删除重复段落。')

    if task.citation_required and not _CITATION_RE.search(text):
        if '证据不足' not in text:
            issues.append('章节缺少引用标记。')
            repairs.append('在有证据的事实句后补充 [[n]]，证据不足时明确写明限制。')

    if not _HEADING_RE.search(f'## {node.title}\n{text}'):
        issues.append('章节标题层级异常。')
        repairs.append('确保章节由 H2/H3 标题和正文组成。')

    passed = len(issues) == 0
    return _build_result(passed=passed, issues=issues, repair_instructions=repairs)


class SectionCritic:
    def __init__(self, llm_callable: Optional[Callable[[str], Any]] = None):
        self._llm = llm_callable

    def _call_llm(self, prompt: str) -> Optional[str]:
        if not callable(self._llm):
            return None
        try:
            out = self._llm(prompt)
        except Exception:
            return None
        if out is None:
            return None
        if isinstance(out, dict):
            text = out.get('text') or out.get('content') or out.get('message')
            if isinstance(text, str):
                return text
            return json.dumps(out, ensure_ascii=False)
        return str(out)

    def evaluate(
        self,
        *,
        section_text: str,
        task: LongFormTaskSchema,
        node: OutlineNode,
        runtime_params: Mapping[str, Any],
    ) -> dict[str, Any]:
        rule_result = _rule_critic(
            section_text=section_text,
            task=task,
            node=node,
            runtime_params=runtime_params,
        )
        use_llm_critic = _runtime_bool(runtime_params, 'lclm_enable_llm_critic', False)
        if not use_llm_critic or not callable(self._llm):
            return rule_result

        prompt = _fill_prompt(
            SECTION_CRITIC_PROMPT,
            task_json=json.dumps(task.to_dict(), ensure_ascii=False, indent=2),
            node_json=json.dumps(node.to_dict(), ensure_ascii=False, indent=2),
            section_text=section_text,
        )
        raw = self._call_llm(prompt)
        parsed = parse_json_text(raw, default={})
        if not isinstance(parsed, dict):
            return rule_result

        llm_passed = bool(parsed.get('passed', True))
        llm_issues = [str(x) for x in (parsed.get('issues') or []) if str(x).strip()]
        llm_repairs = [str(x) for x in (parsed.get('repair_instructions') or []) if str(x).strip()]
        llm_scores = parsed.get('scores') if isinstance(parsed.get('scores'), dict) else {}

        merged_issues = list(dict.fromkeys((rule_result.get('issues') or []) + llm_issues))
        merged_repairs = list(dict.fromkeys((rule_result.get('repair_instructions') or []) + llm_repairs))
        merged_passed = bool(rule_result.get('passed')) and llm_passed and not merged_issues
        return _build_result(
            passed=merged_passed,
            issues=merged_issues,
            repair_instructions=merged_repairs,
            scores=llm_scores,
        )


def validate_document_markdown(markdown: str) -> dict[str, Any]:
    text = str(markdown or '').strip()
    issues: list[str] = []
    if not text:
        issues.append('全文为空。')
    if _PLACEHOLDER_RE.search(text):
        issues.append('全文仍包含占位符。')
    if text.count('## ') < 3:
        issues.append('全文章节层级不足（缺少足够的 H2 标题）。')
    if issues:
        return _build_result(
            passed=False,
            issues=issues,
            repair_instructions=['补齐章节结构并移除占位符。'],
        )
    return _build_result(passed=True, issues=[], repair_instructions=[])
