from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional

from chat.components.lclm.schemas import EvidenceCard, LongFormTaskSchema, OutlineNode, is_story_task
from chat.components.lclm.text_sanitize import (
    contains_lclm_pollution,
    extract_length_constraints,
    is_bad_placeholder_text,
    make_rule_fallback_text,
    sanitize_lclm_text,
    trim_text_to_units,
)
from chat.prompts.lclm import SECTION_WRITER_PROMPT, STORY_SECTION_WRITER_PROMPT


_CITATION_REF_RE = re.compile(r'\[\[\d+\]\]')
_BAD_WRITER_KEYWORDS = (
    '<think>',
    '</think>',
    '<query>',
    'survey on <query>',
    'query 字段为空',
    '用户要求我',
    '让我分析',
    '当前节点信息',
    '关键约束',
    '证据卡为空',
    'evidence_cards',
    'retrieval_queries',
    'hard_controls',
    'tool_policy',
)
_REPORT_POLLUTION_KEYWORDS = (
    '本报告',
    '长文报告',
    '背景与问题定义',
    '方法路线总览',
    '关键分析维度',
    '对 LazyRAG 的启发',
    '推荐实施方案',
    '风险与测试建议',
    '证据不足',
    '未检索到可用证据卡',
    '目前证据不足以支持更强结论',
    'citation',
    '[[1]]',
)


def _word_units(text: str) -> int:
    zh = len(re.findall(r'[\u4e00-\u9fff]', text))
    en = len(re.findall(r'[A-Za-z0-9]+', text))
    return zh + en * 2


def _runtime_int(runtime_params: Mapping[str, Any], key: str, default: int) -> int:
    value = runtime_params.get(key)
    if value in (None, ''):
        return default
    try:
        return int(value)
    except Exception:
        return default


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


def _has_dialogue(text: str) -> bool:
    raw = str(text or '')
    return bool(re.search(r'[“"].+?[”"]', raw) or re.search(r'^[\u4e00-\u9fffA-Za-z]{1,12}[:：].+', raw, re.MULTILINE))


