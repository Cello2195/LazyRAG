# Codex Prompt: PPTX Skill 接入与主流程稳定性改进

你现在接手 LazyRAG 项目的 PPTX generation skill 接入与主流程稳定性改进任务。

这次不要改 visual template 设计，不要重构 web 下载逻辑，不要改前端下载按钮，不要改 artifact_save 的 URL 生成方式。当前 web 端下载链接逻辑比较脆弱，但已经有可用实现，必须保护。

本次只做以下主流程相关改动：

1. 新增或替换 PPTX 生成专用 skill：
   `skills/.curated/visual-pptx-generation/SKILL.md`

2. 让 Agent 在用户要求生成 PPT/PPTX/slides/deck 时能稳定使用该 skill。

3. 确保 Agent 不只是返回大纲，而是构造 deck_schema 并调用生成工具。

4. 优先调用 one-shot 工具：
   `html_deck_generate_visual_pptx`

5. 如果 one-shot 工具不可用，再使用低层工具链：
   `html_deck_create_from_schema → html_deck_qa → html_deck_render_screenshots → pptx_create_from_html_screenshots → artifact_save`

6. 保护现在已有的 web 下载链接逻辑。不要改这些内容，除非只是读取返回值：
   - static-files route
   - signed URL route
   - artifact_save download_url 生成
   - 前端下载按钮
   - web 端文件访问逻辑
   - 现有 file_path / download_url 返回结构

最高优先级是让 LazyRAG 在真实用户请求下能稳定生成 PPTX，而不是只让 `scripts/debug_html_deck_generation.py` 通过。

## 一、需要新增/更新的 skill

请将压缩包中的文件写入：

`skills/.curated/visual-pptx-generation/SKILL.md`

## 二、检查 Agent 是否能检索到该 skill

请检查当前项目的 skill 管理逻辑，例如：

- `algorithm/chat/tools/skill_manager.py`
- `skills/.curated/`
- `algorithm/chat/prompts/agentic.py`
- `algorithm/chat/components/agentic/config.py`

确保当用户请求包含以下关键词时，Agent 有较高概率命中 PPTX generation skill：

- PPT
- PPTX
- PowerPoint
- slides
- deck
- 幻灯片
- 演示文稿
- 生成汇报
- 做一个报告
- MiniMax 风格
- guizang 风格
- 视觉化 PPT
- 科技感 PPT

如果当前 skill retrieval 不稳定，请只做轻量增强，不要重构整套 skill 系统。

可以在 prompt 中补充：

当用户要求生成 PPTX 时，必须使用 visual-pptx-generation skill，并调用 PPTX 生成工具生成 artifact，不要只返回大纲。

## 三、工具入口必须支持 schema 容错

请检查：

- `algorithm/chat/tools/html_deck.py`
- `algorithm/chat/html_deck/schema.py`

重点修复 deck_schema 输入类型问题。

工具入口必须支持：

1. dict
2. JSON string
3. double-encoded JSON string
4. 被 markdown code fence 包裹的 JSON string

请新增一个公共函数，例如：

`parse_deck_schema_input(value)`

要求：

- 如果输入是 dict，直接返回。
- 如果输入是 str，先去掉 markdown fence。
- 尝试 json.loads。
- 如果解析结果仍然是 str，继续 json.loads，最多 3 层。
- 最终必须得到 dict。
- 如果最终不是 dict，返回结构化错误。
- 如果 slides 不是 list，返回结构化错误。
- 不允许把整个 JSON 当作一页正文继续生成。

请为这个函数增加测试。

## 四、one-shot 工具优先

请检查是否已有：

`html_deck_generate_visual_pptx`

如果已有，请确保它是 Agent 正常生成 visual PPTX 的默认工具。

该工具应该接受：

```json
{
  "deck_schema": {...},
  "filename": "...",
  "output_dir": "...",
  "require_screenshots": false
}
```

或者兼容当前项目已有参数。

这个工具内部应完成：

```text
normalize_visual_deck_schema
→ validate_visual_deck_schema
→ html_deck_create_from_schema
→ html_deck_qa
→ html_deck_render_screenshots
→ 如果是真实浏览器截图，生成 visual.pptx
→ artifact_save 或复用当前已有保存逻辑
→ 返回 artifacts
```

注意：不要改 artifact_save 的下载链接逻辑。只使用它返回的 download_url / file_path。

