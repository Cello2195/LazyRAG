from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

import lazyllm

from chat.components.lclm.artifact import save_longform_artifact
from chat.components.lclm.critic import SectionCritic, validate_document_markdown
from chat.components.lclm.evidence import EvidenceCollector
from chat.components.lclm.formatter import LongFormFormatter
from chat.components.lclm.planner import LCLMPlanner
from chat.components.lclm.schemas import EvidenceCard, LongFormDocumentState
from chat.components.lclm.writer import SectionWriter

ProgressCallback = Callable[[Dict[str, Any]], None]


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


def _runtime_int(runtime_params: Mapping[str, Any], key: str, default: int) -> int:
    value = runtime_params.get(key)
    if value in (None, ''):
        return default
    try:
        return int(value)
    except Exception:
        return default


def _log_info(message: str) -> None:
    logger = getattr(lazyllm, 'LOG', None)
    fn = getattr(logger, 'info', None)
    if callable(fn):
        fn(message)


def _log_warning(message: str) -> None:
    logger = getattr(lazyllm, 'LOG', None)
    fn = getattr(logger, 'warning', None) or getattr(logger, 'info', None)
    if callable(fn):
        fn(message)


def _build_llm_callable(runtime_params: Mapping[str, Any]) -> Optional[Callable[[str], Any]]:
    candidate = runtime_params.get('lclm_llm_callable') or runtime_params.get('llm_callable')
    if callable(candidate):
        return candidate

    if not _runtime_bool(runtime_params, 'lclm_use_llm', True):
        return None

    try:
        from lazyllm import AutoModel
        from chat.utils.load_config import get_config_path
    except Exception:
        return None

    try:
        model = AutoModel(model='llm', config=get_config_path())
    except Exception:
        return None

    def _invoke(prompt: str) -> Any:
        try:
            return model(prompt)
        except Exception:
            return None

    return _invoke


def _collect_citations(cards: list[EvidenceCard], existing: Dict[str, EvidenceCard]) -> Dict[str, EvidenceCard]:
    merged = dict(existing)
    for card in cards:
        ref = str(card.ref or '').strip()
        if ref:
            merged[ref] = card
    return merged


def _artifact_links(payload: Mapping[str, Any]) -> tuple[str, str]:
    download_link = str(payload.get('download_link') or '').strip()
    download_url = str(payload.get('download_url') or '').strip()
    if not download_link and isinstance(payload.get('artifact'), dict):
        artifact = payload.get('artifact') or {}
        download_link = str(artifact.get('download_link') or '').strip()
        if not download_url:
            download_url = str(artifact.get('download_url') or '').strip()
    return download_link, download_url


