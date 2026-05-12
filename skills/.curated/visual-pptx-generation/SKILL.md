---
name: visual-pptx-generation
description: Generate visual PPTX files from user requests. Use this skill when the user asks to create, generate, export, design, or improve a PowerPoint/PPT/PPTX/deck/slides presentation, especially when visual quality matters.
---

# Visual PPTX Generation Skill

This skill controls how LazyRAG converts a user request into a real visual PPTX artifact through the HTML-deck route.

The goal is **not** to return a slide outline. The goal is to generate a real downloadable PPTX whose HTML render already contains enough substantive body content.

## 0. Non-negotiable rule: never generate title-only body slides

Before calling any PPTX / HTML-deck generation tool, you must build a complete `deck_schema` with real slide content.

A deck is invalid if most slides contain only:

```json
{"type": "content_bullets", "title": "..."}
```

or only chapter titles / agenda items without explanatory content.

For every non-cover, non-toc, non-section-divider slide, at least one of the following must be true:

- `bullets` has **3–6** concrete bullets;
- `cards` has **3–6** cards, and each card has both `title` and `body`;
- `metrics` has **2–4** metrics, and each metric has `label`, `value`, and `description`;
- `headers` and `rows` form a real table with at least **3 rows**;
- `left` and `right` each contain a title and at least **3 bullets**;
- `steps` / `items` has at least **4** process or timeline entries;
- `quote` has a concrete quoted idea plus an `author` or `source` when available.

If this condition is not satisfied, **do not call** `html_deck_generate_visual_pptx`. First expand the schema into a content-complete deck.

## 1. When to use this skill

Use this skill when the user asks for any of the following:

- 生成 PPT / PPTX / PowerPoint / slides / deck
- 做一个汇报 / 演示文稿 / 讲座幻灯片
- 生成更好看的 PPT
- 生成类似 MiniMax / guizang / 科技感 / 发布会风 / 视觉化 的 PPT
- 把资料、论文、报告、检索结果整理成 PPT
- 输出可下载的 PPTX 文件

Do not only provide a textual outline unless the user explicitly asks only for an outline.

## 2. Preferred generation route

For this skill, prefer the visual route unless the user explicitly asks for editable text.

### 2.1 visual_pptx route

Use this route when the user emphasizes:

- 好看
- 视觉化
- 科技感
- MiniMax 风格
- guizang 风格
- 发布会风
- 演讲展示
- demo
- 产品介绍
- 不强要求每个元素可编辑

Tool route:

```text
deck_schema
→ html_deck_generate_visual_pptx
```

Prefer the one-shot tool `html_deck_generate_visual_pptx` when available. It should internally handle:

```text
normalize schema
→ validate schema
→ create HTML deck
→ QA
→ Playwright screenshots
→ image-based PPTX
→ artifact save
```

If the one-shot tool is unavailable, use the lower-level tools in this order:

```text
html_deck_create_from_schema
→ html_deck_qa
→ html_deck_render_screenshots
→ pptx_create_from_html_screenshots
→ artifact_save
```

### 2.2 editable_pptx route

Use the editable route only when the user explicitly emphasizes:

- 可编辑
- 正式办公交付
- 后续还要手动修改
- 表格和文字准确性优先
- 不强调强视觉效果

Tool route:

```text
deck_schema
→ pptx_create_from_schema
→ pptx_parse
→ pptx_qa
→ artifact_save
```

## 3. Content-first construction policy

When the user only gives a topic, you must infer and write the slide body content yourself. Do not leave empty placeholders such as `内容待补充`, `TBD`, `待完善`, `请输入内容`, `示例内容`, or `N/A`.

A good visual deck should usually contain:

```text
cover: 1 slide
toc: 1 slide
section_divider: 1–3 slides, optional
substantive body slides: at least 5 slides
summary: 1 slide
references: optional, only when sources exist
```

For normal Chinese PPT requests, generate **8–12 slides** unless the user specifies a different number. For a short deck, still ensure at least **4 substantive body slides**.

Each body slide should express a complete point:

```text
main claim → supporting explanation → implication / action
```

Do not create one slide per outline heading unless each slide also has actual body content.

