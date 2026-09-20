# LEAP 教学页面示例

**语言 / Language**：**简体中文** ｜ [English](README.md)

五个单文件教学页面，由宿主 Agent 依据工程侧任务书产出。它们是宿主 Agent 生成页面时，在结构、组件、交互与视觉上的参考标准。

> 视觉设计规范由项目作者另行维护，**不在本仓库**；本目录下的每个页面都遵循该规范。

## 目录结构

```
examples/
├── README.md                     # 英文说明
├── README_CN.md                  # 本文件（中文）
├── _shared/
│   ├── leap-web-spec.md          # 结构规范（结构层的权威版）
│   ├── leap-bridge.md            # 页面 ↔ 运行时接口
│   ├── interaction-output.schema.json
│   └── design-references/        # 四张视觉参考图
├── 01-python-recursion/          # 编程
├── 02-math-linear-equation/      # 数学
├── 03-cs-osi-model/              # 计算机基础
├── 04-physics-free-fall/         # 物理
└── 05-logic-flowchart/           # 逻辑
```

`leap-web-spec.md` 规定"必须有哪三段、JSON 必须有哪些字段"；视觉规范规定"这三段长什么样"。

## 命名与存放

每个示例是**一个单文件 HTML**，文件名与位置固定：

| # | 学科 | 文件名 | 目录 |
|---|---|---|---|
| 1 | 编程 —— Python 递归 | `leap-01-python-recursion.html` | `01-python-recursion/` |
| 2 | 数学 —— 一元一次方程 | `leap-02-math-linear-equation.html` | `02-math-linear-equation/` |
| 3 | 计算机基础 —— OSI 模型 | `leap-03-cs-osi-model.html` | `03-cs-osi-model/` |
| 4 | 物理 —— 自由落体 | `leap-04-physics-free-fall.html` | `04-physics-free-fall/` |
| 5 | 逻辑 —— 流程图 | `leap-05-logic-flowchart.html` | `05-logic-flowchart/` |

生成方分段输出时，请把各段**按顺序拼接完整**后再保存为上述文件名；不要留下碎片文件。

## 自动化验收

不要靠肉眼逐条比对，先跑这些：

```bash
# 1) 静态规范符合性
python scripts/verify_example.py --all

# 2) 运行时行为（headless Chromium 真实执行 + JSON Schema 权威校验）
python scripts/verify_example_runtime.py --all

# 3) 隐私扫描（本目录也会被扫）
python scripts/security_scan.py --root .

# 4) 宿主桥接完整性
python scripts/apply_leap_bridge.py --check
```

- `verify_example.py` 覆盖：结构、契约、设计令牌、反模式、学科组件、宿主桥接，以及
  **DOM 引用完整性**（改了元素 id 却没同步脚本引用，这类问题只在运行时才暴露）。
- `verify_example_runtime.py` 覆盖只有真跑起来才能验的部分：`getInteractionResult()`
  是否可调用、返回值是否通过 schema 校验、`events` 是否只增不减、`created_at` 是否 Unix 秒、
  375/1280px 是否横向溢出，以及桥接是否真的通。
- **静态通过 ≠ 运行时可用。两个都要跑。**

若某个示例缺少宿主桥接，或页面被重新生成后桥接被弄丢了一部分：

```bash
python scripts/apply_leap_bridge.py --all       # 注入（幂等）
python scripts/apply_leap_bridge.py --repair    # 补齐被弄丢的部分
python scripts/apply_leap_bridge.py --check     # 检查完整性（不只是有没有）
```

`verify_example_runtime.py` 需要 `playwright` 与 Chromium，可用 `--chromium <path>` 指定；
加 `--screenshots <dir>` 可导出整页截图，便于人工复核视觉层。

## 验收清单

- [ ] 单文件、零外部 CDN / 零网络请求 / 零外部图片，双击可直接运行
- [ ] 三段式结构齐全：教学内容区 + 交互练习区 + Agent 数据输出区
- [ ] 输出区 `id="leap-interaction-output"`，且存在 `window.LEAP.getInteractionResult()`
- [ ] JSON 结构完全符合 `_shared/interaction-output.schema.json`，字段名未改动
- [ ] **宿主桥接齐备**：`LEAP.hydrate()` 可注入、`LEAP.drainOutbox()` 可出队
- [ ] **每次交互都产生对应 MCP 调用**，且 `commit_assessment` 带非空 `raw_answer`
- [ ] **页面不自行推算 `mastery_probability`**，也不把它放进调用入参
- [ ] 三级渐进提示可用，使用后正确记录 `hint_level`（0/1/2/3/4）
- [ ] 反馈区分 `answer_error` / `reasoning_error` / `misconception`
- [ ] 支持部分正确（不只有对 / 错两态）
- [ ] 公式使用原生 MathML 或 SVG（**不得**出现 KaTeX / MathJax）
- [ ] 图形全部为内联 SVG / Canvas（无外部图片）
- [ ] 本学科要求的交互组件全部实现
- [ ] 桌面 1280px 与移动 375px 下布局不错位

### 视觉层验收

- [ ] `:root` 令牌块完整，全文无裸 hex、无表外间距值
- [ ] 顶栏常驻"学习进度脊柱"（证据阶段五段轨 + 掌握度 + 下次复习）
- [ ] 三个 Zone 使用 ZoneHeader 五件套分隔（微标签 / 标题 / 目标句 / 元信息 / hairline）
- [ ] 提示阶梯为**底部对齐、高度递增**的阶梯图元，非三个并排按钮
- [ ] 提示第 4 级需二次确认，展示后强制后置验证
- [ ] 反馈面板为三段式（你做对的部分 → 卡在哪里 → 下一步），色条随 `error_type` 变化
- [ ] 证据轨随每次交互新增事件点
- [ ] Agent 输出区为折叠状态条 + 可展开记录仪（**非黑底裸 `<pre>`**）
- [ ] 无渐变、无玻璃拟态、无 emoji 图标

## 与框架设计的关系

| 本目录内容 | 对应框架概念 |
|---|---|
| 渐进式答案揭示（3 级） | 渐进式答案披露 |
| 多维度反馈与错误类型 | 多维评估、部分得分 |
| JSON 输出契约字段 | MCP 工具契约、数据模型 |
| 交互事件类型 | 核心事件 |
| 页面即"教学主交互载体" | Web：交互学习层 |
