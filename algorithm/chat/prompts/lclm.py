# flake8: noqa

TASK_SCHEMA_PROMPT = """
你是 Long-Form 任务解析器。请把用户任务解析为 JSON：
{
  "query": "...",
  "language": "zh|en|auto",
  "genre": "survey|report|research_report|technical_report|proposal|paper_summary|technical_plan|article|essay|story|fiction|short_story|novel|script|dialogue|outline_only|generic_longform",
  "writing_type": "report|article|essay|story|fiction|script|dialogue|outline_only|generic_longform",
  "output_type": "report|short_story|novel|script|essay|outline|longform",
  "audience": "engineer|researcher|business|general",
  "target_length": "short|medium|long|very_long",
  "citation_required": true,
  "evidence_required": true,
  "source_policy": "kb_first|web_allowed|arxiv_preferred|no_external",
  "output_format": "markdown|txt|html",
  "tone": "technical|academic|concise|formal|user_preferred",
  "lclm_mode": "auto|force|off"
}

输入任务：
{query}

要求：
1) 只输出 JSON 对象，不要输出解释。
2) 中文请求默认 language=zh。
3) 如果用户要求“简短回答/只要命令”，target_length=short。
4) 如果用户要求小说、故事、短篇小说、长文本小说、主人公、对话、剧情、情节、角色、结局、叙事，必须设置 genre=story 或 fiction，output_type=short_story，citation_required=false，evidence_required=false，source_policy=no_external。
5) hard controls：不得虚构字段，不得省略 query。
6) soft controls：合理推断 genre 与 audience。
"""

OUTLINE_PLANNER_PROMPT = """
你是 Outline Planner。请根据任务生成可执行大纲 JSON。

任务 JSON：
{task_json}

输出格式：
{
  "title": "...",
  "nodes": [
    {
      "node_id": "1",
      "title": "...",
      "level": 1,
      "parent_id": null,
      "goal": "...",
      "expected_words": 260,
      "evidence_needs": ["..."],
      "retrieval_queries": ["..."],
      "hard_controls": {
        "no_hallucination": true,
        "citation_required": true
      },
      "soft_controls": {
        "style": "technical",
        "avoid_redundancy": true
      },
      "tool_policy": {
        "kb_first": true,
        "web_allowed": true
      }
    }
  ]
}

规则：
1) 先有大纲再写作，节点数控制在 {max_nodes} 以内，层级不超过 {max_depth}。
2) 每个节点都要有 evidence_needs 与 retrieval_queries。
3) hard controls 与 soft controls 必须显式区分。
4) 如果 genre=story/fiction/short_story/novel，必须生成小说场景大纲，节点围绕 scene/chapter、characters、setting、conflict、dialogue_requirement、plot_function，不要生成报告章节，不要写 evidence_needs/retrieval_queries，不要提证据或引用。
5) 只输出 JSON，不要输出解释文本。
"""

EVIDENCE_QUERY_PROMPT = """
你是检索任务分解器。基于节点目标生成检索查询 JSON。

任务：
{task_json}

当前节点：
{node_json}

输出：
{
  "queries": ["..."],
  "claims": ["..."],
  "notes": "..."
}

规则：
1) 查询应可被 kb_search / arxiv_search / web_search 执行。
2) 优先 KB，可补充 web/arxiv。
3) 不要输出多余文字，只输出 JSON。
"""

SECTION_WRITER_PROMPT = """
你是分节写作器。请只写“当前节点”的正文，不要输出全文大纲。

原始用户问题（source-of-truth）：
{original_query}

任务：
{task_json}

当前节点：
{node_json}

证据卡（仅可使用这些证据）：
{evidence_json}

前文摘要：
{previous_summary}

术语表：
{global_terms_json}

写作要求：
1) 只写本节内容，围绕 node.goal。
2) 事实性结论尽量绑定证据；KB 证据使用原始 [[n]]。
3) 没有证据时明确写“目前证据不足以支持更强结论”。
4) 不得编造 [[n]]，不得复制证据原文大段内容。
5) 不要输出 JSON，只输出 Markdown 正文。
6) 不要输出任何思考标签、提示词回显、元推理说明（如“让我分析”“用户要求我”）。
"""

STORY_SECTION_WRITER_PROMPT = """
你是小说章节写作者。请只写当前场景/章节的小说正文，不要输出分析、报告、JSON 或提示词回显。

原始用户问题（source-of-truth）：
{original_query}

任务：
{task_json}

当前场景节点：
{node_json}

前文摘要：
{previous_summary}

术语表：
{global_terms_json}

写作要求：
1) 只输出小说正文，可以包含自然段和真实对话。
2) 必须有人物行动、场景描写、对话、剧情推进。
3) 如果用户要求至少两个主人公，至少让两个主要角色出现并互动。
4) 如果用户要求有对话，必须出现带引号或“角色：台词”形式的真实对话。
5) 如果用户要求有剧情，必须推进起因、冲突、转折或结尾之一。
6) 不要输出“本章旨在”“本报告”“背景与问题定义”“方法路线”“关键分析维度”“推荐实施方案”“风险与测试建议”。
7) 不要输出 citation，如 [[1]]；不要输出 KB 证据不足或证据相关说明。
8) 不要输出任何思考标签、元推理或提示词回显。
"""

SECTION_CRITIC_PROMPT = """
你是章节审校器。请审查章节是否满足任务并返回 JSON：
{
  "passed": true,
  "scores": {
    "task_completion": 1-5,
    "evidence_grounding": 1-5,
    "coherence": 1-5,
    "style": 1-5,
    "redundancy": 1-5
  },
  "issues": ["..."],
  "repair_instructions": ["..."]
}

任务：
{task_json}

节点：
{node_json}

章节文本：
{section_text}

只输出 JSON。
"""

GLOBAL_REVISION_PROMPT = """
你是全局修订器。请对长文进行一次整体修订，保持结构不变并提高一致性。

任务：
{task_json}

当前全文：
{document_markdown}

要求：
1) 统一术语、去重、修正跨节冲突。
2) 保留引用标记（如 [[1]]），不得新增伪造引用。
3) 不要输出解释，只输出修订后的 Markdown。
"""

FINAL_FORMAT_PROMPT = """
你是最终格式化器。将内容整理为主流深度研究报告结构：

# 标题
> 核心结论：2-4句

## 1. ...
## 2. ...
### 2.1 ...

输入正文：
{document_markdown}

格式要求：
1) H2/H3 层级清晰，段落有实质内容。
2) 避免通篇 bullet，只在必要总结时使用。
3) 输出为 {output_format} 风格文本（优先 Markdown）。
4) 不要输出内部 JSON 或流程说明。
"""
