# 给 Codex 的中文 Prompt：LazyRAG visual_pptx v4 深度工程改进

你现在接手 LazyRAG 项目的 visual_pptx / html_deck v4 改进任务。我会提供一个新的 delta 压缩包，里面主要修改了视觉系统设计相关代码：`algorithm/chat/html_deck/themes.py`、`algorithm/chat/html_deck/renderer.py`、`algorithm/chat/prompts/agentic.py`、`skills/.curated/visual-pptx-generation/SKILL.md`、`docs/visual_pptx_v3.md`。请先把这个 delta 解压合并到当前最新项目根目录，然后负责把工程链路真正跑通。

本阶段的分工是：视觉模板系统已经由我收敛成一个统一的 Guizang-style visual family，你不要再把它扩展成很多互不相关的模板项目；你的重点是修工程链路，让 HTML 被真实浏览器渲染、截图、封装成 PPTX，并保证中文正常显示。

## 一、当前已知严重问题

用户已经生成过两份 visual PPTX，出现两个明显问题：

1. PPTX 每页都是图片，但图片里的中文变成了“方框”乱码。
2. 虽然代码里定义了多个主题，但实际生成效果几乎一模一样：背景都是黑色，只有字体颜色和左上角横杠颜色有轻微区别，排版也几乎一样。

我检查后判断：这不是 PPTX 图片方案本身的问题，而是工程链路没有真正使用浏览器渲染 HTML。当前截图阶段大概率走了 Pillow fallback，导致 HTML/CSS/SVG/layout 全部没有被真实渲染，最终只是用 Pillow 粗糙画出黑底、标题、横线、bullet。因此：

```text
真实目标流程：HTML slide -> Playwright/Chromium 真实截图 -> PNG -> python-pptx 封装
当前错误流程：HTML slide -> Playwright 不可用 -> Pillow fallback 粗糙画图 -> PNG -> python-pptx 封装
```

Pillow fallback 会造成两个后果：

- 如果系统没有中文字体，Pillow 默认字体或 DejaVuSans 不支持中文，中文就会变成方框。
- fallback 并不渲染 HTML/CSS/SVG，只抽取标题和文本粗略画图，所以所有主题和布局都退化成同一个极简模板。

因此，本阶段最高优先级不是再加主题，而是修复截图链路和 fallback 策略。

## 二、视觉系统代码已经如何调整

新的 delta 已把视觉系统从“很多主题名 + 同一模板换色”改成一个统一的 `Guizang-style visual family`：

- `guizang_ink`
- `guizang_aurora`
- `guizang_paper`
- `guizang_blueprint`
- `guizang_business`
- `guizang_noir`

旧主题名仍然兼容，例如：

- `cyber_blue` -> Guizang aurora 风格
- `dark_tech` -> Guizang ink 风格
- `corporate_blue` -> Guizang blueprint 风格
- `academic_light` -> Guizang paper 风格
- `warm_editorial` -> Guizang paper/warm variant
- `emerald_dark`、`violet_neon`、`midnight_gold`、`light_magazine` 也保留兼容

请注意：这些主题不应该只是换颜色。新主题 token 包含：

```text
background_variant
layout_frame
title_treatment
card_style
ornament
density
```

renderer 应根据这些 token 影响背景纹理、标题处理、卡片样式、布局框架、视觉密度和装饰语言。不要把它重新改回“同一套 CSS 换颜色”。

新的 renderer 也已经把 layout 做成明显不同的页面结构，包括：

- cover_hero：封面 hero，左侧竖线、大标题、轨道装饰
- toc_numbered：杂志式目录，左侧目录面板 + 右侧编号列表
- section_divider：章节海报，大号背景编号
- metric_cards：指标 poster，左侧大指标 + 右侧小指标和结论区
- challenge_cards：风险/挑战卡片网格
- content_bullets：杂志式内容页，左侧标题面板 + 右侧编号内容卡
- two_column：左右对比板，中间 VS/分隔元素
- comparison/table：主题化表格/对比页
- quote：大引用页
- process/timeline：流程/时间线页
- summary：总结 poster
- references：资料来源页

你的任务不是重新设计视觉，而是把这些 HTML 真实渲染出来。

## 三、必须修复的工程链路问题

### 1. Playwright / Chromium 必须真实可用

请检查：

```bash
python -c "import playwright; print('playwright ok')"
python -m playwright install chromium
```

如果当前环境没有 Playwright，请根据项目依赖管理方式添加或提示安装：

