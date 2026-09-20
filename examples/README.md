# LEAP‑V2 前端示例库（examples/）

**语言 / Language**：**简体中文** ｜ [English](README.en.md)

本目录用于存放 LEAP‑V2 的**分学科前端教学网页示例**，作为后续宿主 Agent 生成网页时的结构、组件、交互与视觉参考标准。

> 生成方：Gemini 网页版，按 `../（内部示例任务书，不在本仓库）` 执行。
>
> 本目录由工程侧预先建好，**只负责收文件**，示例 HTML 由 Gemini 产出后手动保存进来。

## 目录结构

```text
examples/
├── README.md                       # 本文件：命名规范 + 存放规则 + 验收清单
├── _shared/
│   ├── leap-web-spec.md            # LEAP 网页规范总纲（结构层，权威版）
│   ├── leap-bridge.md              # 宿主桥接契约（输入注入 + MCP 调用出队）
│   ├── interaction-output.schema.json  # Agent 数据输出契约（机器可读）
│   └── design-references/          # 视觉参考图（4 张，Gemini 必读）
│       ├── 01-design-tokens.png    # 色彩 / 提示阶梯 / 证据阶段 / 字阶
│       ├── 02-teaching-zone.png    # 进度脊柱 + 教学内容区 + 理解检查
│       ├── 03-practice-zone.png    # Stage + 提示阶梯 + 反馈 + 证据轨 + 输出
│       └── 04-mobile-390.png       # 390px 移动端版式
├── 01-python-recursion/            # 示例 1：编程类
├── 02-math-linear-equation/        # 示例 2：数学类
├── 03-cs-osi-model/                # 示例 3：计算机基础
├── 04-physics-free-fall/           # 示例 4：物理类
└── 05-logic-flowchart/             # 示例 5：逻辑类
```

> **视觉规范不在本仓库**：（作者另行维护的视觉规范，不在本仓库）。
> `leap-web-spec.md` 管"必须有哪三段、JSON 必须有哪些字段"；视觉规范管"这三段长什么样"，示例必须遵守。

## 文件命名与存放规则

每个示例产出 **1 个单文件 HTML**，命名与存放位置如下（文件名不得随意更改）：

| 示例 | 学科 | 文件名 | 存放目录 |
|---|---|---|---|
| 1 | 编程（Python 递归） | `leap-01-python-recursion.html` | `01-python-recursion/` |
| 2 | 数学（一元一次方程） | `leap-02-math-linear-equation.html` | `02-math-linear-equation/` |
| 3 | 计算机基础（OSI 七层） | `leap-03-cs-osi-model.html` | `03-cs-osi-model/` |
| 4 | 物理（自由落体） | `leap-04-physics-free-fall.html` | `04-physics-free-fall/` |
| 5 | 逻辑（流程图基础） | `leap-05-logic-flowchart.html` | `05-logic-flowchart/` |

> Gemini 分段输出时，请把各段**按顺序拼接完整**后再保存为上述文件名；不要保存成多个碎片文件。

## 硬性验收清单

每个示例入库前逐条核对，**全部通过才算合格**：

- [ ] 单文件、零外部 CDN / 零网络请求 / 零外部图片，双击可直接运行
- [ ] 三段式结构齐全：教学内容区 + 交互练习区 + Agent 数据输出区
- [ ] 输出区 `id="leap-interaction-output"`，且存在 `window.LEAP.getInteractionResult()`
- [ ] JSON 结构完全符合 `_shared/interaction-output.schema.json`，字段名未改动
- [ ] **宿主桥接齐备**：`LEAP.hydrate()` 可注入、`LEAP.drainOutbox()` 可出队（见 `_shared/leap-bridge.md`）
- [ ] **每次交互都产生对应 MCP 调用**，`commit_assessment` 带非空 `raw_answer`
- [ ] **页面不自行推算 `mastery_probability`**，也不把它放进调用入参
- [ ] 三级渐进提示可用，使用后正确记录 `hint_level`（0/1/2/3/4）
- [ ] 反馈区分 `answer_error` / `reasoning_error` / `misconception`
- [ ] 支持部分正确（不只有对 / 错两态）
- [ ] 公式使用原生 MathML 或 SVG（**不得**出现 KaTeX / MathJax）
- [ ] 图形全部为内联 SVG / Canvas（无外部图片）
- [ ] 本学科要求的交互组件全部实现
- [ ] 桌面 1280px 与移动 375px 下布局不错位

