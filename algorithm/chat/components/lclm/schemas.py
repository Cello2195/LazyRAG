from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

_FENCE_RE = re.compile(
    r'^\s*```(?:json|javascript|js|markdown|md)?\s*(.*?)\s*```\s*$',
    re.IGNORECASE | re.DOTALL,
)
_PLACEHOLDER_KEYS = (
    'query',
    'question',
    'task',
    'input',
)


def strip_markdown_fence(text: str) -> str:
    raw = str(text or '').strip()
    if not raw:
        return raw
    match = _FENCE_RE.match(raw)
    if match:
        return match.group(1).strip()
    return raw


def _extract_json_candidate(text: str) -> str:
    raw = strip_markdown_fence(text)
    if not raw:
        return raw
    if raw[0] in '{[' and raw[-1] in '}]':
        return raw

    start_obj = raw.find('{')
    start_arr = raw.find('[')
    candidates = [idx for idx in (start_obj, start_arr) if idx >= 0]
    if not candidates:
        return raw
    start = min(candidates)
    open_ch = raw[start]
    close_ch = '}' if open_ch == '{' else ']'

    depth = 0
    in_str = False
    esc = False
    end = -1
    for idx, ch in enumerate(raw[start:], start=start):
        if in_str:
            if esc:
                esc = False
                continue
            if ch == '\\':
                esc = True
                continue
            if ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == open_ch:
            depth += 1
            continue
        if ch == close_ch:
            depth -= 1
            if depth == 0:
                end = idx
                break
    if end > start:
        return raw[start:end + 1]
    return raw


def parse_json_text(
    text: Any,
    *,
    default: Any = None,
    repair: Optional[Callable[[str], str]] = None,
) -> Any:
    if isinstance(text, (dict, list)):
        return text
    if text is None:
        return default

    raw = str(text).strip()
    if not raw:
        return default

    candidate = _extract_json_candidate(raw)
    try:
        return json.loads(candidate)
    except Exception:
        pass

    if repair is not None:
        try:
            repaired = str(repair(raw) or '').strip()
            if repaired:
                return json.loads(_extract_json_candidate(repaired))
        except Exception:
            pass

    return default


@dataclass
class LongFormTaskSchema:
    query: str
    original_query: str = ''
    language: str = 'zh'
    genre: str = 'generic_longform'
    writing_type: str = 'generic_longform'
    output_type: str = 'longform'
    audience: str = 'general'
    target_length: str = 'long'
    citation_required: bool = True
    evidence_required: bool = True
    source_policy: str = 'kb_first'
    output_format: str = 'markdown'
    tone: str = 'technical'
    lclm_mode: str = 'auto'

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any], *, query: str) -> 'LongFormTaskSchema':
        data = dict(payload or {})
        normalized_query = str(data.get('query') or query or '').strip()
        if not normalized_query:
            normalized_query = str(query or '').strip()
        if not normalized_query:
            normalized_query = '长文本任务'
        original_query = str(data.get('original_query') or query or normalized_query).strip() or normalized_query
        return cls(
            query=normalized_query,
            original_query=original_query,
            language=str(data.get('language') or 'zh').strip().lower() or 'zh',
            genre=str(data.get('genre') or 'generic_longform').strip().lower() or 'generic_longform',
            writing_type=str(data.get('writing_type') or data.get('genre') or 'generic_longform').strip().lower() or 'generic_longform',
            output_type=str(data.get('output_type') or data.get('writing_type') or data.get('genre') or 'longform').strip().lower() or 'longform',
            audience=str(data.get('audience') or 'general').strip().lower() or 'general',
            target_length=str(data.get('target_length') or 'long').strip().lower() or 'long',
            citation_required=bool(data.get('citation_required', True)),
            evidence_required=bool(data.get('evidence_required', data.get('citation_required', True))),
            source_policy=str(data.get('source_policy') or 'kb_first').strip().lower() or 'kb_first',
            output_format=str(data.get('output_format') or 'markdown').strip().lower() or 'markdown',
            tone=str(data.get('tone') or 'technical').strip().lower() or 'technical',
            lclm_mode=str(data.get('lclm_mode') or 'auto').strip().lower() or 'auto',
        )


STORY_GENRES = {'story', 'fiction', 'short_story', 'novel', 'creative_writing'}


def is_story_task(task: LongFormTaskSchema) -> bool:
    values = {
        str(task.genre or '').strip().lower(),
        str(task.writing_type or '').strip().lower(),
        str(task.output_type or '').strip().lower(),
    }
    return bool(values & STORY_GENRES)


