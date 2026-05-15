from __future__ import annotations

import json
import re
from typing import Any, Callable, List, Mapping, Optional

from chat.components.lclm.schemas import (
    LongFormTaskSchema,
    OutlineNode,
    coerce_outline_nodes,
    coerce_task_schema,
    is_story_task,
    parse_json_text,
)
from chat.components.lclm.text_sanitize import (
    is_bad_placeholder_text,
    sanitize_lclm_text,
    sanitize_title,
)
from chat.prompts.lclm import OUTLINE_PLANNER_PROMPT, TASK_SCHEMA_PROMPT

_STORY_KEYWORDS = (
    '小说',
    '故事',
    '短篇小说',
    '长篇小说',
    '长文本小说',
    '主人公',
    '对话',
    '剧情',
    '情节',
    '角色',
    '结局',
    '叙事',
    'fiction',
    'story',
    'short story',
    'novel',
)
_REPORT_TITLE_TERMS = (
    '背景与问题定义',
    '方法路线总览',
    '关键分析维度',
    '对 LazyRAG 的启发',
    '推荐实施方案',
    '风险与测试建议',
    '长文报告',
    '报告',
    '证据',
    '引用',
)


def _runtime_int(runtime_params: Mapping[str, Any], key: str, default: int) -> int:
    value = runtime_params.get(key)
    if value in (None, ''):
        return default
    try:
        return int(value)
    except Exception:
        return default


def _clamp(value: int, low: int, high: int) -> int:
    return min(max(value, low), high)


def _fill_prompt(template: str, **kwargs: Any) -> str:
    text = str(template)
    for key, value in kwargs.items():
        text = text.replace(f'{{{key}}}', str(value))
    return text


def _guess_language(query: str) -> str:
    text = str(query or '')
    if not text:
        return 'zh'
    zh_count = len(re.findall(r'[\u4e00-\u9fff]', text))
    en_count = len(re.findall(r'[A-Za-z]', text))
    return 'zh' if zh_count >= en_count else 'en'


def _guess_genre(query: str) -> str:
    text = str(query or '').lower()
    if _is_story_query(text):
        return 'story'
    if any(k in text for k in ('survey', '综述', '研究现状', 'literature review')):
        return 'survey'
    if any(k in text for k in ('paper summary', '论文总结', '论文解读')):
        return 'paper_summary'
    if any(k in text for k in ('方案', 'proposal', 'technical plan', '技术路线', '实施路线')):
        return 'technical_plan'
    if any(k in text for k in ('report', '报告', '调研')):
        return 'report'
    return 'generic_longform'


def _is_story_query(query: str) -> bool:
    text = str(query or '').lower()
    return any(k in text for k in _STORY_KEYWORDS)


def _guess_audience(query: str) -> str:
    text = str(query or '').lower()
    if any(k in text for k in ('工程', 'engineer', '架构', '系统设计')):
        return 'engineer'
    if any(k in text for k in ('研究', 'research', '论文', 'arxiv')):
        return 'researcher'
    if any(k in text for k in ('商业', 'business', '管理层', '老板')):
        return 'business'
    return 'general'


def _guess_target_length(query: str) -> str:
    text = str(query or '').lower()
    if any(k in text for k in ('超长', 'very long', '白皮书', '完整报告')):
        return 'very_long'
    if any(k in text for k in ('简短', '一句话', 'short answer')):
        return 'short'
    if any(k in text for k in ('中等', 'medium')):
        return 'medium'
    return 'long'


def _guess_output_format(query: str) -> str:
    text = str(query or '').lower()
    if 'html' in text:
        return 'html'
    if any(k in text for k in ('txt', 'text', '纯文本')):
        return 'txt'
    return 'markdown'


def _guess_source_policy(query: str, runtime_params: Mapping[str, Any]) -> str:
    text = str(query or '').lower()
    if _is_story_query(text):
        return 'no_external'
    if any(k in text for k in ('arxiv', 'paper', '论文', '文献')):
        return 'arxiv_preferred'
    if runtime_params.get('kb_id') or runtime_params.get('temp_files'):
        return 'kb_first'
    if any(k in text for k in ('最新', 'current', 'recent', 'news', '公开资料')):
        return 'web_allowed'
    return 'kb_first'


