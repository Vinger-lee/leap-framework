# Step 05 · 测试、文档、CI 与发布准备

- **日期**：2026-09-19
- **对应任务**：#5
- **状态**：✅ 完成

---

## 1. 测试套件

```
140 passed in 2.18s
```

| 文件 | 覆盖内容 |
|---|---|
| `test_runtime_units.py` | BKT 估计器、Evidence Stage 判据、FSRS 调度 |
| `test_state_guard.py` | 领域校准门禁、单元批量推进、前置依赖、乐观并发、迁移判据 |
| `test_knowledge_dag.py` | DAG 校验（环 / 悬空 / 自环 / 预算 / 关系类型）、节点持久化 |
| `test_lifecycle.py` | 会话生命周期、评估契约、错误概念、策略与遥测、复习、报告、领域证据 |
| `test_infrastructure.py` | 配置、存储、Schema 约束、事务回滚、隐私扫描器 |

### 1.1 守卫测试的双向性

State Guard 是安全边界，因此**从两个方向测试**：既要能拒绝，也要能放行。只会拒绝的守卫会造成学习者死锁。

已覆盖：零证据推进 → 拒绝；部分节点达标 → 整体拒绝；全部达标 → 允许；旧 `state_version` → 拒绝；`manual_override` → 允许并留痕。

### 1.2 约束级测试

直接验证数据库层的硬约束，而不只是应用层：

- 外键被真正强制（插入不存在 learner 的 session → `IntegrityError`）
- `assessment_results.raw_answer` 不能为 NULL
- `evidence_stage` 枚举受 CHECK 约束（写 `'mastered'` → `IntegrityError`）
- 事务在异常时回滚

## 2. 测试驱动出的真实缺陷

本轮测试发现并修复了 **6 个实现缺陷**（不是改测试迁就代码，是修代码）：

| # | 缺陷 | 修复 |
|---|---|---|
| 1 | **策略优先级错误**：前置缺失排在错误概念之前，导致有活跃错误概念时先去做前置补强 | 错误概念提升为规则 #1。理由：错误的心理模型会污染后续所有观测，优先级应高于前置补强 |
| 2 | `get_mastery_status` 在状态行不存在时**不返回 `misconception_ids`** | 权威表数据不应因缓存行缺失而消失，改为始终返回 |
| 3 | `RetentionTools._reevaluate_stage` 与 `AssessmentTools._reevaluate_stage` **跨 mixin 命名冲突**（MRO 覆盖） | 重命名为 `reevaluate_evidence_stage`，消除隐式覆盖 |
| 4 | 扫描器 **`ART001` 规则从未被扫描到**（被错误排除出行级扫描） | 修复，并补自检测试 |
| 5 | 扫描器 **Windows 路径重复报告**（同时命中 Win / Unix 规则） | 加负向后顾断言 |
| 6 | 扫描器 **没有豁免机制**，导致它把自己和测试夹具的合成样本判为真实泄露 | 新增行级 `security-scan: allow` 与文件级 `security-scan: allow-file` 标记 |
| 7 | 扫描器 **把 `@users.noreply.github.com` 文档示例判为邮箱泄露** | 新增规则级 `allowlist` 机制，放行 GitHub noreply 与 RFC 2606 保留域（`example.com/org/net`、`localhost`） |
| 8 | 静态模块加载（`importlib`）未注册 `sys.modules`，导致 `@dataclass` 解析注解失败 | 在 `exec_module` 前注册模块 |

## 3. 隐私扫描器的二次回归（重要）

启用规则后，扫描器**立刻抓到本仓库自己的两处泄露**：

```
P0 SEC002  reports/step-01-security-audit.md:35   sk-<样本原文>
P1 PII002  reports/step-01-security-audit.md:36   <真实样本路径>
P1 PII004  reports/step-01-security-audit.md:37   <样本邮箱>
P1 PII005  reports/step-01-security-audit.md:38   <样本手机号>
P1 ART001  scripts/security_scan.py:181           （规则自身正则包含目标标记）
```

这正是**"审计报告本身也是泄露源"**的真实案例 —— Step 01 报告里逐条引用了合成样本原文。已全部改为掩码占位符，并为规则自身的正则加行级豁免。

现在仓库状态：

```
[security_scan] files=58 P0=0 P1=0 P2=0
```

并把这条检查固化成测试 `test_repository_itself_is_clean` —— **任何未来提交引入 P0/P1 都会直接让测试失败**。