```bash
pip install playwright
python -m playwright install chromium
```

如果是 Docker 环境，请检查 Dockerfile / deployment 文档是否需要补充系统依赖。Playwright Chromium 在 Linux 上可能需要额外依赖，请根据实际报错修复。

### 2. 中文字体必须可用

请检查：

```bash
fc-match "Noto Sans CJK SC"
fc-match "Microsoft YaHei"
fc-match "WenQuanYi Zen Hei"
fc-list | grep -i "noto\|wqy\|source han\|cjk" | head
```

如果没有中文字体，需要在服务器或 Dockerfile 中安装，例如 Debian/Ubuntu：

```bash
apt-get update && apt-get install -y fonts-noto-cjk fonts-wqy-zenhei fontconfig
fc-cache -fv
```

不要把“中文方框”当成 PowerPoint 问题。当前 PPTX 是 image-based，每页图片里已经变成方框了，所以必须在 HTML 截图阶段解决字体。

### 3. 禁止 Pillow fallback 冒充真实截图

请重点修改：

```text
algorithm/chat/html_deck/screenshot.py
algorithm/chat/tools/html_deck.py
scripts/debug_html_deck_generation.py
algorithm/chat/html_deck/qa.py
```

当前错误逻辑是：Playwright 不可用时，`render_html_deck_screenshots()` 走 Pillow fallback，然后返回 `success=True`，导致后续继续生成 visual.pptx。这个产品逻辑必须修。

正确逻辑应该是：

```text
Playwright/Chromium 真实截图成功：
    success=True
    fallback_used=False
    is_real_browser_render=True
    can_export_visual_pptx=True
    允许生成 visual.pptx

Pillow fallback 成功：
    success=False 或至少 can_export_visual_pptx=False
    fallback_used=True
    is_real_browser_render=False
    render_quality="debug_fallback"
    只能用于调试预览，不能作为正式 visual_pptx 输出
```

建议返回结构：

```json
{
  "success": false,
  "fallback_used": true,
  "is_real_browser_render": false,
  "can_export_visual_pptx": false,
  "screenshot_paths": [],
  "warnings": ["Playwright unavailable; fallback preview not suitable for visual PPTX export"],
  "install_hint": "python -m playwright install chromium; apt-get install fonts-noto-cjk"
}
```

如果你想保留 fallback，请加一个显式参数：

```text
allow_fallback_preview=True
```

但默认正式工具链必须是：

```text
allow_fallback_preview=False
```

### 4. `--require-screenshots` 必须拒绝 fallback

请修改 `scripts/debug_html_deck_generation.py`。

当前可能只判断：

```python
if args.require_screenshots and not screenshots.get("success"):
    return 2
```

应该改成：

```python
real_screenshot_success = (
    screenshots.get("success")
    and screenshots.get("is_real_browser_render") is True
    and screenshots.get("fallback_used") is not True
    and screenshots.get("can_export_visual_pptx") is True
)

if args.require_screenshots and not real_screenshot_success:
    return 2
```

并且非强制模式下也要打印清楚：

```text
Screenshots: skipped / fallback-preview / real-browser-success
Fallback used: true/false
Can export visual PPTX: true/false
```

### 5. `html_deck_generate_visual_pptx` 必须 gate PPTX 导出

请修改 `algorithm/chat/tools/html_deck.py`。

现在不能只写：

```python
if screenshot_result.get("success"):
    pptx_create_from_html_screenshots(...)
```

应该改成：

```python
can_export = (
    screenshot_result.get("success")
    and screenshot_result.get("can_export_visual_pptx") is True
    and screenshot_result.get("fallback_used") is not True
)

if can_export:
    pptx_create_from_html_screenshots(...)
else:
    return HTML deck artifact + error/warning explaining Playwright/browser/font requirement
```

正式 visual.pptx 只能由真实浏览器截图生成。

### 6. Playwright 截图应截 `.slide-content`，不是整页黑色容器

请检查 `screenshot.py` 中截图实现。推荐：

```python
page = browser.new_page(viewport={"width": 960, "height": 540}, device_scale_factor=2)
page.goto(file_url, wait_until="networkidle")
locator = page.locator(".slide-content")
locator.screenshot(path=out_path)
```

或者 viewport 精确等于 slide 尺寸，并确保 body 中没有额外边框。优先截 `.slide-content`，避免截到外部黑色背景或缩放后的空白区域。