## 五、失败策略

请防止 Agent 反复乱试工具。

如果 one-shot 工具返回：

- schema parse failed
- slides is not list
- slide_count mismatch
- export_ready=false
- can_export_visual_pptx=false

Agent 不应该继续无意义重试。

最多允许：

1. schema 格式问题：重建 schema 后重试一次。
2. Playwright / Chromium / 字体问题：停止，返回 HTML deck 路径和安装提示。
3. 下载链接缺失：返回 file_path，不要伪造 URL。

## 六、最终回答格式

请检查最终 assistant answer 的 prompt 或 formatter，确保生成 PPTX 成功时，尽量输出：

```text
已生成 PPTX。

文件：xxx.pptx
页数：N
下载：<download_url or file_path>
预览：<preview_url or index_path>
QA：通过 / 有 warning

说明：visual_pptx 是图片型 PPTX，视觉效果优先，不保证每个元素可编辑。
```

失败时输出：

```text
PPTX 暂未成功生成。

已完成：
- HTML deck: xxx
- QA: xxx

失败原因：
- xxx

建议：
- xxx
```

不要把原始 deck_schema 当作最终答案返回，除非用户明确要求调试。

## 七、不要改 web 下载链接逻辑

强约束：

1. 不要修改 static file route。
2. 不要修改 signed URL route。
3. 不要修改 artifact_save 的 download_url 生成策略。
4. 不要修改前端 download button。
5. 不要手动拼接 download_url。
6. 不要替换已有 artifact 保存目录结构。
7. 如果需要返回下载信息，只读取现有工具返回的 download_url / file_path。
8. 如果没有 download_url，就返回 file_path，不要伪造链接。

这部分代码经常出错，必须保护。

## 八、测试要求

请新增或增强测试：

1. skill 文件存在测试：
   - `skills/.curated/visual-pptx-generation/SKILL.md` 存在
   - 内容包含 route decision / deck_schema / final response / download link protection

2. schema parser 测试：
   - dict 输入
   - JSON string 输入
   - double-encoded JSON string 输入
   - markdown fenced JSON 输入
   - slides 不是 list 时失败

3. one-shot 工具测试：
   - 传入 6 页 schema，生成 slide_count == 6
   - 如果 screenshots 不可用，不生成正式 visual.pptx，但返回 HTML deck 和明确 warning
   - 如果 screenshots 可用，生成 visual.pptx

4. Agent prompt 测试，至少用静态检查：
   - 用户请求 PPTX 时 prompt 中要求调用工具生成 artifact
   - prompt 中明确禁止只返回大纲

## 九、实际运行命令

请运行：

```bash
python -m compileall algorithm/chat/html_deck algorithm/chat/tools/html_deck.py algorithm/chat/prompts/agentic.py
PYTHONPATH=algorithm pytest tests/test_html_deck_generation.py -q
```

如果新增了测试文件，例如：

```bash
PYTHONPATH=algorithm pytest tests/test_visual_pptx_skill.py -q
```

再运行 debug：

```bash
PYTHONPATH=algorithm python scripts/debug_html_deck_generation.py --theme auto
```

如果当前环境支持 Playwright：

```bash
PYTHONPATH=algorithm python scripts/debug_html_deck_generation.py --theme auto --require-screenshots
```

## 十、最终交付

请返回：

1. 修改文件列表。
2. skill 接入说明。
3. deck_schema 容错解析说明。
4. one-shot 工具调用路径说明。
5. 你实际运行的命令和结果。
6. 是否触碰了 web 下载链接逻辑。这里必须明确说明：
   - 未修改 static route
   - 未修改 signed URL route
   - 未修改前端下载按钮
   - 未修改 artifact_save 的 download_url 生成策略
7. 如果 visual_pptx 因 Playwright/字体问题无法生成正式 PPTX，说明当前能跑到哪一步。
8. 下一步建议，但不要在本轮实现低优先级功能。

## 十一、本轮不要做的事情

不要做以下低优先级功能：

- dual-layer PPTX
- HTML 元素级转 PPTX
- 文生图背景
- 视觉模型 QA
- 大规模新增主题
- 重构 web 下载系统
- 重构整个 skill manager
- 重构前端

本轮只做主流程稳定性：

```text
用户请求
→ skill 命中
→ deck_schema 正确生成
→ one-shot 工具调用
→ 使用现有下载链接返回 artifact
```
