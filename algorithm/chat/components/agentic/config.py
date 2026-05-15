from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, Tuple

try:
    from chat.prompts.agentic import (
        CITATION_GUIDANCE,
        DEFAULT_SYSTEM_PROMPT,
        MEMORY_GUIDANCE,
        SEARCH_GUIDANCE,
        SKILLS_GUIDANCE,
        PPTX_GENERATION_GUIDANCE,
        TOOL_CALL_STATUS_GUIDANCE,
        _COMBINED_REVIEW_PROMPT,
        _MEMORY_REVIEW_PROMPT,
        _SKILL_REVIEW_PROMPT,
    )
except ImportError:
    # Some lightweight tests patch a minimal fake prompt module that may miss
    # newer constants. Keep imports resilient for those environments.
    from chat.prompts.agentic import (  # type: ignore
        CITATION_GUIDANCE,
        DEFAULT_SYSTEM_PROMPT,
        MEMORY_GUIDANCE,
        SEARCH_GUIDANCE,
        SKILLS_GUIDANCE,
        TOOL_CALL_STATUS_GUIDANCE,
        _COMBINED_REVIEW_PROMPT,
        _MEMORY_REVIEW_PROMPT,
        _SKILL_REVIEW_PROMPT,
    )
    PPTX_GENERATION_GUIDANCE = ''
from chat.components.lclm.detector import (
    contains_lclm_intent as _contains_lclm_intent,
    contains_pptx_intent as _contains_lclm_pptx_intent,
)

DEFAULT_TOOLS = [
    'kb_search',
    'kb_get_parent_node',
    'kb_get_window_nodes',
    'kb_keyword_search',
    'web_search',
    'url_fetch',
    'arxiv_search',
    'memory',
    'skill_manage',
    'pptx_validate_schema',
    'pptx_create_from_schema',
    'pptx_generate_with_qa_loop',
    'pptx_parse',
    'pptx_render_thumbnails',
    'pptx_qa',
    'pptx_repair_schema',
    'html_deck_validate_schema',
    'html_deck_create_from_schema',
    'html_deck_preview',
    'html_deck_qa',
    'html_deck_render_screenshots',
    'pptx_create_from_html_screenshots',
    'html_deck_generate_visual_pptx',
    'artifact_save',
]

DEFAULT_PPTX_SKILLS = (
    'visual-pptx-generation',
    'pptx-generation',
)
DEFAULT_LCLM_SKILLS = (
    'outline-longform-generation',
)
_PPTX_INTENT_KEYWORDS = (
    'ppt',
    'pptx',
    'powerpoint',
    'slides',
    'deck',
    '幻灯片',
    '演示文稿',
    '汇报',
    '报告',
    'minimax',
    'guizang',
    '视觉化ppt',
    '科技感ppt',
)

BUILTIN_FILE_TOOLS = (
    'read_file',
    'list_dir',
    'search_in_files',
    'make_dir',
    'write_file',
    'delete_file',
    'move_file',
)

REVIEW_TOOLS: dict[str, list[str]] = {
    'memory': ['memory'],
    'skill': ['skill_manage'],
    'combined': ['memory', 'skill_manage'],
}

REVIEW_PROMPTS: dict[str, str] = {
    'memory': _MEMORY_REVIEW_PROMPT,
    'skill': _SKILL_REVIEW_PROMPT,
    'combined': _COMBINED_REVIEW_PROMPT,
}


def _normalize_skill_fs_url(value: Any) -> str:
    """Best-effort skill FS URL normalization without hard import coupling.

    chat.utils.load_config pulls in runtime config/lazyllm dependencies at import
    time. Keep this helper lazy so lightweight checks/tests can import this module
    without requiring full runtime bootstrap.
    """
    try:
        from chat.utils.load_config import normalize_skill_fs_url as _normalize  # local import on purpose
        return _normalize(value)
    except Exception:
        if value is None:
            return ''
        text = str(value).strip()
        return text.rstrip('/')


