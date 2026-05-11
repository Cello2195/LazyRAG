---
name: visual-pptx-generation
description: Generate editable or visual PPTX files from user requests. Use this skill when the user asks to create, generate, export, design, or improve a PowerPoint/PPT/PPTX/deck/slides presentation.
---

# Visual PPTX Generation Skill

This skill controls how LazyRAG converts a user request into a real PPTX artifact.

The goal is not to return a slide outline as text. The goal is to generate a real downloadable file through the available PPTX / HTML-deck tools.

## 1. When to use this skill

Use this skill when the user asks for any of the following:

- 生成 PPT / PPTX / PowerPoint / slides / deck
- 做一个汇报 / 演示文稿 / 讲座幻灯片
- 生成更好看的 PPT
- 生成类似 MiniMax / guizang / 科技感 / 发布会风 / 视觉化 的 PPT
- 把资料、论文、报告、检索结果整理成 PPT
- 输出可下载的 PPTX 文件

Do not only provide a textual outline unless the user explicitly asks only for an outline.

## 2. Decide the generation route

There are two PPTX routes.

### 2.1 editable_pptx route

Use this route when the user emphasizes:

- 可编辑
- 正式办公交付
- 后续还要手动修改
- 论文组会
- 技术报告
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

### 2.2 visual_pptx route

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

## 3. Important output rule

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

## 4. Protect download link logic

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

## 5. Required deck_schema structure

Always build a structured `deck_schema` before calling PPTX tools.

A valid deck schema should look like:

```json
{
  "title": "AI时代下的程序员该何去何从",
  "subtitle": "职业生存指南与进阶策略",
  "language": "zh",
  "audience": "technical",
  "style": "auto",
  "visual_theme": "auto",
  "slides": [
    {
      "type": "cover",
      "title": "AI时代下的程序员该何去何从",
      "subtitle": "职业生存指南与进阶策略"
    },
    {
      "type": "toc",
      "title": "目录",
      "items": [
        "AI浪潮来袭",
        "直面冲击",
        "新的机会",
        "能力重塑",
        "行动建议"
      ]
    },
    {
      "type": "section_divider",
      "title": "01 AI浪潮来袭",
      "subtitle": "行业现状分析"
    },
    {
      "type": "metric_cards",
      "title": "AI正在改变软件开发分工",
      "metrics": [
        {
          "label": "编码效率提升",
          "value": "55%",
          "description": "AI 编程工具提升基础编码速度"
        },
        {
          "label": "工具采用率",
          "value": "84%",
          "description": "开发者已使用或计划使用 AI 工具"
        },
        {
          "label": "岗位结构变化",
          "value": "30%",
          "description": "初级岗位需求承压"
        }
      ],
      "bullets": [
        "变化不是简单淘汰，而是开发范式重组"
      ]
    },
    {
      "type": "challenge_cards",
      "title": "程序员面临的主要挑战",
      "cards": [
        {
          "title": "岗位替代风险",
          "body": "重复性编码和简单 CRUD 工作更容易被自动化工具压缩。",
          "accent": "danger"
        },
        {
          "title": "效率基准提升",
          "body": "团队对交付速度和工具使用能力的要求明显提高。",
          "accent": "primary"
        },
        {
          "title": "技能更新压力",
          "body": "开发者需要从代码实现者转向问题定义者和系统设计者。",
          "accent": "secondary"
        },
        {
          "title": "竞争结构变化",
          "body": "掌握 AI 工具的人才会获得更高生产力杠杆。",
          "accent": "success"
        }
      ]
    },
    {
      "type": "summary",
      "title": "总结",
      "bullets": [
        "AI 不会简单淘汰所有程序员，但会重塑岗位结构。",
        "基础编码能力仍重要，但不再是唯一护城河。",
        "未来竞争力来自系统设计、业务理解、AI 协作和持续学习。"
      ]
    }
  ]
}
```

## 6. Slide type policy

Choose slide types according to content:

| Content need | Preferred slide type |
|---|---|
| Title page | `cover` |
| Agenda | `toc` |
| New chapter | `section_divider` |
| Important statistics | `metric_cards` |
| Risks / challenges / opportunities | `challenge_cards` |
| Normal explanation | `content_bullets` |
| Two perspectives | `two_column` |
| Comparison | `comparison` |
| Data table | `table` |
| Process / roadmap | `process` or `timeline` |
| Quote / key idea | `quote` |
| Final conclusion | `summary` |
| Sources | `references` |

Avoid putting too much content on one slide.

Recommended content limits:

```text
cover: title + subtitle only
toc: 4–7 items
metric_cards: 2–4 metrics
challenge_cards: 3–6 cards
content_bullets: 3–6 bullets
table: max 5 rows × 4 columns when possible
summary: 3–5 takeaways
```

## 7. Theme policy

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

## 8. Evidence and citations

If the PPT is based on retrieved documents, web pages, papers, or KB evidence:

- preserve important source information in `evidence_refs`;
- add a `references` slide when sources are numerous;
- do not invent data;
- do not fabricate statistics;
- if evidence is insufficient, state the limitation.

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

## 9. Failure handling

If a tool fails, do not repeatedly call tools without changing the input.

Use this policy:

### 9.1 Schema parse failure

If the tool reports schema parsing failure:

1. Rebuild a clean `deck_schema`.
2. Ensure `slides` is a list, not a JSON string.
3. Retry once.

If it still fails, stop and return a concise error.

### 9.2 Screenshot / visual export failure

If the visual route fails because Playwright, Chromium, or fonts are missing:

- do not claim PPTX generation succeeded;
- return the HTML deck path if available;
- explain that real browser screenshot export is not ready;
- include the install hint returned by the tool.

Do not use fallback screenshots as a final visual PPTX.

### 9.3 Download link missing

If the tool produced a file path but no download URL:

- return the file path;
- do not invent a download URL;
- do not modify web download logic.

## 10. Final response format

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

## 11. Strong constraints

- Do not return only a slide outline when the user asked to generate PPTX.
- Do not expose raw schema as the final answer unless debugging is requested.
- Do not invent download URLs.
- Do not change web download link logic.
- Do not use fallback screenshots as final visual PPTX.
- Do not claim image-based PPTX is fully editable.
- Do not overfill slides with long text.
- Prefer one-shot generation tools for normal user requests.