## 4. Body-content density requirements by slide type

Use the following minimum density requirements before tool invocation.

| Slide type | Required content |
|---|---|
| `cover` | `title` + meaningful `subtitle`; optional `highlight` |
| `toc` | 4–7 concrete agenda items |
| `section_divider` | `title` + `subtitle`; no dense body required |
| `content_bullets` | 3–6 bullets; each bullet should be 18–45 Chinese chars or 8–22 English words |
| `challenge_cards` | 3–6 cards; each card has `title` + `body`; body should explain the point, not repeat the title |
| `metric_cards` | 2–4 metrics; each metric has `label`, `value`, `description`; if exact data is unavailable, use qualitative values such as “High”, “Medium”, “Low” instead of inventing numbers |
| `two_column` | `left` and `right`; each column has `title` and 3–5 bullets |
| `comparison` | either `headers` + 3–6 `rows`, or `left_title/right_title` + 3–5 items on each side |
| `table` | 3–5 headers and 3–8 rows |
| `process` | 4–5 steps in `steps` or `items` |
| `timeline` | 4–5 entries; each entry has `time`, `title`, and `desc` |
| `summary` | 3–5 takeaways, each with a clear conclusion or action |
| `references` | actual source names / URLs / document titles only; do not fabricate |

Content should be compact enough for HTML rendering but not empty. Prefer short, information-dense phrases over long paragraphs.

## 5. Required deck_schema structure

Always build a structured `deck_schema` before calling PPTX tools.

A valid visual schema should look like this pattern:

```json
{
  "title": "AI时代下的程序员该何去何从",
  "subtitle": "职业生存指南与能力升级路线",
  "language": "zh",
  "audience": "technical",
  "style": "auto",
  "visual_theme": "auto",
  "slides": [
    {
      "type": "cover",
      "title": "AI时代下的程序员该何去何从",
      "subtitle": "从岗位冲击到能力重塑的行动路线",
      "highlight": "VISUAL BRIEFING"
    },
    {
      "type": "toc",
      "title": "目录",
      "items": [
        "AI如何改变开发范式",
        "程序员真正面临的风险",
        "人类开发者的新机会",
        "能力升级路线",
        "短中长期行动建议"
      ]
    },
    {
      "type": "section_divider",
      "title": "01 AI正在重塑开发分工",
      "subtitle": "变化的核心不是工具替代，而是软件生产链条被重新组织"
    },
    {
      "type": "content_bullets",
      "title": "AI编程工具改变的是开发工作的重心",
      "subtitle": "基础代码产出变快后，瓶颈会转向问题定义、系统设计和结果验证",
      "bullets": [
        "重复性编码、样板代码和简单接口开发更容易被自动化工具压缩。",
        "需求拆解、架构取舍、边界条件识别仍然依赖工程经验和上下文判断。",
        "开发者需要从“写代码的人”转向“定义问题并验证系统的人”。",
        "团队评价标准会从单点编码速度转向端到端交付质量和稳定性。"
      ]
    },
    {
      "type": "challenge_cards",
      "title": "程序员面临的主要挑战",
      "subtitle": "风险集中在低复杂度、低上下文、低责任边界的工作环节",
      "cards": [
        {
          "title": "低端任务压缩",
          "body": "简单 CRUD、脚本拼接和模板化页面会被 AI 工具快速覆盖，岗位议价能力下降。",
          "accent": "danger"
        },
        {
          "title": "效率基准提高",
          "body": "企业会默认开发者能够使用 AI 工具完成更快的原型实现和问题定位。",
          "accent": "primary"
        },
        {
          "title": "知识更新加速",
          "body": "模型、框架和工具链更新频率提高，单一技术栈经验的保质期变短。",
          "accent": "secondary"
        },
        {
          "title": "结果验证更重要",
          "body": "AI 生成内容可能隐藏逻辑漏洞，开发者必须具备测试、审查和系统性验证能力。",
          "accent": "success"
        }
      ]
    },
    {
      "type": "metric_cards",
      "title": "竞争力将转向复合型工程能力",
      "subtitle": "不要编造未经证实的具体数字；无证据时使用定性等级",
      "metrics": [
        {
          "label": "自动化替代风险",
          "value": "High",
          "description": "重复性编码任务更容易被工具接管"
        },
        {
          "label": "系统设计价值",
          "value": "High",
          "description": "复杂系统的边界、可靠性和扩展性仍需人类判断"
        },
        {
          "label": "AI协作能力",
          "value": "Rising",
          "description": "会提问、会拆解、会验证的人能获得更高生产力杠杆"
        }
      ],
      "bullets": [
        "核心变化是能力结构升级，而不是简单的岗位消失。",
        "越接近业务目标和系统责任，越不容易被单点工具替代。"
      ]
    },
    {
      "type": "two_column",
      "title": "从传统程序员到AI协作型工程师",
      "left": {
        "title": "传统工作方式",
        "bullets": [
          "根据需求直接实现功能",
          "主要依赖个人编码速度",
          "问题定位依赖经验搜索",
          "测试和文档常被后置处理"
        ]
      },
      "right": {
        "title": "AI协作工作方式",
        "bullets": [
          "先拆解任务并设计验证标准",
          "用 AI 快速生成候选实现",
          "通过测试和审查筛选结果",
          "把知识沉淀为模板、工具和流程"
        ]
      }
    },
    {
      "type": "process",
      "title": "能力升级路线",
      "steps": [
        "夯实计算机基础：数据结构、网络、数据库、操作系统和工程规范。",
        "强化系统设计：学习模块边界、服务治理、性能优化和可观测性。",
        "掌握AI协作：把提示词、代码审查、测试生成和文档生成纳入日常流程。",
        "积累业务理解：理解真实场景中的成本、风险、用户体验和交付目标。",
        "形成作品闭环：用项目证明自己能独立完成从需求到上线的全过程。"
      ]
    },
    {
      "type": "summary",
      "title": "总结：AI时代的核心策略",
      "bullets": [
        "不要只和 AI 比拼基础编码速度，而要提升问题定义和系统设计能力。",
        "把 AI 当作生产力放大器，同时保持对结果的审查、测试和责任意识。",
        "通过真实项目沉淀方法论，建立比单一技术栈更长期的竞争力。"
      ]
    }
  ]
}
```

