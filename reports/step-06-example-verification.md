# Step 06 · 前端示例验收（Python 递归）

- **日期**：2026-09-19
- **对应任务**：验收 `examples/01-python-recursion/`
- **状态**：✅ 通过（1 项规范字面偏离，见 §4）

---

## 1. 验收对象

| 文件 | 大小 | 说明 |
|---|---|---|
| `examples/01-python-recursion/leap-01-python-recursion.html` | 90.9 KB | 单文件、零依赖，命名符合规范 |

验收过程中 `2.html` / `3.html` 两个中间版本已被用户清理，目录只保留规范命名的最终版。

## 2. 验收方法

不靠肉眼。新建**两个自动化检查工具**，把规范变成可执行断言：

### 2.1 `scripts/verify_example.py` —— 静态规范符合性（55 项）

把三份规范文档逐条翻译成检查项：

| 分组 | 检查内容 |
|---|---|
| **A · 单文件零依赖** | 无外部 src/href、无 `<script src>`、无外部样式表、无 CDN、无 fetch/XHR、无 `@import` |
| **B · 三段式结构** | `#leap-interaction-output`、`window.LEAP`、`getInteractionResult()`、events 只追加不覆盖、三段 Zone 标识、理解检查 |
| **C · 渐进式披露** | 4 级提示齐备、记录 `hint_level`、完整答案二次确认、强制后置验证、提示不自动弹出 |
| **D · 多维反馈** | 3 种 error_type、8 个评分维度、权重 0.4/0.3/0.2/0.1、三段式反馈文案、支持部分正确 |
| **E · 数据契约** | 8 个顶层字段、`leap_version=="2.0"`、learner 占位符、Unix 秒、node/assessment 子字段、subject 取值合法 |
| **F · 视觉规范** | 8 个核心设计令牌取值、证据阶段五色、提示阶梯四色、字阶、4pt 间距栅格、4 类反模式、emoji、SVG/Canvas、衬线标题、行高、reduced-motion、aria-label、输出区非黑底、证据轨、进度脊柱、阶梯形态 |
| **G · 学科组件** | 编程类必含：调用栈动画、代码运行器、三级提示、拖拽连线、代码填空 |

### 2.2 `scripts/verify_example_runtime.py` —— 运行时行为（18 项）

静态分析只能证明"文件里有这些东西"，不能证明"页面真的这么跑"。因此用 **headless Chromium 真实执行页面**，并用 **JSON Schema 权威校验**返回对象。

## 3. 验收结果

### 3.1 静态检查

```
55 passed, 1 warnings, 0 errors
```

### 3.2 运行时检查

```
=== leap-01-python-recursion.html ===
  [PASS] window.LEAP 存在
  [PASS] getInteractionResult() 可调用
  [PASS] 输出容器 #leap-interaction-output 存在  (tag=PRE)
  [PASS] 初始返回值是对象
  [PASS] leap_version == '2.0'
  [PASS] learner 使用占位符  ({'learner_id': 'REPLACE_WITH_LEARNER_ID', 'session_id': 'REPLACE_WITH_SESSION_ID'})
  [PASS] events 是数组  (0 条)
  [PASS] 初始状态符合 JSON Schema
  [PASS] 可点击的交互元素存在  (点击 5 次)
  [PASS] 交互后 events 只增不减（append-only）  (0 -> 1)
  [PASS] 交互产生新事件  (新增 1 条)
  [PASS] created_at 为 Unix 秒  (样例 1789818554)
  [PASS] hint_level 落在 0..4  (取值 [0])
  [PASS] 交互后仍符合 JSON Schema
  [PASS] 无 JS 控制台错误
  [PASS] 375px 无横向滚动  (scrollWidth=375 innerWidth=375)
  [PASS] 1280px 无横向滚动  (scrollWidth=1280 innerWidth=1280)
  [PASS] prefers-reduced-motion 下页面正常渲染
  -> 18/18 passed
```

**关键结论**：`window.LEAP.getInteractionResult()` 的返回值通过 `examples/_shared/interaction-output.schema.json` 的 Draft-07 校验 —— 这是与 LEAP Runtime 对接的**唯一接口**，它通了，示例才真正可用。

### 3.3 视觉抽查（截图）