def _story_title_from_query(query: str) -> str:
    text = str(query or '').strip()
    quoted = re.findall(r'[“"「《](.*?)[”"」》]', text)
    topic = quoted[0].strip() if quoted else text
    if '最后一个人类' in topic or '最后的人类' in topic:
        return '最后的人类与黎明之声'
    topic = re.sub(r'^(请|帮我|请以|以)', '', topic).strip(' ，。,.')
    topic = re.sub(r'(为主题|写一篇|生成|长文本|短篇小说|小说|故事).*$', '', topic).strip(' ，。,.')
    return topic or '最后的人类与黎明之声'


def _enforce_story_task(task: LongFormTaskSchema) -> LongFormTaskSchema:
    task.genre = 'story'
    task.writing_type = 'fiction'
    task.output_type = 'short_story'
    task.citation_required = False
    task.evidence_required = False
    task.source_policy = 'no_external'
    task.tone = 'literary'
    return task


def _fallback_task_schema(query: str, runtime_params: Mapping[str, Any]) -> LongFormTaskSchema:
    mode = str(runtime_params.get('lclm_mode') or 'auto').strip().lower() or 'auto'
    original_query = str(runtime_params.get('original_query') or query or '').strip()
    task = LongFormTaskSchema(
        query=original_query or str(query or '').strip(),
        original_query=original_query or str(query or '').strip(),
        language=_guess_language(query),
        genre=_guess_genre(query),
        audience=_guess_audience(query),
        target_length=_guess_target_length(query),
        citation_required=True,
        source_policy=_guess_source_policy(query, runtime_params),
        output_format=_guess_output_format(query),
        tone='technical',
        lclm_mode=mode,
    )
    if _is_story_query(original_query or query):
        task = _enforce_story_task(task)
    return task


def _rule_outline_template(task: LongFormTaskSchema) -> list[tuple[int, str, str]]:
    if is_story_task(task):
        return [
            (1, '开场：废墟中的最后电台', '在荒废世界中建立孤独、废墟与未知信号的开端。'),
            (1, '第一位主人公登场：最后一个人类', '让最后的人类带着具体欲望、恐惧和行动进入故事。'),
            (1, '第二位主人公登场：黎明之声', '引入 AI、休眠者或克隆体式的第二主人公，并让两者发生互动。'),
            (1, '冲突：是否重启人类文明', '围绕选择、代价和信任制造核心冲突。'),
            (1, '对话与选择', '通过真实对话推进人物关系和价值抉择。'),
            (1, '转折：最后的人类并不孤独', '制造认知反转，让故事进入新的道德困境。'),
            (1, '结局：黎明之前', '完成结尾，回应世界上最后一个人类的主题。'),
        ]
    if task.genre in ('survey', 'paper_summary'):
        return [
            (1, '背景与问题定义', '界定研究问题、范围与评价标准。'),
            (1, '方法路线总览', '概括主流方法的共性框架和比较维度。'),
            (2, '关键技术路线一', '说明核心机制、适用场景、优势与局限。'),
            (2, '关键技术路线二', '说明差异化机制和工程实践挑战。'),
            (1, '证据与案例分析', '结合检索证据给出对比与趋势判断。'),
            (1, '对 LazyRAG 的启发', '映射到 RAG / Skill / Tool / Workflow 改造点。'),
            (1, '实施建议与风险控制', '给出分阶段实施路径、风险和测试建议。'),
            (1, '总结', '给出可执行结论与后续行动。'),
        ]
    if task.genre in ('technical_plan', 'proposal'):
        return [
            (1, '目标与约束', '明确业务目标、边界条件和验收标准。'),
            (1, '方案架构总览', '描述系统分层、关键模块和交互关系。'),
            (2, '关键技术路线', '解释核心算法与工程取舍。'),
            (2, '数据与证据策略', '定义 RAG 检索、引用和质量控制策略。'),
            (1, '实施计划', '按阶段给出任务拆解与里程碑。'),
            (1, '风险与回滚', '识别主要风险并给出缓解与回滚方案。'),
            (1, '测试与验收', '定义测试面、指标和验收门槛。'),
            (1, '总结', '沉淀最终建议与执行优先级。'),
        ]
    return [
        (1, '背景与问题定义', '明确任务上下文、范围和关键问题。'),
        (1, '方法路线总览', '给出整体分析框架与章节结构。'),
        (2, '关键分析维度一', '展开核心机制与证据支持。'),
        (2, '关键分析维度二', '展开对比、边界与局限。'),
        (1, '对 LazyRAG 的启发', '映射到系统、工具和流程设计。'),
        (1, '推荐实施方案', '给出执行顺序、资源建议和阶段目标。'),
        (1, '风险与测试建议', '列出风险点与验证方案。'),
        (1, '总结', '给出结论与下一步行动。'),
    ]