### 视觉层验收（对照 `../（作者维护的视觉规范，不在本仓库）` §8 逐条核对）

- [ ] `:root` 令牌块完整粘贴，全文无裸 hex、无表外间距值
- [ ] 顶栏常驻"学习进度脊柱"（证据阶段五段轨 + 掌握度 + 下次复习）
- [ ] 三个 Zone 使用 ZoneHeader 五件套分隔（微标签 / 标题 / 目标句 / 元信息 / hairline）
- [ ] 提示阶梯为**底部对齐、高度递增**的阶梯图元，非三个并排按钮
- [ ] 提示第 4 级需二次确认，展示后强制后置验证
- [ ] 反馈面板为三段式（你做对的部分 → 卡在哪里 → 下一步），色条随 `error_type` 变化
- [ ] 证据轨随每次交互新增事件点
- [ ] Agent 输出区为折叠状态条 + 可展开记录仪（**非黑底裸 `<pre>`**）
- [ ] 无渐变、无玻璃拟态、无 emoji 图标

## 自动化验收（推荐先跑这个，再人工核对）

上面的清单已固化为可执行检查，**不要靠肉眼逐条比对**：

```bash
# 1) 静态规范符合性（65 项，零依赖）
python scripts/verify_example.py --all

# 2) 运行时行为（headless Chromium 真实执行 + JSON Schema 权威校验）
python scripts/verify_example_runtime.py --all

# 3) 隐私扫描（本目录也会被扫）
python scripts/security_scan.py --root .
```

- `verify_example.py` 覆盖清单里的**结构 / 契约 / 视觉令牌 / 反模式 / 学科组件 / 宿主桥接 / DOM 引用完整性**，退出码非 0 即不合格。
- `verify_example_runtime.py` 覆盖清单里**只有真跑起来才能验的部分**：`getInteractionResult()` 是否可调用、返回值是否通过 `interaction-output.schema.json` 校验、`events` 是否只增不减、`created_at` 是否 Unix 秒、375/1280px 是否横向溢出，以及**宿主桥接是否真的通**（`hydrate()` 注入是否生效、作答是否产生 `submit_attempt`、`commit_assessment` 是否带 `raw_answer`、是否偷偷提交了 `mastery_probability`）。
- 静态检查通过 ≠ 运行时可用；**两个都要跑**。

若某个示例缺少宿主桥接，或页面被重新生成后桥接被弄丢了一部分：

```bash
python scripts/apply_leap_bridge.py --all       # 注入（幂等）
python scripts/apply_leap_bridge.py --repair    # 补齐被重新生成弄丢的部分
python scripts/apply_leap_bridge.py --check     # 检查完整性（不只是有没有）
```

`verify_example_runtime.py` 需要 `playwright` 与一个 Chromium。若浏览器不在默认缓存路径，用 `--chromium <path>` 指定。
加 `--screenshots <dir>` 可导出全页截图，便于人工复核视觉层。

## 与 LEAP‑V2 文档的对应关系

| 本目录内容 | 对应 LEAP‑V2 文档章节 |
|---|---|
| 渐进式答案揭示（3 级） | §12 Progressive Answer Disclosure |
| 多维度反馈与错误类型 | §10.3 多维 Assessment、§10.4 Partial Credit |
| JSON 输出契约字段 | §22 MCP Tool Contract、§23 数据库设计 |
| 交互事件类型 | §18.1 核心事件 |
| 页面即"教学主交互载体" | §24.1 Web：交互学习层 |

## 备注

- 本目录**不包含** Web 前端框架代码、不包含 Obsidian 读写代码；按 LEAP‑V2 §36 的 P0 边界，MCP Runtime 只输出规范，页面文件由宿主 Agent（或本目录的示例）承载。
- 若后续要新增学科示例，请在 `_shared/leap-web-spec.md` 中先补充该学科规范，再新增对应子目录与命名条目。