class OutlineLongFormPipeline:
    def __init__(
        self,
        runtime_params: Mapping[str, Any],
        progress_callback: Optional[ProgressCallback] = None,
    ):
        self.runtime_params = dict(runtime_params or {})
        self.progress_callback = progress_callback
        self.llm_callable = _build_llm_callable(self.runtime_params)
        self.planner = LCLMPlanner(self.llm_callable)
        self.collector = EvidenceCollector(self.llm_callable)
        self.writer = SectionWriter(self.llm_callable)
        self.critic = SectionCritic(self.llm_callable)
        self.formatter = LongFormFormatter(self.llm_callable)

    def _emit_progress(self, stage: str, text: str, **extra: Any) -> None:
        if not callable(self.progress_callback):
            return
        payload: dict[str, Any] = {
            'stage': str(stage or '').strip() or 'unknown',
            'text': str(text or '').strip(),
        }
        payload.update(extra)
        try:
            self.progress_callback(payload)
        except Exception:
            return

    def _write_sections(self, state: LongFormDocumentState) -> None:
        repair_rounds = max(0, _runtime_int(self.runtime_params, 'lclm_max_repair_rounds', 1))
        previous_summary = ''
        total_nodes = max(1, len(state.outline))

        for index, node in enumerate(state.outline, start=1):
            _log_info(f'[LCLM] evidence start node_id={node.node_id}')
            self._emit_progress(
                'evidence_start',
                f'正在检索第 {index}/{total_nodes} 节证据...',
                node_id=node.node_id,
                index=index,
                total_nodes=total_nodes,
            )
            node.status = 'retrieving'
            cards, evidence_warnings = self.collector.collect(
                task=state.task,
                node=node,
                runtime_params=self.runtime_params,
            )
            _log_info(f'[LCLM] evidence end node_id={node.node_id} card_count={len(cards)}')
            self._emit_progress(
                'evidence_end',
                f'第 {index}/{total_nodes} 节证据检索完成（{len(cards)} 条）。',
                node_id=node.node_id,
                index=index,
                total_nodes=total_nodes,
                card_count=len(cards),
            )
            node.evidence_cards = cards
            state.warnings.extend(evidence_warnings)
            state.citation_map = _collect_citations(cards, state.citation_map)

            _log_info(f'[LCLM] writer start node_id={node.node_id}')
            self._emit_progress(
                'writer_start',
                f'正在撰写第 {index}/{total_nodes} 节...',
                node_id=node.node_id,
                index=index,
                total_nodes=total_nodes,
            )
            node.status = 'drafting'
            draft_result = self.writer.write(
                task=state.task,
                node=node,
                evidence_cards=cards,
                previous_section_summary=previous_summary,
                global_terms=state.global_terms,
            )
            critique = self.critic.evaluate(
                section_text=draft_result.section_markdown,
                task=state.task,
                node=node,
                runtime_params=self.runtime_params,
            )

            repaired_once = False
            if not critique.get('passed') and repair_rounds > 0:
                repaired_once = True
                repaired = self.writer.write(
                    task=state.task,
                    node=node,
                    evidence_cards=cards,
                    previous_section_summary=previous_summary,
                    global_terms=state.global_terms,
                    repair_instructions=critique.get('repair_instructions') or [],
                )
                repaired_critique = self.critic.evaluate(
                    section_text=repaired.section_markdown,
                    task=state.task,
                    node=node,
                    runtime_params=self.runtime_params,
                )
                # Keep the better one by pass status first then fewer issues.
                prev_issue_count = len(critique.get('issues') or [])
                new_issue_count = len(repaired_critique.get('issues') or [])
                if repaired_critique.get('passed') or new_issue_count <= prev_issue_count:
                    draft_result = repaired
                    critique = repaired_critique

            node.draft = draft_result.section_markdown.strip()
            node.critique = critique
            node.status = 'checked' if critique.get('passed') else 'failed'
            _log_info(
                f'[LCLM] writer end node_id={node.node_id} '
                f'passed={bool(critique.get("passed"))} status={node.status}'
            )
            self._emit_progress(
                'writer_end',
                f'第 {index}/{total_nodes} 节撰写完成。',
                node_id=node.node_id,
                index=index,
                total_nodes=total_nodes,
                passed=bool(critique.get('passed')),
                status=node.status,
            )
            state.section_summaries[node.node_id] = draft_result.section_summary
            previous_summary = draft_result.section_summary

            if repaired_once and not critique.get('passed'):
                state.warnings.append(f'章节 {node.node_id} 修复后仍有问题：{"; ".join(critique.get("issues") or [])}')
            if draft_result.warnings:
                state.warnings.extend(draft_result.warnings)

    def _compose_document(self, state: LongFormDocumentState, title: str) -> str:
        markdown = self.formatter.compose_markdown(
            title=title,
            task=state.task,
            outline=state.outline,
            section_summaries=state.section_summaries,
            warnings=state.warnings,
            runtime_params=self.runtime_params,
        )
        doc_check = validate_document_markdown(markdown)
        if not doc_check.get('passed'):
            state.warnings.extend(doc_check.get('issues') or [])
        return markdown

    def _save_artifact(self, state: LongFormDocumentState, *, title: str) -> Dict[str, Any]:
        if not _runtime_bool(self.runtime_params, 'lclm_save_artifact', True):
            return {}

        related = {
            'outline': [
                {
                    'node_id': node.node_id,
                    'title': node.title,
                    'status': node.status,
                    'issue_count': len((node.critique or {}).get('issues') or []),
                }
                for node in state.outline
            ],
            'warnings': state.warnings[:20],
            'citation_count': len(state.citation_map),
        }
        output_content = self.formatter.render_output(state.final_markdown, state.task.output_format)
        return save_longform_artifact(
            content=output_content,
            title=title,
            output_format=state.task.output_format,
            related_artifacts=related,
        )

    def run(
        self,
        *,
        query: str,
        history: Optional[List[dict[str, Any]]] = None,
    ) -> Tuple[Dict[str, Any], LongFormDocumentState]:
        start_ts = time.time()
        _log_info('[LCLM] start')
        self._emit_progress('start', '正在启动长文本生成流程...')
        del history  # Reserved for future memory refinement.
        _log_info('[LCLM] planning start')
        self._emit_progress('planning_start', '正在规划大纲...')
        task, title, outline, planning_warnings = self.planner.plan(query, self.runtime_params)
        _log_info(f'[LCLM] planning end outline_nodes={len(outline)}')
        self._emit_progress(
            'planning_end',
            f'已完成大纲规划，共 {len(outline)} 个章节。',
            outline_nodes=len(outline),
        )
        state = LongFormDocumentState(task=task, outline=outline)
        state.warnings.extend(planning_warnings)
        if planning_warnings:
            _log_warning(f'[LCLM] planning warnings={len(planning_warnings)}')

        self._write_sections(state)
        _log_info('[LCLM] compose start')
        self._emit_progress('compose_start', '正在合成全文...')
        state.final_markdown = self._compose_document(state, title=title)
        _log_info('[LCLM] compose end')
        self._emit_progress('compose_end', '全文合成完成。')
        self._emit_progress('artifact_saving', '正在保存可下载文件...')
        artifact_payload = self._save_artifact(state, title=title)
        state.artifact = dict(artifact_payload or {})

        preview_chars = max(300, _runtime_int(self.runtime_params, 'lclm_preview_chars', 1500))
        preview = state.final_markdown
        if len(preview) > preview_chars:
            preview = preview[:preview_chars].rstrip() + '\n\n...（以下内容请通过下载链接查看完整版本）'

        download_link, download_url = _artifact_links(artifact_payload)
        if download_link or download_url:
            _log_info(
                f'[LCLM] artifact saved download_link={download_link} download_url={download_url}'
            )
            self._emit_progress(
                'artifact_saved',
                '文件已生成，正在返回下载链接...',
                download_link=download_link,
                download_url=download_url,
            )
        else:
            _log_info('[LCLM] artifact saved')
            self._emit_progress('artifact_saved', '文件已生成。')
        final_lines = ['已生成长文本报告。', '', f'标题：{title}', f'字数：约 {len(state.final_markdown)} 字']
        if download_link:
            final_lines.append(f'下载：[点击下载]({download_link})')
        elif download_url:
            final_lines.append(f'下载：[点击下载]({download_url})')
        final_lines.extend(['', '下面是正文预览：', preview])

        response: Dict[str, Any] = {
            'think': (
                'LCLM workflow completed: task schema -> outline -> node evidence -> '
                'section drafting -> critic -> global formatting -> artifact.'
            ),
            'text': '\n'.join(final_lines).strip(),
            'artifact': artifact_payload.get('artifact') if isinstance(artifact_payload, dict) else {},
            'download_link': download_link,
            'download_url': download_url,
            'lclm': {
                'enabled': True,
                'outline_nodes': len(state.outline),
                'warning_count': len(state.warnings),
                'citation_count': len(state.citation_map),
            },
        }
        if state.warnings:
            response['lclm']['warnings'] = state.warnings[:20]
        total_cost = round(time.time() - start_ts, 3)
        _log_info(f'[LCLM] done total_cost={total_cost}')
        self._emit_progress('done', '长文本生成完成。', total_cost=total_cost)
        return response, state


def run_outline_longform(
    *,
    query: str,
    history: Optional[List[dict[str, Any]]],
    runtime_params: Mapping[str, Any],
    progress_callback: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    pipeline = OutlineLongFormPipeline(
        runtime_params=runtime_params,
        progress_callback=progress_callback,
    )
    result, _state = pipeline.run(query=query, history=history)
    return result