def _fallback_outline(
    task: LongFormTaskSchema,
    *,
    max_nodes: int,
    max_depth: int,
    section_words: int,
) -> tuple[str, List[OutlineNode]]:
    nodes: list[OutlineNode] = []
    if is_story_task(task):
        outline_title = _story_title_from_query(task.original_query or task.query)
    else:
        outline_title = sanitize_title(
            f'{task.original_query or task.query} - 长文报告',
            task.original_query or task.query,
            fallback='长文报告',
        )
    template = _rule_outline_template(task)[:max_nodes]
    parent_by_level: dict[int, str] = {}
    for idx, (level, title, goal) in enumerate(template, start=1):
        normalized_level = _clamp(level, 1, max_depth)
        node_id = str(idx) if normalized_level == 1 else f'{idx - 1}.{1}'
        parent_id = None
        if normalized_level > 1:
            parent_id = parent_by_level.get(normalized_level - 1) or str(max(idx - 1, 1))
        parent_by_level[normalized_level] = str(idx)
        expected_words = section_words
        if '总结' in title:
            expected_words = max(120, int(section_words * 0.8))
        nodes.append(
            OutlineNode(
                node_id=node_id,
                title=title,
                level=normalized_level,
                parent_id=parent_id,
                goal=goal,
                expected_words=expected_words,
                evidence_needs=[] if is_story_task(task) else [
                    f'{title} 的关键事实依据',
                    f'{title} 的典型案例或对比信息',
                ],
                retrieval_queries=[] if is_story_task(task) else [
                    f'{task.original_query or task.query} {title} 关键要点',
                    f'{title} 风险 限制 实践',
                ],
                hard_controls=(
                    {
                        'scene_id': node_id,
                        'scene_title': title,
                        'narrative_goal': goal,
                        'characters': ['最后一个人类', '黎明之声'],
                        'dialogue_requirement': '至少包含一次真实对话',
                        'plot_function': title,
                        'citation_required': False,
                    }
                    if is_story_task(task)
                    else {
                        'no_hallucination': True,
                        'citation_required': bool(task.citation_required),
                    }
                ),
                soft_controls=(
                    {
                        'style': 'literary',
                        'setting': '末日后的废墟世界',
                        'conflict': '是否重启人类文明，以及重启的代价',
                    }
                    if is_story_task(task)
                    else {
                        'style': task.tone,
                        'audience': task.audience,
                        'avoid_redundancy': True,
                    }
                ),
                tool_policy=(
                    {'evidence_required': False, 'external_search': False}
                    if is_story_task(task)
                    else {
                        'kb_first': task.source_policy in {'kb_first', 'arxiv_preferred'},
                        'web_allowed': task.source_policy in {'web_allowed', 'arxiv_preferred'},
                        'arxiv_preferred': task.source_policy == 'arxiv_preferred',
                    }
                ),
            )
        )
    return outline_title, nodes