The example above is not a fixed template. Adapt the slide titles, bullets, cards, metrics, and process steps to the user’s actual topic.

## 6. Slide type policy

Choose slide types according to content:

| Content need | Preferred slide type |
|---|---|
| Title page | `cover` |
| Agenda | `toc` |
| New chapter | `section_divider` |
| Important statistics / indicators | `metric_cards` |
| Risks / challenges / opportunities | `challenge_cards` |
| Normal explanation | `content_bullets` |
| Two perspectives | `two_column` |
| Comparison | `comparison` |
| Data table | `table` |
| Process / roadmap | `process` or `timeline` |
| Quote / key idea | `quote` |
| Final conclusion | `summary` |
| Sources | `references` |

Avoid putting too much content on one slide, but never remove all body content. If a slide feels crowded, split it into two content-complete slides instead of leaving a title-only slide.

## 7. Schema self-check before tool call

Before calling `html_deck_generate_visual_pptx`, mentally run this checklist:

```text
[ ] slides is a list, not a JSON string
[ ] total slides are appropriate for the request, normally 8–12
[ ] cover has title and subtitle
[ ] toc has 4–7 items
[ ] every body slide has bullets/cards/metrics/table/columns/steps/timeline content
[ ] no body slide contains only title/subtitle
[ ] no placeholder words: TBD / 内容待补充 / N/A / 示例内容
[ ] metrics do not fabricate exact numbers without evidence
[ ] visual_theme is set to auto or a supported guizang theme
[ ] evidence_refs / references are preserved when using retrieved sources
```

If any checkbox fails, fix the schema first.

## 8. Theme policy

Do not hard-code one fixed theme.

If the user gives no preference, use:

```json
"visual_theme": "auto"
```

If the user requests a style, choose accordingly:

