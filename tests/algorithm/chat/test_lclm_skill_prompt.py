from pathlib import Path

from chat.components.agentic.config import _augment_skills_for_request
import chat.prompts.lclm as lclm_prompts


def test_lclm_prompt_constants_exist():
    assert 'JSON' in lclm_prompts.TASK_SCHEMA_PROMPT
    assert 'nodes' in lclm_prompts.OUTLINE_PLANNER_PROMPT
    assert 'queries' in lclm_prompts.EVIDENCE_QUERY_PROMPT
    assert 'Markdown' in lclm_prompts.SECTION_WRITER_PROMPT
    assert 'repair_instructions' in lclm_prompts.SECTION_CRITIC_PROMPT
    assert '修订' in lclm_prompts.GLOBAL_REVISION_PROMPT
    assert '核心结论' in lclm_prompts.FINAL_FORMAT_PROMPT


def test_outline_longform_skill_file_exists_and_has_required_sections():
    root = Path(__file__).resolve().parents[3]
    skill_path = root / 'skills/.curated/outline-longform-generation/SKILL.md'
    assert skill_path.exists()
    text = skill_path.read_text(encoding='utf-8').lower()
    assert 'outline-first' in text
    assert '不要用于 pptx' in text
    assert 'hard controls' in text
    assert 'soft controls' in text
    assert 'artifact' in text
    assert 'download_link' in text


def test_lclm_skill_is_augmented_without_affecting_pptx_intent():
    longform_skills = _augment_skills_for_request(
        [],
        query='请详细调研一下 RAG 与 Agent 的技术路线并输出长文',
        available_tools=['kb_search', 'web_search'],
    )
    pptx_skills = _augment_skills_for_request(
        [],
        query='帮我生成一个PPT',
        available_tools=['html_deck_generate_visual_pptx', 'artifact_save'],
    )

    assert 'outline-longform-generation' in longform_skills
    assert 'outline-longform-generation' not in pptx_skills