如果 HTML 中有 `scaleSlide()`，在截图时可能会根据窗口缩放，导致截图尺寸不稳定。可以考虑在截图模式下禁用缩放，或者用 query 参数/环境变量让 HTML 不执行 scale。最简单策略是：viewport 设为 960×540，`.slide-content` 本身就是 960×540，直接 locator screenshot。

### 7. QA 应检查真实截图与 fallback

请增强 `algorithm/chat/html_deck/qa.py`：

如果 `screenshot_result.fallback_used=True`，要 warning 或 issue：

```text
fallback_screenshot_used: Pillow fallback is not acceptable for visual_pptx export
```

如果 `can_export_visual_pptx=False`，不要让 QA 显示为完全通过正式导出。可以区分：

```json
"html_passed": true,
"export_ready": false
```

HTML deck QA 通过，不等于 visual_pptx export ready。

## 四、必须保持的视觉约束

请不要把新代码改回“很多主题名字但同一排版”的方式。你可以修 bug，但不要破坏以下原则：

1. 视觉主参考是 Guizang-style，一套统一设计语言。
2. 旧主题名只做兼容入口，最终应映射到统一视觉家族。
3. 主题差异不只是颜色差异，还应体现在：
   - background_variant
   - layout_frame
   - title_treatment
   - card_style
   - ornament
   - density
4. 不要继续混入多个风格不一致的仓库模板。
5. `html2ppt` 类项目只作为导出技术参考，不作为视觉模板参考。
6. `visual_pptx` 是 image-based PPTX，不要声称完全可编辑。
7. 如果用户强调可编辑，继续走原有 `editable_pptx` 路线。

## 五、必须运行的验收命令

请实际运行，不要只声称完成。

### 1. 语法检查

```bash
python -m compileall algorithm/chat/html_deck algorithm/chat/tools/html_deck.py scripts/debug_html_deck_generation.py
```

### 2. 单元测试

```bash
PYTHONPATH=algorithm pytest tests/test_html_deck_generation.py -q
```

### 3. HTML deck 非强制模式

```bash
PYTHONPATH=algorithm python scripts/debug_html_deck_generation.py --theme auto
PYTHONPATH=algorithm python scripts/debug_html_deck_generation.py --theme guizang_ink
PYTHONPATH=algorithm python scripts/debug_html_deck_generation.py --theme guizang_aurora
PYTHONPATH=algorithm python scripts/debug_html_deck_generation.py --theme guizang_paper
PYTHONPATH=algorithm python scripts/debug_html_deck_generation.py --theme guizang_blueprint
```

这些命令至少必须生成 HTML deck 和 index.html，并通过 HTML QA。

### 4. 强制真实截图模式

先安装 Chromium：

```bash
python -m playwright install chromium
```

然后运行：

```bash
PYTHONPATH=algorithm python scripts/debug_html_deck_generation.py --theme auto --require-screenshots
```

最高验收标准：必须生成真实 visual.pptx，并且日志中明确显示：

```text
Fallback used: false
Real browser render: true
Can export visual PPTX: true
Visual PPTX created: ...
```

如果因为服务器网络/权限无法安装 Chromium，请明确说明：

- 你运行了什么命令；
- 失败原因是什么；
- 当前能跑通到哪一步；
- 用户应该如何在服务器/Docker 中修复。

## 六、最终交付要求

完成后请返回：

1. 修改/新增文件列表。
2. 工程链路修复说明，尤其是 Playwright、字体、fallback gating。
3. 实际运行过的命令和输出摘要。
4. 生成的 HTML deck 目录。
5. index.html 路径。
6. screenshots 路径。
7. visual.pptx 路径。
8. QA 结果摘要。
9. 是否使用 fallback；如果使用，为什么；是否禁止其作为正式 PPTX 导出。
10. 多主题/多变体测试结果，至少说明 auto、guizang_ink、guizang_aurora、guizang_paper、guizang_blueprint 是否可生成不同 HTML。
11. 如果 Playwright/Chromium/中文字体仍不可用，请给出明确环境修复命令。

## 七、强约束

1. 不要破坏已有 editable_pptx 路线。
2. 不要把 Pillow fallback 生成的 PNG 当作正式 visual_pptx 输出。
3. 不要继续输出中文方框的 PPTX。
4. 不要依赖外部 CDN。
5. 不要依赖文生图模型。
6. 不要把生成的 demo HTML/PNG/PPTX 提交到代码目录。
7. 不要把 visual_pptx 说成完全可编辑 PPTX。
8. 不要重新引入多个风格杂糅的模板体系。
9. 不要只做理论分析，必须实际改代码并运行自检。