class LCLMPlanner:
    def __init__(self, llm_callable: Optional[Callable[[str], Any]] = None):
        self._llm = llm_callable

    def _call_llm(self, prompt: str) -> Optional[str]:
        if not callable(self._llm):
            return None
        try:
            out = self._llm(prompt)
        except Exception:
            return None
        if isinstance(out, dict):
            text = out.get('text') or out.get('content') or out.get('message')
            if isinstance(text, str):
                return text
            return json.dumps(out, ensure_ascii=False)
        if out is None:
            return None
        return str(out)

    @staticmethod
    def _is_invalid_schema_output(task: LongFormTaskSchema, original_query: str) -> bool:
        if is_bad_placeholder_text(task.query):
            return True
        if '<query>' in task.query.lower():
            return True
        oq = str(original_query or '').strip()
        return bool(oq) and len(task.query.strip()) <= 2

    def build_task_schema(
        self,
        query: str,
        runtime_params: Mapping[str, Any],
    ) -> LongFormTaskSchema:
        original_query = str(runtime_params.get('original_query') or query or '').strip()
        fallback = _fallback_task_schema(original_query or query, runtime_params)
        prompt = _fill_prompt(TASK_SCHEMA_PROMPT, query=query)
        llm_output = self._call_llm(prompt)
        if not llm_output:
            return fallback
        parsed = coerce_task_schema(
            sanitize_lclm_text(llm_output),
            query=original_query or query,
            default_mode=fallback.lclm_mode,
        )
        parsed.original_query = original_query or parsed.original_query or parsed.query
        if self._is_invalid_schema_output(parsed, original_query):
            return fallback
        if _is_story_query(original_query or query) or is_story_task(parsed):
            parsed = _enforce_story_task(parsed)
        # Keep fallback defaults when LLM misses key fields.
        if parsed.genre == 'generic_longform' and fallback.genre != 'generic_longform':
            parsed.genre = fallback.genre
        if parsed.source_policy == 'kb_first' and fallback.source_policy != 'kb_first':
            parsed.source_policy = fallback.source_policy
        if parsed.output_format == 'markdown' and fallback.output_format != 'markdown':
            parsed.output_format = fallback.output_format
        parsed.query = sanitize_title(parsed.query, original_query or parsed.query, fallback='长文本任务')
        parsed.original_query = original_query or parsed.original_query or parsed.query
        return parsed

    @staticmethod
    def _is_report_outline_for_story(title: str, nodes: List[OutlineNode]) -> bool:
        haystack = ' '.join([title] + [node.title for node in nodes] + [node.goal for node in nodes])
        return any(term in haystack for term in _REPORT_TITLE_TERMS)

    @staticmethod
    def _normalize_story_nodes(task: LongFormTaskSchema, nodes: List[OutlineNode]) -> List[OutlineNode]:
        for idx, node in enumerate(nodes, start=1):
            if any(term in node.title for term in _REPORT_TITLE_TERMS):
                node.title = _rule_outline_template(task)[min(idx - 1, len(_rule_outline_template(task)) - 1)][1]
            node.evidence_needs = []
            node.retrieval_queries = []
            node.tool_policy = {'evidence_required': False, 'external_search': False}
            node.hard_controls = {
                **(node.hard_controls if isinstance(node.hard_controls, dict) else {}),
                'scene_id': node.node_id,
                'scene_title': node.title,
                'narrative_goal': node.goal,
                'characters': ['最后一个人类', '黎明之声'],
                'dialogue_requirement': '至少包含一次真实对话',
                'citation_required': False,
            }
            node.soft_controls = {
                **(node.soft_controls if isinstance(node.soft_controls, dict) else {}),
                'style': 'literary',
                'setting': '末日后的废墟世界',
                'conflict': '是否重启人类文明，以及重启的代价',
            }
        return nodes

    def build_outline(
        self,
        task: LongFormTaskSchema,
        runtime_params: Mapping[str, Any],
    ) -> tuple[str, List[OutlineNode], List[str]]:
        max_nodes = _clamp(_runtime_int(runtime_params, 'lclm_max_outline_nodes', 8), 1, 16)
        max_depth = _clamp(_runtime_int(runtime_params, 'lclm_max_depth', 3), 1, 4)
        min_words = _clamp(_runtime_int(runtime_params, 'lclm_section_min_words', 180), 80, 1200)
        max_words = _clamp(_runtime_int(runtime_params, 'lclm_section_max_words', 900), 120, 2400)
        section_words = _clamp((min_words + max_words) // 2, min_words, max_words)

        warnings: list[str] = []
        fallback_title, fallback_nodes = _fallback_outline(
            task,
            max_nodes=max_nodes,
            max_depth=max_depth,
            section_words=section_words,
        )
        if not callable(self._llm):
            return fallback_title, fallback_nodes, warnings

        prompt = _fill_prompt(
            OUTLINE_PLANNER_PROMPT,
            task_json=json.dumps(task.to_dict(), ensure_ascii=False, indent=2),
            max_nodes=max_nodes,
            max_depth=max_depth,
        )
        primary = self._call_llm(prompt)
        if not primary:
            warnings.append('outline_planner_empty_output_fallback')
            return fallback_title, fallback_nodes, warnings

        parsed = parse_json_text(sanitize_lclm_text(primary), default=None)
        nodes = coerce_outline_nodes(
            parsed if parsed is not None else sanitize_lclm_text(primary),
            max_nodes=max_nodes,
            max_depth=max_depth,
            default_words=section_words,
        )
        if nodes:
            title = ''
            if isinstance(parsed, dict):
                title = str(parsed.get('title') or '').strip()
            title = _story_title_from_query(task.original_query or task.query) if is_story_task(task) else sanitize_title(title or fallback_title, task.original_query or task.query, fallback='长文报告')
            if is_story_task(task) and self._is_report_outline_for_story(title, nodes):
                warnings.append('story_outline_report_shape_fallback')
                return fallback_title, fallback_nodes, warnings
            for idx, node in enumerate(nodes, start=1):
                if is_bad_placeholder_text(node.title):
                    node.title = f'章节 {idx}'
                if is_bad_placeholder_text(node.goal):
                    node.goal = f'围绕 {task.original_query or task.query} 进行分析。'
                node.evidence_needs = [x for x in node.evidence_needs if not is_bad_placeholder_text(x)]
                node.retrieval_queries = [x for x in node.retrieval_queries if not is_bad_placeholder_text(x)]
                if is_story_task(task):
                    node.retrieval_queries = []
                elif not node.retrieval_queries:
                    node.retrieval_queries = [f'{task.original_query or task.query} {node.title}']
            if is_story_task(task):
                nodes = self._normalize_story_nodes(task, nodes)
            return title, nodes, warnings

        # One repair round for broken JSON output.
        repair_prompt = (
            '请修复下面内容为合法 JSON，仅输出 JSON：\n'
            f'{primary}'
        )
        repaired = self._call_llm(repair_prompt)
        repaired_nodes = coerce_outline_nodes(
            sanitize_lclm_text(repaired),
            max_nodes=max_nodes,
            max_depth=max_depth,
            default_words=section_words,
        )
        if repaired_nodes:
            repaired_parsed = parse_json_text(sanitize_lclm_text(repaired), default={})
            repaired_title = ''
            if isinstance(repaired_parsed, dict):
                repaired_title = str(repaired_parsed.get('title') or '').strip()
            warnings.append('outline_planner_repaired_json')
            repaired_title = _story_title_from_query(task.original_query or task.query) if is_story_task(task) else sanitize_title(
                repaired_title or fallback_title,
                task.original_query or task.query,
                fallback='长文报告',
            )
            if is_story_task(task) and self._is_report_outline_for_story(repaired_title, repaired_nodes):
                warnings.append('story_outline_repaired_report_shape_fallback')
                return fallback_title, fallback_nodes, warnings
            for idx, node in enumerate(repaired_nodes, start=1):
                if is_bad_placeholder_text(node.title):
                    node.title = f'章节 {idx}'
                if is_bad_placeholder_text(node.goal):
                    node.goal = f'围绕 {task.original_query or task.query} 进行分析。'
                node.evidence_needs = [x for x in node.evidence_needs if not is_bad_placeholder_text(x)]
                node.retrieval_queries = [x for x in node.retrieval_queries if not is_bad_placeholder_text(x)]
                if is_story_task(task):
                    node.retrieval_queries = []
                elif not node.retrieval_queries:
                    node.retrieval_queries = [f'{task.original_query or task.query} {node.title}']
            if is_story_task(task):
                repaired_nodes = self._normalize_story_nodes(task, repaired_nodes)
            return repaired_title, repaired_nodes, warnings

        warnings.append('outline_planner_parse_failed_rule_fallback')
        return fallback_title, fallback_nodes, warnings

    def plan(
        self,
        query: str,
        runtime_params: Mapping[str, Any],
    ) -> tuple[LongFormTaskSchema, str, List[OutlineNode], List[str]]:
        task = self.build_task_schema(query, runtime_params)
        title, nodes, warnings = self.build_outline(task, runtime_params)
        return task, title, nodes, warnings