### 3.1 第三次回归：门禁在真实开发中生效

写本报告的过程中，用户并行新增了设计文档与示例页面。重新扫描后门禁**立刻报出 1 条 P1**：

```
P1 PII004 Email address  reports/step-05-tests-docs-ci.md:112
    （本报告推荐的 GitHub noreply 邮箱示例）
```

这是一条**误报** —— `@users.noreply.github.com` 是 GitHub 官方文档化的非识别性地址，
推荐它正是为了避免暴露真实邮箱。处理方式不是加豁免标记掩盖，而是**改进规则**：
为 `Rule` 增加 `allowlist` 字段，放行 GitHub noreply 与 RFC 2606 保留域。

这验证了门禁的实际价值：**它在真实开发流程中主动发现了我自己写的文档问题**，
而不是只在一次性审计时有效。

## 4. 文档交付

| 文件 | 说明 |
|---|---|
| `README.md` | 项目门面：定位、架构、快速开始、核心机制、参数表、P0 边界 |
| `docs/host-agent-system-prompt.md` | **可直接复制的宿主 Agent System Prompt** + 工具速查 + 错误码表 + 最小可用序列 |
| `LICENSE` | MIT |
| `reports/step-01..05` | 分阶段实施报告 |

`docs/host-agent-system-prompt.md` 是 §36 P0 交付项 #9（Host Agent 侧 System-Prompt 文档）。它把"LEAP 负责什么 / Agent 负责什么"的边界写成了可执行规则，特别是六条硬规则（不自己算掌握度、必传 `raw_answer`、不绕过守卫等）。

## 5. CI

`.github/workflows/ci.yml`：

- **privacy-scan** job：每次 push / PR 跑隐私扫描，有 P0/P1 直接失败
- **test** job：Python 3.11 / 3.12 / 3.13 矩阵

`permissions: contents: read` —— 最小权限，不授予写权限。

## 6. 发布前检查清单

| 项 | 状态 |
|---|---|
| 隐私扫描 P0/P1 = 0 | ✅ |
| 全部测试通过 | ✅ 140 passed |
| `.gitignore` 覆盖密钥 / 本地数据 / `.workbuddy-ai/` | ✅ |
| 许可证 | ✅ MIT（版权方为 "LEAP Framework Contributors"，不含个人信息） |
| 无个人绝对路径 | ✅ |
| 无 AI 引用残留标记 | ✅ |
| README 与接入文档 | ✅ |
| CI 门禁 | ✅ |
| **首次提交前完成脱敏** | ⚠️ 尚未 commit，**这是建立干净历史的唯一窗口期** |

## 7. 仍未完成 / 待用户决策

| 项 | 说明 |
|---|---|
| 首次 git 提交 | 尚未执行。建议确认后再提交，避免历史留痕 |
| **git 提交身份未设置** | `user.name` / `user.email` 全局与仓库级**均未设置**。公共仓库的每个 commit 都会永久公开作者姓名与邮箱 —— 这属于隐私决策，**必须由用户决定**（可用 GitHub 提供的 noreply 邮箱，例如 `12345+user@users.noreply.github.com`） |
| 远端仓库地址 | `pyproject.toml` 的 `project.urls.Homepage` 仍是占位 `https://github.com/` |
| `examples/01-python-recursion/gemini-code-*.html` | Gemini 产出的示例页面尚未验收，也尚未重命名为规范要求的 `leap-01-python-recursion.html` |
| 参考 Host Agent 示例代码 | 属 P1，不在本轮范围 |

## 8. 提交前的建议操作顺序

```bash
# 1. 先决定公开身份（二选一）
git config --local user.name  "<公开显示名>"
git config --local user.email "<GitHub noreply 邮箱>"     # 推荐，避免暴露真实邮箱

# 2. 再跑一次门禁
python scripts/security_scan.py --root . && pytest -q

# 3. 提交
git add -A && git commit -m "feat: LEAP Framework V2.0 P0 runtime, MCP server and tool set"

# 4. 关联远端并推送
git remote add origin <repo-url> && git push -u origin main
```

> 用 `--local` 而非 `--global`：这样提交身份只作用于本仓库，不会影响你其他项目的默认身份。

## 9. 下一步建议

1. **验收 Gemini 前端示例**，对照 `examples/_shared/leap-web-spec.md` 与 JSON 契约检查
2. **决定公开提交身份，然后首次提交**（见 §8）
3. 进入 P1：最小 Host Agent 参考实现
