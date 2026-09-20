# Step 08 · 规范符合性审计：代码与设计文档到底差多少

- **日期**：2026-09-19
- **审计对象**：`src/leap/**` vs `（作者维护的框架设计文档，不在本仓库）`（42 节）
- **方法**：机械比对（可解析的清单）+ 行为核查（清单查不出来的要求）
- **结论**：**P0 交付边界 100% 完成；文档中可机械比对的部分 100% 不差；但仍有 6 处行为性要求未落地，因此不能说"完全不差"。**

---

## 1. 可机械比对的部分：100% 覆盖

新增 `scripts/spec_coverage.py`，直接解析设计文档并与运行时代码比对。

```
[spec_coverage] §22 49/49 | §23 18/18 | §30 19/19
```

| 章节 | 文档定义 | 已实现 | 覆盖率 |
|---|---|---|---|
| §22 MCP 工具契约 | 49 | 49 | **100%** |
| §23 数据库表设计 | 18 | 18 | **100%** |
| §30 默认工程参数 | 19 | 19 | **100%** |

代码比文档**多出**的部分（属工程补充，非偏离）：

- 工具 +5：`check_advance_unit`（干跑校验）、`complete_session`、`list_artifacts`、`resolve_misconception`、`get_teaching_context`（§22.4 定义了但未列在工具表里）
- 表 +2：`request_log`（§19.4 幂等）、`schema_meta`
- 参数 +5：`artifact_root`、`database_path`、`transfer_pass_score`、`bkt.*`、`fsrs.*`

### 1.1 其他逐字段核对

| 项 | 结果 |
|---|---|
| §7.1 `learner_knowledge_state` 12 个字段 | ✅ 12/12 |
| §13.3 `review_items` 10 个字段 | ✅ 10/10 |
| §9 教学策略库 10 条 | ✅ 已种子化 |
| §18.1 事件类型 21 种 | ✅ 21/21 已声明 |

---

## 2. ⚠️ 六处行为性缺口（文档有要求，代码未完全落地）

这些**不在表格里**，所以机械比对查不出来。逐条列出：

### G1 · §35 架构可插拔性 —— 零抽象接口（严重度：中）

§35.1–§35.6 六处都声明"可替换"：

```
§35.1 State Estimation   BKT → Forgetting-aware BKT → PFA → DKT → Bayesian → Hybrid
§35.2 Assessment         Rule → Rubric → LLM → Hybrid → Human-in-the-loop
§35.3 Pedagogical Policy Rule → LLM → Hybrid → Learned
§35.4 Review Scheduler   FSRS → Other Scheduler
§35.5 Storage            SQLite → PostgreSQL → Distributed
§35.6 Artifact Storage   Local → Object Storage → Knowledge Base
```

**实际代码中没有任何 `Protocol` / `ABC` / `abstractmethod`。** `BKTEstimator`、`PolicyEngine`、`ReviewScheduler`、`Database` 全是具体类，替换需要改调用点。

> §10.2 也写了"**LEAP 的 State Estimation 是一个接口层，具体模型可以替换**"——目前只是"代码写得比较集中"，不是真正的接口层。

### G2 · §31 Interleaving —— 配置项是死的（严重度：中）

```yaml
interleaving_enabled: conditional     # config/default.yaml:24
```

```
$ grep -rn "interleaving" src/leap/runtime/
（无输出）
```

**配置项存在，runtime 从不引用。** §31.2 要求的启用条件（`Relevant Knowledge Has Basic Stability` + `Discrimination Between Concepts Is Useful` + `Additional Load Is Acceptable`）没有实现，交错练习不会真的发生。

### G3 · §32 自定义学习模式 —— 无入口（严重度：中）

§32 要求学习者能用自然语言提出"以项目实战为主"/"我要准备考试"/"只学核心内容"，系统在配置层调整：

```
PBL ↑  Project Task ↑  Transfer ↑  Pure Explanation ↓
Assessment Density ↑  Retrieval Practice ↑  Exam-style Items ↑
Scope ↓  Non-core Nodes ↓  Practice Time Optimization ↑
```

并保存为 `Learning Configuration + Pedagogical Policy Overrides`。

**当前没有任何 MCP 工具或字段承接这个能力。** 配置加载器支持程序化覆盖（`load_config(overrides=...)`），但宿主 Agent 无法在会话中提出这类调整。

### G4 · §25 结业报告 —— 缺 3 个小节（严重度：低）

§25 列出 14 个必需小节，`generate_final_report` 覆盖 11 个：

| 小节 | 状态 |
|---|---|
| Learning Goal / Knowledge Coverage / Current Mastery / Misconceptions / Evidence Stage / Retention Evidence / Transfer Performance / Hint Dependency / Confidence Calibration / Review Plan / Next Learning Path | ✅ |
| **Diagnostic Baseline** | ❌ 未单列诊断基线 |
| **Reasoning Quality** | ❌ 无聚合值 |
| **Learning Gain** | ❌ 未计算（需诊断基线 vs 后测） |

### G5 · §26 学习效果评测 —— 指标未计算（严重度：低）

§26.1 列出 9 个核心指标，目前只有 4 个能从已有数据直接读出（Immediate Performance、Delayed Retention、Transfer Performance、Hint Dependency、Confidence Calibration 部分）。

未实现：