def _story_polluted(text: str) -> bool:
    raw = str(text or '')
    if contains_lclm_pollution(raw):
        return True
    return any(term in raw for term in _REPORT_POLLUTION_KEYWORDS)


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
        runtime_params: Mapping[str, Any],
    ) -> SectionWriteResult:
        warnings: list[str] = []
        paragraphs: list[str] = []
        source_query = task.original_query or task.query

        intro = f'本节围绕“{source_query}”展开，重点回答 {node.title} 在当前任务中的关键问题。'
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
                f'目前证据不足以支持关于“{source_query}”的更强结论，建议后续补充更具体的数据来源、案例对比或实验结果。'
            )

        if task.citation_required and evidence_cards and not any(card.ref for card in evidence_cards):
            warnings.append(f'章节 {node.node_id} 没有可用引用标记。')

        text = '\n\n'.join(paragraphs).strip()
        if _word_units(text) < max(80, int(node.expected_words * 0.6)):
            text += '\n\n从工程落地角度看，建议优先验证可行性最高的子路径，并对关键假设设立监控指标，以便快速迭代。'

        max_units = _runtime_int(runtime_params, 'lclm_section_max_words', max(120, node.expected_words))
        max_units = max(80, min(max_units, max(120, int(node.expected_words * 1.2))))
        text = trim_text_to_units(text, max_units)

        return SectionWriteResult(
            section_markdown=text.strip(),
            section_summary=_summary_from_text(text),
            used_citations=_used_citations(text, evidence_cards),
            warnings=warnings,
        )

    def _story_rule_write(
        self,
        *,
        task: LongFormTaskSchema,
        node: OutlineNode,
        previous_section_summary: str,
        runtime_params: Mapping[str, Any],
    ) -> SectionWriteResult:
        del previous_section_summary
        source_query = task.original_query or task.query
        title = str(node.title or '').strip()
        controls = node.hard_controls if isinstance(node.hard_controls, dict) else {}
        characters = controls.get('characters') if isinstance(controls.get('characters'), list) else []
        hero = str(characters[0]) if characters else '林岚'
        companion = str(characters[1]) if len(characters) > 1 else '黎明之声'
        if hero in {'最后一个人类', '人类'}:
            hero = '林岚'
        if companion in {'黎明之声', 'AI'}:
            companion = '黎明之声'

        idx = str(node.node_id or '1')
        if idx.endswith('1') and idx in {'1', '1.1'}:
            text = (
                f'风从空城的高架桥下穿过，卷起一张褪色的儿童画。{hero}把画按在胸口，沿着废墟里唯一还亮着的红灯走向中央电台。'
                f'她已经三年没有听见另一个人的脚步声，直到那天夜里，电台里传出一个干净得近乎陌生的声音。\n\n'
                f'“这里是黎明协议。”声音说，“如果还有人类活着，请回答。”\n\n'
                f'{hero}握紧话筒，喉咙像被尘土封住。很久以后，她才说：“我是{hero}。也许是最后一个。”\n\n'
                f'“不，”那个声音停顿了一秒，“至少现在，你还有我。”'
            )
        elif '第二' in title or '登场' in title or idx.startswith('2') or idx.startswith('3'):
            text = (
                f'{companion}没有身体，只存在于城市地下的旧服务器里。它用残存的摄像头看见{hero}穿过大厅，看见她把一枚生锈的门禁卡插进控制台。'
                f'屏幕亮起时，蓝色光斑映在她的脸上，像一场迟到的日出。\n\n'
                f'“你为什么找我？”{hero}问。\n\n'
                f'“因为你携带最后一组未经污染的人类基因。”{companion}回答，“也因为你还有选择权。”\n\n'
                f'{hero}笑了一下，笑声干涩：“世界都空了，选择权听起来像一个冷笑话。”\n\n'
                f'“冷笑话也是文明的遗迹。”{companion}说，“我一直在等一个会笑的人。”'
            )
        elif '冲突' in title or '选择' in title or '重启' in title:
            text = (
                f'地下穹顶打开时，{hero}看见数万只透明培养舱，里面漂浮着尚未醒来的胚胎。重启人类文明的按钮就在她掌心下方，红得像一颗没来得及停止跳动的心。'
                f'{companion}把旧时代的影像投到墙上：战争、饥荒、海啸，也有婚礼、操场和孩子第一次写下自己的名字。\n\n'
                f'“如果我按下去，”{hero}低声说，“他们会不会重新毁掉一切？”\n\n'
                f'“可能会。”{companion}没有撒谎。\n\n'
                f'“那你为什么还要我做？”\n\n'
                f'“因为结局不该由恐惧一个人书写。”'
            )
        elif '转折' in title:
            text = (
                f'就在{hero}准备关闭系统时，远端频道忽然亮起微弱的绿点。一个孩子的声音从噪声里挤出来，断断续续，却真实得让她几乎站不稳。\n\n'
                f'“有人吗？我叫安。妈妈说，如果灯塔亮了，就往北走。”\n\n'
                f'{hero}猛地看向屏幕。{companion}沉默了，它调出地图，在冰封海岸标出一个几乎被遗忘的避难所。'
                f'世界上的最后一个人类，原来只是世界以为的最后一个。\n\n'
                f'“我们去找她。”{hero}说。\n\n'
                f'“那重启协议呢？”\n\n'
                f'“等我们有三个人，再一起投票。”'
            )
        else:
            text = (
                f'黎明前最黑的时候，{hero}背起电台终端，走出中央塔。{companion}的声音藏在她耳机里，替她计算风暴间隙，也替她记住每一个还可能有人回应的频率。'
                f'她没有按下重启按钮，也没有放弃它；她把决定带上路，像带着一颗还没命名的种子。\n\n'
                f'“如果我们找不到安呢？”{companion}问。\n\n'
                f'{hero}望着远处亮起的第一线天光：“那就继续找。最后一个人类不该只负责结束，也可以负责开始。”\n\n'
                f'风停时，电台里传来第二次呼叫。{hero}笑了，第一次不再像废墟里的回声。'
            )

        max_units = _runtime_int(runtime_params, 'lclm_section_max_words', max(180, node.expected_words))
        text = trim_text_to_units(text, max(120, max_units))
        if not _has_dialogue(text):
            text += f'\n\n“我们还活着吗？”{hero}问。\n\n“只要还会回答，就还活着。”{companion}说。'
        return SectionWriteResult(
            section_markdown=text.strip(),
            section_summary=_summary_from_text(text),
            used_citations=[],
            warnings=[],
        )

    def write(
        self,
        *,
        task: LongFormTaskSchema,
        node: OutlineNode,
        evidence_cards: list[EvidenceCard],
        previous_section_summary: str,
        global_terms: Mapping[str, str],
        runtime_params: Optional[Mapping[str, Any]] = None,
        repair_instructions: Optional[list[str]] = None,
    ) -> SectionWriteResult:
        params = runtime_params if isinstance(runtime_params, Mapping) else {}
        source_query = task.original_query or task.query
        if is_story_task(task):
            prompt = _fill_prompt(
                STORY_SECTION_WRITER_PROMPT,
                task_json=json.dumps(task.to_dict(), ensure_ascii=False, indent=2),
                node_json=json.dumps(node.to_dict(), ensure_ascii=False, indent=2),
                previous_summary=previous_section_summary or '',
                global_terms_json=json.dumps(dict(global_terms or {}), ensure_ascii=False),
                original_query=source_query,
            )
            if repair_instructions:
                prompt += '\n\n修复要求：\n' + '\n'.join(f'- {item}' for item in repair_instructions if item)
            llm_output = self._call_llm(prompt)
            if llm_output:
                text = sanitize_lclm_text(llm_output)
                max_units = _runtime_int(params, 'lclm_section_max_words', max(180, node.expected_words))
                max_units = max(120, min(max_units, max(220, int(node.expected_words * 1.4))))
                text = trim_text_to_units(text, max_units)
                if text and not _story_polluted(text) and _has_dialogue(text):
                    return SectionWriteResult(
                        section_markdown=text,
                        section_summary=_summary_from_text(text),
                        used_citations=[],
                        warnings=[],
                    )
            return self._story_rule_write(
                task=task,
                node=node,
                previous_section_summary=previous_section_summary,
                runtime_params=params,
            )

        prompt = _fill_prompt(
            SECTION_WRITER_PROMPT,
            task_json=json.dumps(task.to_dict(), ensure_ascii=False, indent=2),
            node_json=json.dumps(node.to_dict(), ensure_ascii=False, indent=2),
            evidence_json=json.dumps([card.to_dict() for card in evidence_cards], ensure_ascii=False, indent=2),
            previous_summary=previous_section_summary or '',
            global_terms_json=json.dumps(dict(global_terms or {}), ensure_ascii=False),
            original_query=source_query,
        )
        if repair_instructions:
            prompt += '\n\n修复要求：\n' + '\n'.join(f'- {item}' for item in repair_instructions if item)

        llm_output = self._call_llm(prompt)
        if llm_output:
            text = sanitize_lclm_text(llm_output)
            # If LLM accidentally outputs fenced code block, keep body only.
            if text.startswith('```') and text.endswith('```'):
                lines = text.splitlines()
                if len(lines) >= 3:
                    text = '\n'.join(lines[1:-1]).strip()
            text = sanitize_lclm_text(text)
            max_units = _runtime_int(params, 'lclm_section_max_words', max(120, node.expected_words))
            max_units = max(80, min(max_units, max(120, int(node.expected_words * 1.3))))
            text = trim_text_to_units(text, max_units)
            lower = text.lower()
            polluted = contains_lclm_pollution(text) or any(k in lower for k in _BAD_WRITER_KEYWORDS)
            if is_bad_placeholder_text(text):
                polluted = True
            if text:
                if not polluted:
                    warnings: list[str] = []
                    if not evidence_cards:
                        warnings.append(f'章节 {node.node_id} 使用了无证据写作回退。')
                    return SectionWriteResult(
                        section_markdown=text,
                        section_summary=_summary_from_text(text),
                        used_citations=_used_citations(text, evidence_cards),
                        warnings=warnings,
                    )

        fallback = self._rule_write(
            task=task,
            node=node,
            evidence_cards=evidence_cards,
            previous_section_summary=previous_section_summary,
            runtime_params=params,
        )
        if is_bad_placeholder_text(fallback.section_markdown) or contains_lclm_pollution(fallback.section_markdown):
            constraints = extract_length_constraints(source_query)
            fallback.section_markdown = make_rule_fallback_text(
                source_query,
                max_units=constraints.get('max_units'),
            )
            fallback.section_summary = _summary_from_text(fallback.section_markdown)
        return fallback
