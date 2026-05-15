from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

import lazyllm

from chat.components.lclm.schemas import EvidenceCard, LongFormTaskSchema, OutlineNode, parse_json_text
from chat.prompts.lclm import EVIDENCE_QUERY_PROMPT


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


def _fill_prompt(template: str, **kwargs: Any) -> str:
    text = str(template)
    for key, value in kwargs.items():
        text = text.replace(f'{{{key}}}', str(value))
    return text


def _truncate(text: Any, limit: int = 320) -> str:
    raw = str(text or '').strip()
    if len(raw) <= limit:
        return raw
    return f'{raw[:limit]}...'


def _score_to_confidence(score: Any) -> float:
    try:
        s = float(score)
    except Exception:
        return 0.55
    if s <= 0:
        return 0.45
    if s >= 1:
        return min(0.95, 0.55 + min(s / 10, 0.4))
    return min(0.95, 0.5 + s * 0.4)


def _extract_items(result: Any) -> List[Dict[str, Any]]:
    if isinstance(result, dict):
        if result.get('success') is False:
            return []
        items = result.get('items')
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        if isinstance(items, dict):
            nested = items.get('items')
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
        # Some tool wrappers return {'total':X,'items':[...]} through `result`.
        nested_result = result.get('result')
        if isinstance(nested_result, dict):
            nested_items = nested_result.get('items')
            if isinstance(nested_items, list):
                return [item for item in nested_items if isinstance(item, dict)]
        return []
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    return []


def _kb_source_type(item: Mapping[str, Any]) -> str:
    md = item.get('metadata') if isinstance(item.get('metadata'), dict) else {}
    if md.get('source') == 'uploaded_file':
        return 'uploaded_file'
    return 'kb'


def _kb_card_from_item(item: Mapping[str, Any], *, idx: int, query: str) -> EvidenceCard:
    title = (
        str(item.get('file_name') or '').strip()
        or str(item.get('docid') or '').strip()
        or 'knowledge base'
    )
    snippet = _truncate(item.get('text') or item.get('content') or '')
    ref = str(item.get('ref') or '').strip()
    if ref and not re.fullmatch(r'\[\[\d+\]\]', ref):
        ref = ''
    return EvidenceCard(
        evidence_id=f'kb-{idx}',
        source_type=_kb_source_type(item),
        title=title,
        ref=ref,
        snippet=snippet,
        supported_claims=[],
        confidence=_score_to_confidence(item.get('score')),
        metadata={
            'query': query,
            'docid': item.get('docid') or '',
            'uid': item.get('uid') or '',
        },
    )


def _web_card_from_item(
    item: Mapping[str, Any],
    *,
    idx: int,
    source_type: str,
    query: str,
) -> EvidenceCard:
    title = str(item.get('title') or item.get('url') or source_type).strip() or source_type
    url = str(item.get('url') or '').strip()
    snippet = _truncate(item.get('snippet') or item.get('content') or '')
    ref = ''
    if title and url:
        ref = f'{title} ({url})'
    elif url:
        ref = url
    else:
        ref = title
    return EvidenceCard(
        evidence_id=f'{source_type}-{idx}',
        source_type=source_type,
        title=title,
        ref=ref,
        snippet=snippet,
        supported_claims=[],
        confidence=0.6,
        metadata={
            'query': query,
            'url': url,
            'source': source_type,
        },
    )


