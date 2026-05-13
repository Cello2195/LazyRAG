from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional

from chat.components.lclm.schemas import EvidenceCard, LongFormTaskSchema, OutlineNode
from chat.prompts.lclm import SECTION_WRITER_PROMPT


_CITATION_REF_RE = re.compile(r'\[\[\d+\]\]')


def _word_units(text: str) -> int:
    zh = len(re.findall(r'[\u4e00-\u9fff]', text))
    en = len(re.findall(r'[A-Za-z0-9]+', text))
    return zh + en * 2


def _shorten(text: str, limit: int = 120) -> str:
    raw = str(text or '').strip()
    if len(raw) <= limit:
        return raw
    return f'{raw[:limit]}...'


def _summary_from_text(text: str, limit: int = 90) -> str:
    compact = re.sub(r'\s+', ' ', str(text or '')).strip()
    return compact[:limit]


def _used_citations(text: str, cards: list[EvidenceCard]) -> list[str]:
    refs = set(_CITATION_REF_RE.findall(text))
    used: list[str] = []
    for card in cards:
        if card.ref and (card.ref in refs or card.ref.startswith('http')):
            used.append(card.ref)
    return used


def _fill_prompt(template: str, **kwargs: Any) -> str:
    text = str(template)
    for key, value in kwargs.items():
        text = text.replace(f'{{{key}}}', str(value))
    return text


def _source_suffix(card: EvidenceCard) -> str:
    ref = str(card.ref or '').strip()
    if not ref:
        return ''
    if _CITATION_REF_RE.fullmatch(ref):
        return ref
    return f'（来源：{ref}）'


@dataclass
class SectionWriteResult:
    section_markdown: str
    section_summary: str
    used_citations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class SectionWriter:
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

    def _rule_write(
        self,
        *,
        task: LongFormTaskSchema,
        node: OutlineNode,
        evidence_cards: list[EvidenceCard],
        previous_section_summary: str,
    ) -> SectionWriteResult:
        warnings: list[str] = []
        paragraphs: list[str] = []

        intro = f'本节围绕“{node.goal}”展开，重点回答 {node.title} 在当前任务中的关键问题。'
        if previous_section_summary:
            intro += f' 为避免与前文重复，本节承接上一节结论：{_shorten(previous_section_summary, 80)}。'
        paragraphs.append(intro)

        if evidence_cards:
            for card in evidence_cards[:4]:
                snippet = _shorten(card.snippet, 180)
                if not snippet:
                    continue
                claim = (
                    f'基于证据“{card.title}”，可以得到如下信息：{snippet}'
                )
                claim += _source_suffix(card)
                paragraphs.append(claim)

            paragraphs.append(
                '综合以上证据，可以先形成稳健判断；若需更强结论，需要在关键指标和对照样本上继续补充证据。'
            )
        else:
            warnings.append(f'章节 {node.node_id} 证据不足。')
            paragraphs.append(
                '目前证据不足以支持更强结论，建议后续补充更具体的数据来源、案例对比或实验结果。'
            )

        if task.citation_required and evidence_cards and not any(card.ref for card in evidence_cards):
            warnings.append(f'章节 {node.node_id} 没有可用引用标记。')

        text = '\n\n'.join(paragraphs).strip()
        if _word_units(text) < max(80, int(node.expected_words * 0.6)):
            text += '\n\n从工程落地角度看，建议优先验证可行性最高的子路径，并对关键假设设立监控指标，以便快速迭代。'

        return SectionWriteResult(
            section_markdown=text.strip(),
            section_summary=_summary_from_text(text),
            used_citations=_used_citations(text, evidence_cards),
            warnings=warnings,
        )

    def write(
        self,
        *,
        task: LongFormTaskSchema,
        node: OutlineNode,
        evidence_cards: list[EvidenceCard],
        previous_section_summary: str,
        global_terms: Mapping[str, str],
        repair_instructions: Optional[list[str]] = None,
    ) -> SectionWriteResult:
        prompt = _fill_prompt(
            SECTION_WRITER_PROMPT,
            task_json=json.dumps(task.to_dict(), ensure_ascii=False, indent=2),
            node_json=json.dumps(node.to_dict(), ensure_ascii=False, indent=2),
            evidence_json=json.dumps([card.to_dict() for card in evidence_cards], ensure_ascii=False, indent=2),
            previous_summary=previous_section_summary or '',
            global_terms_json=json.dumps(dict(global_terms or {}), ensure_ascii=False),
        )
        if repair_instructions:
            prompt += '\n\n修复要求：\n' + '\n'.join(f'- {item}' for item in repair_instructions if item)

        llm_output = self._call_llm(prompt)
        if llm_output:
            text = str(llm_output).strip()
            # If LLM accidentally outputs fenced code block, keep body only.
            if text.startswith('```') and text.endswith('```'):
                lines = text.splitlines()
                if len(lines) >= 3:
                    text = '\n'.join(lines[1:-1]).strip()
            if text:
                warnings: list[str] = []
                if not evidence_cards:
                    warnings.append(f'章节 {node.node_id} 使用了无证据写作回退。')
                return SectionWriteResult(
                    section_markdown=text,
                    section_summary=_summary_from_text(text),
                    used_citations=_used_citations(text, evidence_cards),
                    warnings=warnings,
                )

        return self._rule_write(
            task=task,
            node=node,
            evidence_cards=evidence_cards,
            previous_section_summary=previous_section_summary,
        )