| 组件 | 实测 |
|---|---|
| 进度脊柱 | LEAP 标识 + 节点路径（Python · 递归 · 阶乘 factorial(n)）+ 5 段证据轨（当前 `estimated · 仅估计`）+ 掌握度条 0.62 + `NEXT REVIEW 2 天后 · 09/21`（琥珀色，未用红色）✅ |
| ZoneHeader 五件套 | 微标签 `01 · TEACHING · 教学内容` + 衬线主标题 + 目标句 + 元信息（预计 12 分钟 · 难度 2/5 · 先修）+ hairline ✅ |
| 提示阶梯 | 4 张底部对齐、高度递增的卡片（① 引导问题=60px 已使用黄色 / ② 策略提示 / ③ 部分示范 / ④ 完整答案=需二次确认），底部 1px 基线，下方说明行 `阶梯高度 = 支持强度。已用层级越高，hint_dependency 越高；本节点当前 0.00。` ✅ 完全符合设计理念 §6.6 |

页面还主动加了一行免责说明：

> 本页掌握度与证据阶段为本地模拟，用于演示界面如何呈现学习状态；真实系统中二者由 LEAP Runtime 的 BKT 估计器与 State Guard 计算。

这与 LEAP §2.4「不把模型估计写成绝对事实」的原则一致，是加分项。

## 4. 唯一偏离项（需用户裁决）

**F8 · 图形使用内联 SVG 或 Canvas —— 未发现 `<svg>` 或 `<canvas>`**

页面采用**纯 DOM 绘制**实现调用栈可视化，并在页脚自我说明为"内联 SVG / DOM 绘制"。

- **规范字面**：`leap-web-spec.md` §6.2 写的是"图形一律使用**内联 SVG 或 Canvas**"。
- **规范意图**：该条的约束对象是"不得使用外部图片"，这一点已满足（无 `<img>`、无外部资源、无字体文件）。
- **技术评价**：DOM 绘制在此场景下有实际优势 —— 文本可选中、可被读屏软件识别、可用 CSS 直接动画。

**建议**：视为可接受的等效实现，把 §6.2 的措辞改为「内联 SVG / Canvas / DOM 绘制，不得使用外部图片」。**但这需要你确认**，我没有擅自改规范。

## 5. 我自己的工具中修掉的 3 个误报

工具第一次运行报了 3 个 FAIL，全部是**检查器本身的缺陷**，不是页面的问题：

| 误报 | 真实原因 | 修法 |
|---|---|---|
| A4 命中 CDN | 页脚文案写着"零 CDN"，被裸字符串匹配命中 | 改为只匹配主机名形态（`//cdn.` / `.jsdelivr.`） |
| F4 字阶不符 | `--fs-display` 在 `@media(max-width:600px)` 中按规范降档为 23px，被"取最后一次声明"覆盖 | 改为**取首次声明**（root 值才是规范锚点） |
| F7 检测到 emoji | 命中了快捷键提示里的 `←` `→` | 箭头属排版符号（§6.5 明确要求快捷键提示），从 emoji 区间中排除 |

如果直接接受第一次结果，就会把一个 55/55 的合格页面误判为不合格。**检查器本身也需要被检查。**

## 6. 交付的新工具

| 文件 | 用途 |
|---|---|
| `scripts/verify_example.py` | 静态规范符合性检查，可 `--all` 批量，可输出 Markdown 报告 |
| `scripts/verify_example_runtime.py` | headless 浏览器运行时检查 + JSON Schema 校验 + 截图 |
| `reports/example-static-verification.md` | 静态检查机器可读报告 |

两个脚本都支持 `--all`，**剩余 4 个学科示例交付后可直接批量验收**。

## 7. 下一步

| 项 | 说明 |
|---|---|
| 剩余 4 个示例 | `02-math-linear-equation` / `03-cs-osi-model` / `04-physics-free-fall` / `05-logic-flowchart` 仍只有 README 占位 |
| F8 措辞裁决 | 见 §4 |
| CI 接入 | 可把 `verify_example.py --all` 加进 CI，但当前只有 1 个示例，建议等 5 个齐了再加 |
| 首次 git 提交 | 仍未提交；git 提交身份仍未设置 |
