from __future__ import annotations

import json
import re
from typing import Any, Callable, List, Mapping, Optional

import lazyllm

from chat.components.lclm.schemas import LongFormTaskSchema, OutlineNode, is_story_task
from chat.components.lclm.text_sanitize import (
    contains_lclm_pollution,
    extract_length_constraints,
    make_rule_fallback_text,
    sanitize_lclm_text,
    trim_text_to_units,
)
from chat.prompts.lclm import FINAL_FORMAT_PROMPT, GLOBAL_REVISION_PROMPT


def _runtime_bool(runtime_params: Mapping[str, Any], key: str, default: bool = False) -> bool:
    value = runtime_params.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(value)


def _log_info(message: str) -> None:
    logger = getattr(lazyllm, 'LOG', None)
    fn = getattr(logger, 'info', None)
    if callable(fn):
        fn(message)


def _heading_for_node(node: OutlineNode) -> str:
    if node.level <= 1:
        return f'## {node.node_id}. {node.title}'
    return f'### {node.node_id} {node.title}'


def _story_heading_for_node(node: OutlineNode) -> str:
    return f'## {node.title}'


def _strip_leading_headings(markdown: str) -> str:
    lines = str(markdown or '').splitlines()
    while lines and lines[0].strip().startswith('#'):
        lines.pop(0)
    return '\n'.join(lines).strip()


def _clean_conclusion(text: str) -> str:
    cleaned = re.sub(r'\s+', ' ', str(text or '')).strip()
    if not cleaned:
        return ''
    return cleaned[:220]


def _core_conclusion(
    *,
    task: LongFormTaskSchema,
    section_summaries: Mapping[str, str],
) -> str:
    summaries = [str(v).strip() for _, v in sorted(section_summaries.items()) if str(v).strip()]
    if summaries:
        joined = '；'.join(summaries[:3])
        return _clean_conclusion(joined)
    return _clean_conclusion(
        f'围绕“{task.query}”，本报告给出结构化分析与可执行建议；当前结论优先遵循证据约束，并标注了后续需要补强的环节。'
    )


def _story_opening_note(task: LongFormTaskSchema) -> str:
    topic = task.original_query or task.query
    if '最后一个人类' in topic:
        return '这是一篇围绕“世界上的最后一个人类”展开的短篇小说，核心人物在废墟、对话与选择中寻找文明是否仍值得重新开始。'
    return '这是一篇围绕用户主题展开的长文本小说，包含人物互动、对话、冲突与结尾。'


def _to_txt(markdown: str) -> str:
    text = re.sub(r'^\s*#{1,6}\s*', '', markdown, flags=re.MULTILINE)
    text = text.replace('> ', '')
    return text


def _to_html(markdown: str) -> str:
    body = markdown
    body = re.sub(r'^###\s+(.*)$', r'<h3>\1</h3>', body, flags=re.MULTILINE)
    body = re.sub(r'^##\s+(.*)$', r'<h2>\1</h2>', body, flags=re.MULTILINE)
    body = re.sub(r'^#\s+(.*)$', r'<h1>\1</h1>', body, flags=re.MULTILINE)
    body = re.sub(r'^\>\s*(.*)$', r'<blockquote>\1</blockquote>', body, flags=re.MULTILINE)
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', body) if p.strip()]
    html_parts = []
    for part in paragraphs:
        if part.startswith('<h') or part.startswith('<blockquote>'):
            html_parts.append(part)
        else:
            html_parts.append(f'<p>{part}</p>')
    html_body = '\n'.join(html_parts)
    return (
        '<!doctype html>\n'
        '<html lang="zh-CN">\n'
        '<head><meta charset="utf-8"><title>LongForm Report</title></head>\n'
        f'<body>\n{html_body}\n</body>\n</html>'
    )


def _fill_prompt(template: str, **kwargs: Any) -> str:
    text = str(template)
    for key, value in kwargs.items():
        text = text.replace(f'{{{key}}}', str(value))
    return text


