---
name: outline-longform-generation
description: Generate long-form reports, surveys, technical analyses, and structured essays through outline-first planning, node-level evidence retrieval, section writing, critique, and downloadable artifact output.
---

# Outline LongForm Generation

## 1. 什么时候触发

当用户请求详细调研、综述、长报告、技术方案、研究现状、论文总结、长文写作等任务时触发。

如果用户明确要求“简短回答/只要命令/不用长文”，不要触发。

## 2. 不要用于 PPTX

如果请求是 PPT/PPTX/PowerPoint/slides/deck/幻灯片/演示文稿，请优先走 `visual-pptx-generation` 或 `pptx-generation`，不要把 PPTX 请求转成长文流程。

## 3. Outline-first 流程

固定流程：

1. 解析任务 schema（language、genre、citation policy、output format）。
2. 先生成结构化大纲，再执行工具调用。
3. 对每个大纲节点执行证据检索与证据卡归一化。
4. 按节点分节写作，不一次性输出全文。
5. 对每节做规则审校，必要时最多修复一次。
6. 做全局格式化与一致性修订。
7. 保存 artifact 并返回下载链接。

## 4. Hard Controls

- 不得跳过大纲阶段。
- 不得编造 KB 引用 `[[n]]`。
- `citation_required=true` 时，事实性结论需证据支撑；证据不足要明确说明。
- 每节必须有实质正文，禁止空章节和占位符（`TBD/待补充/N/A/示例内容`）。

## 5. Soft Controls

- 保持术语一致、减少跨节重复。
- 章节粒度均衡，优先段落叙述，少量列表用于总结。
- 面向目标受众调整语气（technical/academic/formal/concise）。

## 6. Tool Policy

- 默认 KB 优先：`kb_search`。
- 需要上下文补全时可用 `kb_get_parent_node` / `kb_get_window_nodes` / `kb_keyword_search`。
- 公开研究或论文主题可补充 `arxiv_search`、`web_search`、`url_fetch`。
- 每个节点控制证据卡数量，避免上下文过载。

## 7. Citation Policy

- KB 证据使用工具返回的原始 `ref`（如 `[[1]]`）。
- 不可自行伪造 `[[n]]`。
- Web/arXiv 若无 `[[n]]`，使用标题或 URL 标注来源。

## 8. Final Output Format

最终文本应包含：

- `# 标题`
- `> 核心结论`
- 多个 `##` / `###` 章节
- 可执行建议、风险与测试建议

不要只输出“以下是大纲”。

## 9. Artifact / Download Policy

- 复用现有 artifact 保存逻辑，返回 signed URL 字段。
- 用户回复中优先使用 `download_link`，其次 `download_url`。
- 不要把 `relative_path/local_path/file_path` 当作 Web 下载地址。

## 10. Failure Handling

- LLM JSON 解析失败时先尝试一次 repair，再回退规则型大纲。
- 单节最多修复一次，全局最多修复一次。
- 出现证据不足时记录 warning 并保留可读输出，不能让服务崩溃。
