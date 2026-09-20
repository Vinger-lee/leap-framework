# Step 03 · 核心 Runtime 实现

- **日期**：2026-09-19
- **对应任务**：#3
- **状态**：✅ 完成

---

## 1. 目标

实现 P0 的"大脑"：所有**必须由服务端决定**的组件。计划书 §2.3 明确：Prompt 只能引导行为，状态一致性必须由服务端保证。本步实现的就是这个服务端。

新增模块（`src/leap/runtime/`）：

| 文件 | 对应章节 | 职责 |
|---|---|---|
| `events.py` | §18 | 事件日志（26 种事件类型） |
| `bkt.py` | §10.2‑1 | 简化遗忘感知 BKT 估计器 |
| `evidence.py` | §11.4 | Evidence Stage 升级 / 回退启发式 |
| `scheduler.py` | §13 | py‑fsrs 复习调度封装 |
| `state_guard.py` | §19 | 服务端状态守卫 |
| `policy.py` | §8 / §9 / §12 / §15 | 教学策略决策引擎 |

---

## 2. 各模块要点

### 2.1 `bkt.py` —— mastery_probability 由服务端计算

落实 §10.2‑1：**P0 不依赖 LLM 做概率估算**。单次更新四步：

```
1. 时间衰减   p * 0.5^(elapsed_days / forget_halflife_days)
2. 证据更新   经典 BKT 后验（p_guess / p_slip）
3. 状态转移   p' = p + (1-p) * p_transit
4. 自发遗忘   p' * (1 - p_forget)
```

两个关键设计：

- **支持部分得分**：`score` 参数按 `s·P(correct) + (1-s)·P(incorrect)` 混合后验。这样"方法对、算错"不会等同于全错。
- **`confidence_weighted()`**：落实 §29.2 —— 评估不确定时把观测拉回先验，**不允许把"不确定"写成 `mastery = 0`**。

实测行为（默认参数）：

```
初始 0.20 → 答对 0.657 → 0.909 → 0.965 → 0.975
部分得分 0.5 → 0.919        （比全对低，比全错高，符合预期）
30 天后再答错 → 0.367        （时间衰减 + 负证据共同作用）
低置信度(0.1)观测 → 仅从 0.975 微调到 0.963   （未把不确定当事实）
```

### 2.2 `evidence.py` —— Evidence Stage 允许回退

§11.4 的参考默认判据全部落地，并且**回退优先于升级**（先检查回退路径）：

- `retained`/`transferred` + 长期未接触 → 退回 `practiced` 并重新进入复习队列；
- `transferred` + 最近一次迁移失败 → 退回 `demonstrated`。

所有阈值从 config 读取，注释明确写出"**权威判据在 Policy 层，本节只是参考默认值**"，与 §11.4 的表述一致。

### 2.3 `scheduler.py` —— FSRS 只做调度

- 采用 FSRS 标准 **1‑4 评分**（Again/Hard/Good/Easy），与 §13.5 一致；
- **不硬编码 1/3/7 天间隔**，间隔全部由调度器从记忆状态推导；
- 边界只使用 Unix 秒，`datetime` 转换仅在本模块内部发生；
- 学习步长改为 `(10 分钟, 1 天)` —— FSRS 默认的 60 秒/600 秒适合闪卡刷题，不适合导师场景。**此为偏离默认值的实现决策，已在此记录**。

### 2.4 `state_guard.py` —— 唯一有权批准状态迁移的组件

`advance_unit` 的批量语义按 §6.6 实现：**遍历 unit 内全部 node，逐个过 node 级校验，任一不过则整体拒绝**。无独立 unit 表。

7 项检查全部实现：`prerequisites_met` / `assessment_sufficient` / `evidence_sufficient` / `transfer_required` / `transfer_completed` / `current_state_version_valid` / `manual_override`。

另外实现：

- **§19.2‑1 Domain Grounding 前置拦截**：`allow_skip_domain_grounding=false` 时，未完成校准且无基准报告 → 拒绝 `generate_diagnostic`（中文提示文案与文档一致）；
- **§19.4 乐观并发**：`check_state_version` + `bump_state_version`；
- **§13.6 `transfer_required` 判据**：`bloom_level >= apply` 且非记忆/理解类 → 要求迁移。支持中英文 Bloom 标签（记忆/理解/应用/分析/评价/创造）。

### 2.5 `policy.py` —— 策略与动作严格分离

§8.4 的 10 个 Strategy 与 15 个 Action 各自成集，**`Strategy != Action`** 在类型层面就成立。

决策链（P0 规则式，对应 §35.3 可插拔阶梯第一级）按优先级：

```
1. 前置缺失        → Scaffolding  / Review Prerequisite   （§21.3 回退）
2. 活跃错误概念    → Correction   / Correct Misconception （§9.4）
3. 学习摩擦        → Scaffolding  / Give Hint             （§15.3）
4. 重复失败/高依赖 → Worked Example / Provide Worked Example（§9.5）
5. 无任何证据      → Explanation  / Explain Concept
6. 推理质量低      → Socratic     / Ask Guiding Question  （§9.3）
7. 掌握达标但证据不足 → Retrieval Practice / Generate Retrieval Item
8. 需要迁移未通过  → Transfer Probe / Run Transfer Probe  （§13.6）
9. 本节点复习到期  → Retrieval Practice / Generate Retrieval Item（§21.5）
10. 无阻塞         → Retrieval Practice / Generate Practice
```

同时实现 §22.4 的 `build_teaching_context`（一次返回 13 类状态，减少高频读取）与 §27.1 的决策落库（`pedagogical_decisions`，可回放）。

**注意**：`policy.py` 中的 `due_reviews` 只读取，不阻塞；§13.4 明确"到期复习不应在系统层面一律阻止所有新知识学习"——是否阻塞由 Guard + Policy 共同决定，不做全局硬规则。

---

## 3. 验证结果

端到端场景（Python 递归，`n1 调用栈 → n2 递归`，同一 unit）：

| 场景 | 结果 |
|---|---|
| 未做 Domain Grounding | ✅ REJECT（中文提示文案正确） |
| 有报告但 stage=pending | ✅ REJECT |
| stage=completed | ✅ ALLOW |
| 零证据推进 unit | ✅ REJECT（n1/n2 均报缺证据） |
| n1=demonstrated，n2=practiced | ✅ REJECT（n2 缺评估证据 + 缺迁移证据） |
| 全证据齐备 | ✅ ALLOW（7 项检查全 True） |
| 旧 `state_version` | ✅ REJECT（stale version） |
| 正确 `state_version` | ✅ ALLOW |
| 无证据时的 Policy | ✅ Explanation / Explain Concept |
| 全证据时的 Policy | ✅ Retrieval Practice / Generate Practice |

**关键结论：守卫既能拒绝也能放行**，不存在"永远 REJECT"的死锁路径。

---

## 4. 与文档的偏差记录

| 项 | 说明 |
|---|---|
| FSRS 学习步长 | 由库默认 `60s/600s` 改为 `10min/1d`，适配导师场景（可配置） |
| BKT 参数具体数值 | 文档未给值，本实现取标准 BKT 启发值并标注为可配置 |
| `retention_interval_days` | §11.4 提到"配置间隔时间"但未给值，实现默认 1.0 天 |
| Policy 规则优先级 | 文档给出策略清单但未定优先级，本实现按 §21 的前进/补强/回退/迁移/复习逻辑排序 |

---

## 5. 下一步

任务 #4：MCP Server（stdio）+ §22 全量工具集。
