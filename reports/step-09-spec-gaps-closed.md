# Step 09 · 六处规范缺口全部补齐

- **日期**：2026-09-19
- **对应任务**：#6–#11（按 Step 08 审计给出的优先级顺序）
- **状态**：✅ 全部完成

---

## 0. 结果总览

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 测试 | 168 passed | **213 passed** |
| MCP 工具 | 54 | **58** |
| §22/§23/§30 覆盖率 | 100% | 100%（保持） |
| 隐私扫描 | 0/0/0 | 0/0/0 |
| Step 08 缺口 | G1–G6 共 6 项 | **0** |

修复顺序按审计给出的优先级：G1 → G6 → G4 → G2 → G3 → G5。

---

## G1 · §35 架构可插拔性

**原问题**：§35.1–§35.6 六处都声称"可替换"，代码里没有任何 `Protocol` / `ABC`。§10.2 也明说"State Estimation 是一个接口层"。实际只是"代码写得比较集中"。

**修复**：

新增 `src/leap/runtime/contracts.py`，用 `typing.Protocol` 定义六个接缝：

| 协议 | 对应章节 | 语义 |
|---|---|---|
| `MasteryEstimator` | §35.1 | 掌握度估计（BKT → PFA → DKT → Bayesian → Hybrid） |
| `ScoreAggregator` | §35.2 | 多维评分聚合（Rule → Rubric → LLM → Hybrid） |
| `PolicyStrategy` | §35.3 | 教学策略（Rule → LLM → Hybrid → Learned） |
| `ReviewSchedulerBackend` | §35.4 | 复习调度（FSRS → Other） |
| `StorageBackend` | §35.5 | 持久化（SQLite → PostgreSQL → Distributed） |
| `ArtifactStore` | §35.6 | 工件存储（Local → Object → Knowledge Base） |

新增 `src/leap/runtime/plugins.py` 注册表，配置项直接选择实现：

```yaml
mastery_estimator: simplified_bkt   # 35.1
score_aggregator: weighted          # 35.2
policy_engine: rule_based           # 35.3
review_scheduler: py-fsrs           # 35.4
storage_backend: sqlite             # 35.5
artifact_store: local               # 35.6
```

顺带抽出两个新实现：`WeightedScoreAggregator`（§10.3‑1 加权聚合，含自动归一化与 transfer/hint_dependency 排除）、`LocalArtifactStore`。

**验证**：六个内置实现全部 `isinstance` 通过各自协议；测试中注册一个 `ConstantEstimator` 后，只需改配置即被采用，**调用点一行未动**。

---

## G6 · §18.1 三种事件只声明不发出

**原问题**：21 种事件全部在枚举里，但只有 18 种有 `emit()` 调用点。

**修复**：

| 事件 | 补在哪里 |
|---|---|
| `policy_evaluated` | `evaluate_pedagogical_policy` —— 附带**状态快照**（证据阶段 / 掌握度 / 提示依赖 / 推理质量 / 活跃错误概念 / 缺失前置 / 到期复习数 / 摩擦信号），让 §27.1「为什么触发、当时状态是什么」可回放 |
| `review_started` | `submit_review` 应用评分之前 |
| `transfer_started` | `record_transfer_result` 落库之前 |

**验证**：21/21 均有 emit 调用点（由测试从设计文档反向解析事件清单后逐条核对）。

---

## G4 · §25 结业报告缺 3 小节

**原问题**：14 个必需小节只覆盖 11 个。

**修复**：

| 小节 | 实现 |
|---|---|
| **Diagnostic Baseline** | 诊断完成前的评估证据：证据点数、探测过的节点、基线均分、完成时间、关联工件 |
| **Reasoning Quality** | `reasoning_quality` 聚合均值 + 样本数 + 是否低于阈值 |
| **Learning Gain** | 基线均分 vs 后测均分 + 绝对增益 |

**踩到的坑（重要）**：第一次实现用 `created_at <= diagnostic_completed_at` 切分基线，结果把教学阶段的 3 次作答也算进了基线 —— 因为**项目统一用 Unix 秒**，一次教学回合全落在同一秒里，时间戳无法区分先后。

修法：改用事件日志的 `rowid`（追加顺序）定位切分点。这个坑值得记住：**秒级时间戳不能用来做同秒内的先后判断**。

**验证**：基线 1 条 / 后测 3 条切分正确；学习增益 0.62；报告 Markdown 含全部 3 个新小节。

---

## G2 · §31 Interleaving 是死配置

**原问题**：`interleaving_enabled` 在 config 里，但 `grep interleaving src/leap/runtime/` 无输出。

**修复**：新增 `PolicyEngine.interleaving_plan(context)`，严格实现 §31.2 的三个条件：

```
1. 相关知识已有基本稳定性   当前节点证据阶段 ≥ practiced
2. 区分概念本身有价值       同 unit_tag 下 ≥2 个节点达到 practiced+
3. 额外负荷可接受           无摩擦信号 且 hint_dependency ≤ hint_dependency_high
```

三个条件**全部满足**才适用，默认答案是"不适用"并给出原因。决策链中作为规则 #10 插入，产出 `interleaving` 字段（含参与交错的节点列表）供宿主 Agent 使用。

**验证**：条件全满足 → 适用，`trigger_event = interleaving`；只有 1 个节点稳定 → 不适用；`interleaving_enabled: false` → 不适用；`hint_dependency = 0.95` → 不适用；节点无 `unit_tag` → 不适用。