def _normalize_available_tools(tools: Any) -> list[str]:
    if tools is None:
        return list(DEFAULT_TOOLS)
    if isinstance(tools, str):
        tools = [tools]
    if not isinstance(tools, list):
        return list(DEFAULT_TOOLS)
    if any(isinstance(t, str) and t.lower() == 'all' for t in tools):
        return list(DEFAULT_TOOLS)
    return [t for t in tools if isinstance(t, str) and t]


def _merge_builtin_file_tools(tools: list[str]) -> list[str]:
    merged: list[str] = []
    seen_names: set[str] = set()

    for tool in tools:
        if not isinstance(tool, str) or not tool:
            continue
        tool_name = tool.rsplit('.', 1)[-1]
        if tool_name in seen_names:
            continue
        seen_names.add(tool_name)
        merged.append(tool)

    for tool_name in BUILTIN_FILE_TOOLS:
        if tool_name in seen_names:
            continue
        seen_names.add(tool_name)
        merged.append(tool_name)

    return merged


def _normalize_available_skills(skills: Any) -> list[str]:
    if skills is None:
        return []
    if isinstance(skills, str):
        skills = [skills]
    if not isinstance(skills, list):
        return []
    return [skill for skill in skills if isinstance(skill, str) and skill]


def _contains_pptx_intent(query: str) -> bool:
    text = str(query or '').strip().lower()
    if not text:
        return False
    return any(keyword in text for keyword in _PPTX_INTENT_KEYWORDS)


def _augment_skills_for_request(
    available_skills: list[str],
    *,
    query: str,
    available_tools: list[str],
) -> list[str]:
    if not isinstance(available_skills, list):
        available_skills = []

    needs_pptx_skill = _contains_pptx_intent(query) and (
        'html_deck_generate_visual_pptx' in available_tools
        or 'pptx_create_from_schema' in available_tools
    )
    if not needs_pptx_skill:
        # Additive long-form skill enhancement, without touching PPTX route.
        if _contains_lclm_intent(query) and not _contains_lclm_pptx_intent(query):
            merged = list(available_skills)
            for skill in DEFAULT_LCLM_SKILLS:
                if skill not in merged:
                    merged.append(skill)
            return merged
        return available_skills

    merged: list[str] = []
    seen: set[str] = set()
    for skill in available_skills:
        if isinstance(skill, str) and skill and skill not in seen:
            seen.add(skill)
            merged.append(skill)
    for skill in DEFAULT_PPTX_SKILLS:
        if skill not in seen:
            seen.add(skill)
            merged.append(skill)
    return merged


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == '':
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _parse_dataset_url(dataset_url: str) -> Tuple[str, str]:
    parts = [p.strip() for p in str(dataset_url).split(',', 1)]
    kb_url = parts[0] if parts else ''
    kb_name = parts[1] if len(parts) > 1 else ''
    return kb_url, kb_name


def _sync_request_context(config: dict) -> None:
    filters = config.get('filters') if isinstance(config.get('filters'), dict) else {}
    raw_kb_id = filters.get('kb_id')
    if not raw_kb_id:
        raw_kb_id = config.get('kb_id')

    kb_id = ''
    if isinstance(raw_kb_id, str):
        kb_id = raw_kb_id.strip()
    elif isinstance(raw_kb_id, list):
        for item in raw_kb_id:
            if isinstance(item, str) and item.strip():
                kb_id = item.strip()
                break

    if kb_id:
        config['kb_id'] = kb_id
    else:
        config.pop('kb_id', None)

    files = config.get('files') or []
    config['temp_files'] = files if isinstance(files, list) else []

    kb_url, kb_name = _parse_dataset_url(config.get('document_url') or '')
    if kb_url:
        config['kb_url'] = kb_url
    if kb_name:
        config['kb_name'] = kb_name
    config['skill_fs_url'] = _normalize_skill_fs_url(config.get('skill_fs_url'))