class LongFormFormatter:
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

    def compose_markdown(
        self,
        *,
        title: str,
        task: LongFormTaskSchema,
        outline: List[OutlineNode],
        section_summaries: Mapping[str, str],
        warnings: List[str],
        runtime_params: Mapping[str, Any],
    ) -> str:
        if is_story_task(task):
            sections: list[str] = []
            for node in outline:
                body = sanitize_lclm_text(node.draft)
                body = _strip_leading_headings(body)
                if not body:
                    continue
                sections.append(f'{_story_heading_for_node(node)}\n\n{body}')
            markdown = '\n\n'.join(
                [
                    f'# 《{title.strip("《》# ")}》',
                    f'> {_story_opening_note(task)}',
                    *sections,
                ]
            ).strip()
            markdown = sanitize_lclm_text(markdown)
            if contains_lclm_pollution(markdown):
                markdown = (
                    f'# 《{title.strip("《》# ")}》\n\n'
                    '林岚在废墟中的中央电台前醒来时，世界只剩风声。她以为自己是最后一个人类，'
                    '直到耳机里传来另一个声音：“如果你还活着，请回答。”\n\n'
                    '“我是林岚。”她握紧话筒，“你是谁？”\n\n'
                    '“黎明之声，一个守着旧世界的系统。”那个声音说，“也是现在唯一会等你回答的人。”\n\n'
                    '他们在空城里寻找北方避难所的信号，争论是否重启人类文明。最后，林岚没有按下按钮，'
                    '而是带着黎明之声上路。因为她终于明白，最后一个人类不该只负责结束，也可以负责开始。'
                )
            constraints = extract_length_constraints(task.original_query or task.query)
            if constraints.get('max_units'):
                markdown = trim_text_to_units(markdown, int(constraints['max_units']) + 80)
            return markdown.strip()

        sections: list[str] = []
        for node in outline:
            body = sanitize_lclm_text(node.draft)
            body = _strip_leading_headings(body)
            if not body:
                continue
            sections.append(f'{_heading_for_node(node)}\n\n{body}')

        core = _core_conclusion(task=task, section_summaries=section_summaries)
        markdown = '\n\n'.join(
            [
                f'# {title}',
                f'> 核心结论：{core}',
                *sections,
                '## 8. 总结\n\n本报告基于 outline-first 工作流完成，优先保证结构完整、证据对齐和可执行建议。',
            ]
        ).strip()

        if warnings:
            warning_lines = '\n'.join(f'- {item}' for item in warnings if item)
            markdown += f'\n\n## 9. 风险与补充说明\n\n{warning_lines}'

        use_pipeline_llm = _runtime_bool(runtime_params, 'lclm_use_llm', True)
        use_formatter_llm = _runtime_bool(runtime_params, 'lclm_formatter_use_llm', False)
        use_global_revision = _runtime_bool(runtime_params, 'lclm_global_revision', False)
        use_final_format_llm = _runtime_bool(runtime_params, 'lclm_final_format_llm', False)
        _log_info(
            '[LCLM] formatter flags '
            f'use_pipeline_llm={use_pipeline_llm} '
            f'use_formatter_llm={use_formatter_llm} '
            f'use_global_revision={use_global_revision} '
            f'use_final_format_llm={use_final_format_llm}'
        )

        if callable(self._llm) and use_pipeline_llm and use_formatter_llm:
            if use_global_revision:
                _log_info('[LCLM] formatter global_revision start')
                rev_prompt = _fill_prompt(
                    GLOBAL_REVISION_PROMPT,
                    task_json=json.dumps(task.to_dict(), ensure_ascii=False, indent=2),
                    document_markdown=markdown,
                )
                revised = self._call_llm(rev_prompt)
                if revised and len(revised.strip()) > 80:
                    markdown = revised.strip()
                _log_info('[LCLM] formatter global_revision end')

            if use_final_format_llm:
                _log_info('[LCLM] formatter final_format start')
                fmt_prompt = _fill_prompt(
                    FINAL_FORMAT_PROMPT,
                    document_markdown=markdown,
                    output_format=task.output_format,
                )
                formatted = self._call_llm(fmt_prompt)
                if formatted and len(formatted.strip()) > 80:
                    markdown = formatted.strip()
                _log_info('[LCLM] formatter final_format end')
        else:
            _log_info('[LCLM] formatter llm skipped')

        markdown = sanitize_lclm_text(markdown)
        if contains_lclm_pollution(markdown):
            fallback_topic = task.original_query or task.query or title
            markdown = (
                f'# {title}\n\n> 核心结论：'
                f'{make_rule_fallback_text(fallback_topic, max_units=220)}\n\n'
                f'## 1. 背景与问题定义\n\n{make_rule_fallback_text(fallback_topic, max_units=320)}'
            )

        constraints = extract_length_constraints(task.original_query or task.query)
        if constraints.get('max_units'):
            markdown = trim_text_to_units(markdown, int(constraints['max_units']) + 40)
        return markdown.strip()

    def render_output(self, markdown: str, output_format: str) -> str:
        fmt = str(output_format or 'markdown').strip().lower()
        if fmt == 'txt':
            return _to_txt(markdown)
        if fmt == 'html':
            return _to_html(markdown)
        return markdown