---

## G3 · §32 自定义学习模式无入口

**原问题**：宿主无法提出"我要准备考试"这类调整。

**修复**：

新增 `src/leap/runtime/learning_modes.py`，三个预置模式 + 均衡模式：

| 模式 | 触发词 | 关键覆写 |
|---|---|---|
| `project_based` | 以项目实战为主 / 项目驱动 | 强制迁移验证、`max_retry` 4 |
| `exam_prep` | 我要准备考试 / 备考 | `mastery_threshold` 0.85、`max_hint_level` 2、强制迁移 |
| `core_only` | 只学核心 / 尽快学会 / 速成 | 阈值 0.75、`unit_concept_budget` 5、关闭迁移要求 |
| `balanced` | 默认 / 恢复正常 | 无覆写 |

- 新增会话字段 `learning_mode` + `policy_overrides`（**per-session**，不碰全局配置）
- 新增工具 `set_learning_configuration` / `get_learning_configuration`
- `PolicyEngine` 改为**会话感知**：`_get(key, default, session_id)` 先查会话覆写再查全局
- **覆写键白名单**：只允许 §30 里的参数，越权键被拒绝并回报
- **未识别请求如实回报**，不静默忽略

**诚实性设计**：`overrides` 真正改变引擎行为；`preferences`（偏好策略/动作）只作为宿主 Agent 的呈现建议，**不绕过任何 State Guard 检查** —— 这一点写进了文档字符串和返回值的 note。

**验证**：四种请求正确映射；覆写真实生效（`mastery_threshold` 0.80 → 0.85 → 0.75 → 0.80）；不跨会话泄漏；越权键被拒；全局配置未被改动；模式切换记入事件日志。

**顺带修的坑**：覆写以 `{mode, overrides, preferences, requested}` 结构存库，但读取时按扁平结构查键，导致**覆写静默失效**。已修为自动解包 `overrides` 子映射。

---

## G5 · §26 学习效果评测指标

**原问题**：9 个核心指标一个都没算。

**修复**：新增 `src/leap/runtime/metrics.py` + 工具 `get_learning_metrics`：

| 指标 | 实现 |
|---|---|
| Immediate Performance | 全部 / 最近 3 次评估的 `overall_score` 均值 |
| Delayed Retention | 间隔 ≥ 配置阈值的复习项评分均值（FSRS 1–4 分） |
| Transfer Performance | 迁移得分均值 + 按 near/variation/far/integrated 分型 |
| **Time to Target Evidence** | 每个节点从首次作答到达 `demonstrated` 的秒数 |
| **Attempts to Target Evidence** | 同上路径的有效尝试次数 |
| Hint Dependency | 均值 + 是否超阈值 |
| **Misconception Resolution** | active → resolved 比例 |
| Confidence Calibration | \|预测 − 实际\| 平均误差 |
| Learning Gain | 诊断基线 vs 后测差值 |

Time/Attempts 的实现思路：`assessment_committed` 事件带 `stage_after`，取该节点**首次**达到目标阶段的事件位置，再数它之前的 `attempt_submitted` 事件条数 —— 同样用 `rowid` 而非时间戳。

结业报告的学习增益改为**调用同一个实现**，避免报告与指标工具给出不同数字。

**验证**：9 个指标全部产出；`attempts_to_target_evidence.per_node["n1"] == 3`；迁移均值 0.70；错误概念解决率 0→1；同秒切分正确。

---

## 顺带交付：Schema 迁移机制

G3 给 `learning_sessions` 加了两个字段。但 `CREATE TABLE IF NOT EXISTS` **不会给已存在的表加列** —— 老数据库会静默缺字段。

新增轻量迁移：`ADDED_COLUMNS` 声明 + `Database._migrate()` 用 `PRAGMA table_info` 检测后 `ALTER TABLE`，幂等。测试覆盖了"先用旧结构建库，再 initialize 应自动补列"。

---

## 测试

新增 `tests/test_spec_gaps.py`（**45 项**），按 G1–G6 分组织：

| 组 | 覆盖 |
|---|---|
| G1 | 六协议一致性、注册表解析、**自定义实现热替换**、未知实现名报错、白名单 |
| G2 | 三个条件各自的拒绝路径 + 全满足路径 + 配置关闭 |
| G3 | 自然语言映射、覆写真实生效、会话隔离、越权键拒绝、全局配置不被污染 |
| G4 | 14 小节齐备、基线切分、增益为正、缺基线时报为不确定 |
| G5 | 9 指标齐备、逐节点时间/次数、迁移分型、错误概念解决率、同秒切分 |
| G6 | 从设计文档反向解析事件清单并逐条核对 emit 调用点 |

---

## 当前状态

| 项 | 值 |
|---|---|
| 测试 | **213 passed** |
| MCP 工具 | 58 |
| §22/§23/§30 覆盖率 | 49/49、18/18、19/19 |
| §18.1 事件 | 21/21 有 emit 调用点 |
| 隐私扫描 | `P0=0 P1=0 P2=0` |
| Step 08 缺口 | 全部关闭 |

**仍未执行首次 git 提交**；提交身份仍未设置；GitHub 令牌仍未吊销。

## 下一步

1. 吊销并重签 GitHub 令牌
2. 决定公开提交身份 → 首次提交
3. 示例 3 定稿后补桥接并修正 `subject: 'cs'` → `computer-science`
4. 示例 4 / 5 产出后按同一套脚本验收