@dataclass
class EvidenceCard:
    evidence_id: str
    source_type: str
    title: str
    ref: str
    snippet: str
    supported_claims: List[str] = field(default_factory=list)
    confidence: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OutlineNode:
    node_id: str
    title: str
    level: int
    parent_id: Optional[str]
    goal: str
    expected_words: int
    evidence_needs: List[str] = field(default_factory=list)
    retrieval_queries: List[str] = field(default_factory=list)
    hard_controls: Dict[str, Any] = field(default_factory=dict)
    soft_controls: Dict[str, Any] = field(default_factory=dict)
    tool_policy: Dict[str, Any] = field(default_factory=dict)
    evidence_cards: List[EvidenceCard] = field(default_factory=list)
    draft: str = ''
    critique: Dict[str, Any] = field(default_factory=dict)
    status: str = 'pending'

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload['evidence_cards'] = [card.to_dict() for card in self.evidence_cards]
        return payload

    @classmethod
    def from_dict(
        cls,
        payload: Dict[str, Any],
        *,
        fallback_id: str,
        default_words: int,
    ) -> 'OutlineNode':
        data = dict(payload or {})
        raw_cards = data.get('evidence_cards') if isinstance(data.get('evidence_cards'), list) else []
        cards = []
        for idx, raw in enumerate(raw_cards, start=1):
            if not isinstance(raw, dict):
                continue
            cards.append(
                EvidenceCard(
                    evidence_id=str(raw.get('evidence_id') or f'{fallback_id}-ev-{idx}'),
                    source_type=str(raw.get('source_type') or 'kb'),
                    title=str(raw.get('title') or 'evidence'),
                    ref=str(raw.get('ref') or ''),
                    snippet=str(raw.get('snippet') or ''),
                    supported_claims=[str(x) for x in (raw.get('supported_claims') or []) if str(x).strip()],
                    confidence=float(raw.get('confidence') or 0.5),
                    metadata=raw.get('metadata') if isinstance(raw.get('metadata'), dict) else {},
                )
            )

        node_id = str(data.get('node_id') or fallback_id).strip() or fallback_id
        goal = str(data.get('goal') or data.get('title') or f'完成章节 {node_id}').strip()
        title = str(data.get('title') or f'章节 {node_id}').strip() or f'章节 {node_id}'
        level = int(data.get('level') or 1)
        level = min(max(level, 1), 3)
        parent_id_raw = data.get('parent_id')
        parent_id = None if parent_id_raw in (None, '', 'null') else str(parent_id_raw)
        expected_words = int(data.get('expected_words') or default_words or 220)
        expected_words = min(max(expected_words, 80), 1600)

        return cls(
            node_id=node_id,
            title=title,
            level=level,
            parent_id=parent_id,
            goal=goal,
            expected_words=expected_words,
            evidence_needs=[
                str(x).strip()
                for x in (data.get('evidence_needs') or [])
                if str(x).strip()
            ],
            retrieval_queries=[
                str(x).strip()
                for x in (data.get('retrieval_queries') or [])
                if str(x).strip()
            ],
            hard_controls=data.get('hard_controls') if isinstance(data.get('hard_controls'), dict) else {},
            soft_controls=data.get('soft_controls') if isinstance(data.get('soft_controls'), dict) else {},
            tool_policy=data.get('tool_policy') if isinstance(data.get('tool_policy'), dict) else {},
            evidence_cards=cards,
            draft=str(data.get('draft') or ''),
            critique=data.get('critique') if isinstance(data.get('critique'), dict) else {},
            status=str(data.get('status') or 'pending'),
        )


@dataclass
class LongFormDocumentState:
    task: LongFormTaskSchema
    outline: List[OutlineNode] = field(default_factory=list)
    global_terms: Dict[str, str] = field(default_factory=dict)
    section_summaries: Dict[str, str] = field(default_factory=dict)
    citation_map: Dict[str, EvidenceCard] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    final_markdown: str = ''
    artifact: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task': self.task.to_dict(),
            'outline': [node.to_dict() for node in self.outline],
            'global_terms': dict(self.global_terms),
            'section_summaries': dict(self.section_summaries),
            'citation_map': {k: v.to_dict() for k, v in self.citation_map.items()},
            'warnings': list(self.warnings),
            'final_markdown': self.final_markdown,
            'artifact': dict(self.artifact),
        }


def coerce_task_schema(payload: Any, *, query: str, default_mode: str = 'auto') -> LongFormTaskSchema:
    parsed = parse_json_text(payload, default={})
    if not isinstance(parsed, dict):
        parsed = {}
    if not parsed:
        parsed = {'query': query}
    if 'query' not in parsed:
        for key in _PLACEHOLDER_KEYS:
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                parsed['query'] = value.strip()
                break
    if 'query' not in parsed:
        parsed['query'] = query
    if 'original_query' not in parsed:
        parsed['original_query'] = query
    if 'lclm_mode' not in parsed:
        parsed['lclm_mode'] = default_mode
    return LongFormTaskSchema.from_dict(parsed, query=query)


def coerce_outline_nodes(
    payload: Any,
    *,
    max_nodes: int,
    max_depth: int,
    default_words: int,
) -> List[OutlineNode]:
    parsed = parse_json_text(payload, default={})
    raw_nodes: list[Any]
    if isinstance(parsed, dict):
        candidates = parsed.get('outline') or parsed.get('nodes') or parsed.get('sections') or []
        raw_nodes = candidates if isinstance(candidates, list) else []
    elif isinstance(parsed, list):
        raw_nodes = parsed
    else:
        raw_nodes = []

    nodes: list[OutlineNode] = []
    for idx, raw_node in enumerate(raw_nodes[: max(1, int(max_nodes))], start=1):
        if not isinstance(raw_node, dict):
            continue
        fallback_id = str(raw_node.get('node_id') or idx)
        node = OutlineNode.from_dict(
            raw_node,
            fallback_id=fallback_id,
            default_words=default_words,
        )
        node.level = min(max(node.level, 1), max(1, int(max_depth)))
        nodes.append(node)
    return nodes