- **Time to Target Evidence** —— 达到指定 Evidence Stage 所需时间
- **Attempts to Target Evidence** —— 达到目标证据阶段的尝试次数
- **Misconception Resolution** —— active → resolved 的比例
- **Learning Gain** —— 诊断基线与后测的差值

§26.3 的 A/B 实验基础设施属 P2，不算缺口。

### G6 · §18.1 三种事件只声明、从不发出（严重度：低）

21 种事件全部在 `EVENT_TYPES` 中声明，但实际有 `emit()` 调用点的只有 18 种：

```
policy_evaluated   ❌  evaluate_pedagogical_policy 不落事件（只返回，不记录）
review_started     ❌  只有 review_completed，没有开始事件
transfer_started   ❌  只有 transfer_completed
```

`policy_committed` 有发出，所以决策仍可回放；但 §27.1 要求的"为什么触发 / 当时状态 / 候选动作"链条在 `policy_evaluated` 这一环是断的。

---

## 3. 按设计不交付的部分（**不是**缺口）

| 章节 | 内容 | P0 边界依据 |
|---|---|---|
| §24 Web / Obsidian | 真实 Obsidian 库读写、Web 前端代码 | §36「P0 不交付」明确排除；MCP 只输出规范 |
| §36 P1 | 参考最小 Host Agent 示例代码 | P1 阶段 |
| §36 P2 | HTTP/SSE 传输、认证、多租户、Teacher Dashboard | P2 阶段 |
| §16 多模态 | 实际渲染（公式/图表/模拟） | 由宿主 Agent 承载 |

---

## 4. §36 P0 交付清单：全部完成

### 4.1 P0 必须实现（9 项）

| # | 项 | 状态 |
|---|---|---|
| 1 | LEAP MCP Server（stdio）+ SQLite | ✅ |
| 2 | 完整工具集（49 个） | ✅ |
| 3 | State Guard | ✅ |
| 4 | 内置简化遗忘 BKT（服务端） | ✅ |
| 5 | FSRS（py-fsrs）复习调度 | ✅ |
| 6 | 事件日志 | ✅ |
| 7 | Artifact 存储 | ✅ |
| 8 | 规范模板输出（Web 组件 / Obsidian 目录） | ✅ |
| 9 | Host Agent System-Prompt 文档、架构文档 | ✅ |

### 4.2 P0 核心闭环（12 项）

MCP/Runtime 边界、Goal Specification、Learner Diagnostic、Knowledge Nodes + DAG、Learner Knowledge State、Basic Assessment、Knowledge State Estimation、Dynamic Policy、Progressive Answer Disclosure、Server-side State Guard、Persistence、Event Log —— **12/12 完成**。

### 4.3 顺带：§36 P1 大部分也已实现

| P1 项 | 状态 |
|---|---|
| Multi-dimensional Rubric | ✅ 已实现 |
| Misconception Tracking | ✅ 已实现（权威表 + 缓存同步） |
| Evidence Stages | ✅ 已实现（含回退） |
| Transfer Layer | ✅ 已实现 |
| Retention Scheduler / FSRS | ✅ 已实现 |
| Learning Friction Signals | ✅ 已实现 |
| `get_teaching_context` | ✅ 已实现 |
| Evidence / Grounding | ✅ 已实现 |
| Metacognition / SRL | ⚠️ 部分（`predicted_performance` 字段与校准计算已有，缺采集入口） |
| Obsidian Integration | ➖ P0 只输出规范 |
| Multimodal Artifacts | ➖ P0 只输出规范 |

---

## 5. 直接回答

> **问：整个项目已经完成了吗？和文档已经不差了吗？**

**分三层回答：**

1. **P0 交付边界：已完成。** §36 的 9 项交付物 + 12 项核心闭环全部落地，168 项测试通过，隐私扫描干净。

2. **文档中可机械比对的部分：不差。** §22 工具 49/49、§23 表 18/18、§30 参数 19/19、§7.1 字段 12/12、§13.3 字段 10/10，覆盖率 100%。

3. **但整体不能说"完全不差"。** 文档里还有 **6 处行为性要求**没有落地（G1–G6）。其中 §35 可插拔性、§31 Interleaving、§32 自定义学习模式这三条是**文档明确写了、代码里完全没有**的，不是"实现得简单"，是"没有"。

**建议**：这 6 条按投入产出排序——

| 优先级 | 项 | 说明 |
|---|---|---|
| 高 | G1 可插拔接口 | §35 是架构级承诺，且 §10.2 明确要求 State Estimation 是接口层；改动集中在加 Protocol + 注入点 |
| 高 | G6 补齐 3 种事件 | 改动最小，直接补 `emit()` 调用点 |
| 中 | G4 结业报告 3 小节 | 数据都在库里，纯聚合 |
| 中 | G2 Interleaving | 需要在 Policy 决策链里加一条分支 |
| 中 | G3 Policy Overrides | 需要新增工具 + 会话级配置字段 |
| 低 | G5 评测指标 | §26 属方法论章节，P0/P1 清单均未要求 |

---

## 6. 审计工具

`scripts/spec_coverage.py` 已固化，可随时重跑：

```bash
python scripts/spec_coverage.py --md reports/spec-coverage.md
```

退出码 `0` = 全覆盖 / `1` = 有文档条目未实现。建议接入 CI，防止后续改动悄悄丢掉规范条目。