def _dedupe_cards(cards: Iterable[EvidenceCard], *, limit: int) -> List[EvidenceCard]:
    if int(limit) <= 0:
        return []
    deduped: list[EvidenceCard] = []
    seen: set[str] = set()
    max_items = int(limit)
    for card in cards:
        key = '|'.join(
            [
                str(card.source_type),
                str(card.ref or ''),
                str(card.title or ''),
                str(card.snippet[:120] or ''),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(card)
        if len(deduped) >= max_items:
            break
    return deduped


def _should_try_web(task: LongFormTaskSchema) -> bool:
    return task.source_policy in {'web_allowed', 'arxiv_preferred'}


def _should_try_arxiv(task: LongFormTaskSchema, node: OutlineNode) -> bool:
    text = ' '.join(
        [
            task.genre,
            task.query,
            node.title,
            node.goal,
            ' '.join(node.evidence_needs),
        ]
    ).lower()
    if task.source_policy == 'arxiv_preferred':
        return True
    return any(k in text for k in ('arxiv', 'paper', '论文', '文献', 'research'))


def _extract_query_plan(raw: Any) -> tuple[list[str], list[str]]:
    parsed = parse_json_text(raw, default={})
    if not isinstance(parsed, dict):
        return [], []
    queries = [
        str(q).strip()
        for q in (parsed.get('queries') or [])
        if str(q).strip()
    ]
    claims = [
        str(c).strip()
        for c in (parsed.get('claims') or [])
        if str(c).strip()
    ]
    return queries, claims


class EvidenceCollector:
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

    def _build_queries(
        self,
        task: LongFormTaskSchema,
        node: OutlineNode,
    ) -> tuple[list[str], list[str]]:
        base_queries = [q for q in node.retrieval_queries if q]
        base_claims = [c for c in node.evidence_needs if c]
        if not callable(self._llm):
            return base_queries, base_claims

        prompt = _fill_prompt(
            EVIDENCE_QUERY_PROMPT,
            task_json=json.dumps(task.to_dict(), ensure_ascii=False, indent=2),
            node_json=json.dumps(node.to_dict(), ensure_ascii=False, indent=2),
        )
        llm_output = self._call_llm(prompt)
        if not llm_output:
            return base_queries, base_claims
        queries, claims = _extract_query_plan(llm_output)
        merged_queries = base_queries + [q for q in queries if q not in base_queries]
        merged_claims = base_claims + [c for c in claims if c not in base_claims]
        return merged_queries, merged_claims

    def collect(
        self,
        *,
        task: LongFormTaskSchema,
        node: OutlineNode,
        runtime_params: Mapping[str, Any],
    ) -> tuple[list[EvidenceCard], list[str]]:
        warnings: list[str] = []
        enable_evidence = _runtime_bool(runtime_params, 'lclm_enable_evidence', True)
        node_topk = _runtime_int(runtime_params, 'lclm_node_evidence_topk', 5)

        if not enable_evidence:
            reason = 'lclm_enable_evidence=false'
            warnings.append(f'章节 {node.node_id} 已跳过证据检索：{reason}')
            _log_info(f'[LCLM] evidence skipped reason={reason} node_id={node.node_id}')
            return [], warnings

        if node_topk <= 0:
            reason = f'lclm_node_evidence_topk={node_topk}'
            warnings.append(f'章节 {node.node_id} 已跳过证据检索：{reason}')
            _log_info(f'[LCLM] evidence skipped reason={reason} node_id={node.node_id}')
            return [], warnings

        queries, claims = self._build_queries(task, node)
        if not queries:
            queries = [f'{task.query} {node.title}', node.goal]
        node.evidence_needs = claims or node.evidence_needs
        node.retrieval_queries = queries

        query_topk = max(1, min(node_topk, 8))
        cards: list[EvidenceCard] = []

        has_kb_context = bool(runtime_params.get('kb_id') or runtime_params.get('temp_files'))
        if has_kb_context:
            kb_search_fn = runtime_params.get('lclm_kb_search')
            if not callable(kb_search_fn):
                from chat.tools import kb as kb_tools
                kb_search_fn = kb_tools.kb_search

            for q_idx, query in enumerate(queries[:3], start=1):
                try:
                    search_result = kb_search_fn(query=query, topk=query_topk)
                except Exception as exc:
                    msg = f'章节 {node.node_id} KB 检索失败：{exc}'
                    warnings.append(msg)
                    _log_warning(f'[LCLM] {msg}')
                    continue
                for idx, item in enumerate(_extract_items(search_result), start=1):
                    cards.append(_kb_card_from_item(item, idx=(q_idx * 100 + idx), query=query))

        if not cards:
            warnings.append(f'章节 {node.node_id} KB 证据不足，已尝试外部补充。')

        enable_arxiv = _runtime_bool(runtime_params, 'lclm_enable_arxiv', True)
        enable_web = _runtime_bool(runtime_params, 'lclm_enable_web', True)
        try_arxiv = enable_arxiv and _should_try_arxiv(task, node)
        try_web = enable_web and _should_try_web(task)
        if (try_arxiv or try_web) and len(cards) < max(1, node_topk // 2):
            arxiv_fn = runtime_params.get('lclm_arxiv_search')
            web_fn = runtime_params.get('lclm_web_search')
            if (try_arxiv and not callable(arxiv_fn)) or (try_web and not callable(web_fn)):
                from chat.tools import web_search as web_tools
                if try_arxiv and not callable(arxiv_fn):
                    arxiv_fn = web_tools.arxiv_search
                if try_web and not callable(web_fn):
                    web_fn = web_tools.web_search

            for query in queries[:2]:
                if try_arxiv:
                    try:
                        arxiv = arxiv_fn(query=query, max_results=min(5, query_topk))
                    except Exception as exc:
                        msg = f'章节 {node.node_id} arXiv 检索失败（已降级）：{exc}'
                        warnings.append(msg)
                        _log_warning(f'[LCLM] {msg}')
                        arxiv = None
                    if arxiv is None:
                        pass
                    else:
                        for idx, item in enumerate(_extract_items(arxiv), start=1):
                            cards.append(
                                _web_card_from_item(
                                    item,
                                    idx=idx,
                                    source_type='arxiv',
                                    query=query,
                                )
                            )

                if try_web:
                    try:
                        web = web_fn(query=query, source='auto', topk=min(5, query_topk))
                    except Exception as exc:
                        msg = f'章节 {node.node_id} Web 检索失败（已降级）：{exc}'
                        warnings.append(msg)
                        _log_warning(f'[LCLM] {msg}')
                        web = None
                    if web is None:
                        pass
                    else:
                        for idx, item in enumerate(_extract_items(web), start=1):
                            cards.append(
                                _web_card_from_item(
                                    item,
                                    idx=idx,
                                    source_type='web',
                                    query=query,
                                )
                            )

        if not enable_arxiv and _should_try_arxiv(task, node):
            _log_info(f'[LCLM] evidence skipped reason=lclm_enable_arxiv=false node_id={node.node_id}')
        if not enable_web and _should_try_web(task):
            _log_info(f'[LCLM] evidence skipped reason=lclm_enable_web=false node_id={node.node_id}')

        deduped = _dedupe_cards(cards, limit=node_topk)
        if not deduped:
            warnings.append(f'章节 {node.node_id} 未检索到可用证据卡。')
        return deduped, warnings