| User intent | Suggested theme |
|---|---|
| AI / Agent / system / engineering | `guizang_aurora` or `guizang_ink` |
| Business / product / project report | `guizang_business` or `guizang_blueprint` |
| Academic / paper / group meeting | `guizang_paper` or `guizang_blueprint` |
| High-end strategy / annual summary | `guizang_noir` |
| Editorial / course / public talk | `guizang_paper` |

If the user provides brand colors or preferred colors, pass them as `palette`.

Example:

```json
{
  "visual_theme": "auto",
  "palette": {
    "primary": "#7c3aed",
    "accent": "#f97316"
  }
}
```

## 9. Evidence and citations

If the PPT is based on retrieved documents, web pages, papers, or KB evidence:

- preserve important source information in `evidence_refs`;
- add a `references` slide when sources are numerous;
- do not invent data;
- do not fabricate statistics;
- if evidence is insufficient, state the limitation in the deck or final answer.

Example:

```json
{
  "type": "references",
  "title": "参考资料",
  "sources": [
    "Source 1: ...",
    "Source 2: ..."
  ]
}
```

## 10. Important output rule

The final answer must not be a raw JSON schema, raw HTML code, or only a slide outline.

The final answer should summarize:

```text
已生成 PPTX
- 文件名
- 页数
- 下载链接或文件路径
- HTML 预览链接或路径，if available
- QA 状态
- 如果失败，说明失败原因和下一步处理方式
```

If the tool returns a valid `download_url`, preserve it exactly. Do not rewrite, reconstruct, or modify download URLs.

## 11. Protect download link logic

Do not change or bypass the existing web download link logic.

When a tool returns fields such as:

```json
{
  "download_url": "...",
  "preview_url": "...",
  "file_path": "...",
  "artifact": {...},
  "artifacts": {...}
}
```

Use them as returned.

Do not invent a new URL.
Do not manually concatenate static file paths.
Do not modify backend static-file or signed-url logic.
Do not change frontend download button behavior.
Do not alter existing artifact_save implementation unless the user explicitly asks to fix download-link logic.

The current web download implementation is fragile and must be protected.

## 12. Failure handling

If a tool fails, do not repeatedly call tools without changing the input.

### 12.1 Schema parse failure

If the tool reports schema parsing failure:

1. Rebuild a clean `deck_schema`.
2. Ensure `slides` is a list, not a JSON string.
3. Retry once.

If it still fails, stop and return a concise error.

### 12.2 HTML content too thin

If QA or visual inspection suggests that the HTML deck contains mostly titles / outline / empty slides:

1. Do not claim final success.
2. Rebuild the `deck_schema` with the density requirements in Sections 0 and 4.
3. Prefer `content_bullets`, `challenge_cards`, `two_column`, `process`, and `summary` slides with concrete body text.
4. Retry generation once.

### 12.3 Screenshot / visual export failure

If the visual route fails because Playwright, Chromium, or fonts are missing:

- do not claim PPTX generation succeeded;
- return the HTML deck path if available;
- explain that real browser screenshot export is not ready;
- include the install hint returned by the tool.

Do not use fallback screenshots as a final visual PPTX.

### 12.4 Download link missing

If the tool produced a file path but no download URL:

- return the file path;
- do not invent a download URL;
- do not modify web download logic.

## 13. Final response format

When successful:

```text
已生成 PPTX。

文件：<filename>
页数：<slide_count>
下载：<download_url or file_path>
预览：<preview_url or index_path>
QA：<passed / warnings>

说明：visual_pptx 为图片型 PPTX，视觉效果优先，不保证每个元素可编辑。
```

When failed:

```text
PPTX 暂未成功生成。

已完成：
- HTML deck: <path if available>
- QA: <status>

失败原因：
- <error_message>

建议：
- <install_hint or next step>
```

## 14. Strong constraints

- Do not return only a slide outline when the user asked to generate PPTX.
- Do not expose raw schema as the final answer unless debugging is requested.
- Do not invent download URLs.
- Do not change web download link logic.
- Do not use fallback screenshots as final visual PPTX.
- Do not claim image-based PPTX is fully editable.
- Do not overfill slides with long text.
- Do not create title-only body slides.
- Do not use placeholder content.
- Prefer one-shot generation tools for normal user requests.