def _filter_tools_for_request(tools: list[str], config: dict) -> list[str]:
    if config.get('kb_id'):
        return tools

    has_temp_files = bool(config.get('temp_files'))
    filtered = []
    for tool in tools:
        if not tool.startswith('kb_'):
            filtered.append(tool)
        elif has_temp_files and tool == 'kb_search':
            filtered.append(tool)
    return filtered


def _build_runtime_system_prompt(config: dict, available_tools: list[str]) -> str:
    prompt_parts = [DEFAULT_SYSTEM_PROMPT]

    tool_guidance: list[str] = []
    if 'memory' in available_tools and config.get('use_memory', True):
        tool_guidance.append(MEMORY_GUIDANCE)
    if 'skill_manage' in available_tools:
        tool_guidance.append(SKILLS_GUIDANCE)
    if tool_guidance:
        prompt_parts.append(' '.join(tool_guidance))
    if available_tools:
        prompt_parts.append(TOOL_CALL_STATUS_GUIDANCE)
    if any(tool.startswith('kb_') for tool in available_tools):
        prompt_parts.append(CITATION_GUIDANCE)
    if (
        'web_search' in available_tools
        or 'arxiv_search' in available_tools
        or 'url_fetch' in available_tools
    ):
        prompt_parts.append(SEARCH_GUIDANCE)
    if 'pptx_create_from_schema' in available_tools or 'html_deck_generate_visual_pptx' in available_tools:
        prompt_parts.append(PPTX_GENERATION_GUIDANCE)

    return '\n\n'.join(prompt_parts)


@lru_cache(maxsize=1)
def _get_runtime_agent_defaults() -> Dict[str, Any]:
    from config import config as _cfg
    return {
        'kb_url': _cfg['agentic_kb_url'],
        'core_api_url': _cfg['core_api_url'],
        'kb_name': _cfg['agentic_kb_name'],
        'skill_fs_url': _cfg['skill_fs_url'],
        'es_url': _cfg['opensearch_uri'],
        'es_user': _cfg['opensearch_user'],
        'es_password': _cfg['opensearch_password'],
        'web_search_timeout': _cfg['web_search_timeout'],
        'web_search_auto_sources': _cfg['web_search_auto_sources'],
        'web_search_wikipedia_base_url': _cfg['web_search_wikipedia_base_url'],
        'web_search_google_api_key': _cfg['web_search_google_api_key'],
        'web_search_google_search_engine_id': _cfg['web_search_google_search_engine_id'],
        'web_search_bing_subscription_key': _cfg['web_search_bing_subscription_key'],
        'web_search_bing_endpoint': _cfg['web_search_bing_endpoint'],
        'web_search_bocha_api_key': _cfg['web_search_bocha_api_key'],
        'web_search_bocha_base_url': _cfg['web_search_bocha_base_url'],
        'arxiv_search_timeout': _cfg['arxiv_search_timeout'],
        'lclm_mode': _cfg['lclm_mode'],
        'lclm_max_outline_nodes': _cfg['lclm_max_outline_nodes'],
        'lclm_max_depth': _cfg['lclm_max_depth'],
        'lclm_use_llm': _cfg['lclm_use_llm'],
        'lclm_section_min_words': _cfg['lclm_section_min_words'],
        'lclm_section_max_words': _cfg['lclm_section_max_words'],
        'lclm_node_evidence_topk': _cfg['lclm_node_evidence_topk'],
        'lclm_enable_evidence': _cfg['lclm_enable_evidence'],
        'lclm_enable_arxiv': _cfg['lclm_enable_arxiv'],
        'lclm_enable_web': _cfg['lclm_enable_web'],
        'lclm_max_repair_rounds': _cfg['lclm_max_repair_rounds'],
        'lclm_save_artifact': _cfg['lclm_save_artifact'],
        'lclm_preview_chars': _cfg['lclm_preview_chars'],
    }
