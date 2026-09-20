# Step 01 · 隐私安全审计与仓库初始化

- **日期**：2026-09-19
- **负责人**：WorkBuddy AI（Agent 执行）
- **对应任务**：#1
- **状态**：✅ 完成

---

## 1. 背景与目标

本项目最终要推送到 **GitHub 公共仓库**。公开仓库一旦推送，历史提交中的任何个人信息、密钥、内部路径都会永久留痕（即使后续删除，仍可通过 commit 历史检索到）。

因此在任何工程代码开工之前，先做一次全仓库隐私 / 敏感信息审计，并建立防回归机制。

## 2. 执行内容

### 2.1 编写可复用的扫描工具

新增 `scripts/security_scan.py`（约 480 行，纯标准库，无第三方依赖）：

- 递归遍历仓库，自动跳过 `.git` / `node_modules` / `.venv` / 二进制与媒体文件；
- 13 条检测规则，分三级：
  - **P0（阻断发布）**：私钥块、云/API 密钥（AWS / GitHub PAT / `sk-` / Slack / Google）、`key=value` 形式的密钥字面量、中国居民身份证号；
  - **P1（必须修复）**：Windows / macOS / Linux 个人绝对路径、邮箱、中国手机号、AI 工具链引用残留标记（形如 `filecite` + `turnNfileN` 或 `oai_` 前缀的内部标记）、Unicode 私用区字符、双向控制字符（Trojan-Source 类隐藏文本）；
  - **P2（建议复核）**：敏感文件名（`.env` / `id_rsa` / `*.pem`…）、内网地址、公网 IPv4。
- 输出 Markdown 报告与 JSON，退出码 `0` 干净 / `1` 有 P0+P1 / `2` 仅有 P2，可直接接入 CI 作为门禁。

### 2.2 工具自检（验证有效性）

用一份合成的"脏"样本做自检，确认各规则确实能命中。下表用**掩码占位符**记录结果（本报告本身也是仓库内容，不能把样本原文写进来）：

```
[security_scan] files=1 P0=1 P1=6 P2=0
P0  SEC002  Cloud / API access key       sample.md:5  sk-<REDACTED>
P1  PII002  Personal absolute path (Win) sample.md:2  <drive>:/Users/<user>/Documents/secret.md
P1  PII004  Email address                sample.md:3  <user>@example.com
P1  PII005  Chinese mobile phone number  sample.md:4  138****5678
P1  ART001  AI citation artifact         sample.md:6  <AI citation marker>
P1  PII003  Personal absolute path (nix) sample.md:7  /Users/<user>/projects/x
P1  ART002  Private-use-area character   sample.md:8  U+FEFF
```

自检中发现并修复了 2 个缺陷：

1. **`ART001` 规则从未被扫描到** —— 该规则在行级扫描中被错误排除，导致 AI 引用残留标记漏检（正是历史记录里出现过的问题类型）。已修复。
2. **Windows 路径被重复报告** —— `<drive>:/Users/<user>/` 同时命中 Windows 与 Unix 路径规则。已加负向后顾断言消除误报。

> **补充（本轮回归）**：启用规则后，扫描器把**本报告初稿中的样本原文**判为 P0/P1 —— 这正是"审计报告本身也是泄露源"的真实案例。已全部改为掩码占位符，并新增行级 / 文件级豁免标记机制，供测试夹具使用。

### 2.3 实际仓库扫描

```
[security_scan] files=15 P0=0 P1=0 P2=0
```

**当前仓库内容干净，无隐私 / 密钥问题。**

值得说明的是：计划书 §1.1 曾存在的"私有区字符 + `fileciteturn…` 明文"残留，在上一轮文档修订中已被清理，本轮扫描确认无残留。

### 2.4 建立防回归机制

- `git init -b main` 初始化仓库（此前并非 git 仓库）；
- 新增 `.gitignore`，覆盖密钥、本地数据库、`data/`、`artifacts/`、`logs/`、Python / Node 构建产物、编辑器与系统文件；
- **特别处理**：`.workbuddy-ai/`（AI 助手本地工作区，含记忆与草稿）**已排除**，不进入公共仓库。已验证 `git check-ignore` 生效。

## 3. 交付物

| 文件 | 说明 |
|---|---|
| `scripts/security_scan.py` | 可复用隐私扫描器，可接 CI |
| `.gitignore` | 仓库忽略规则 |
| `.git/` | 已初始化的 git 仓库（分支 `main`） |
| `reports/step-01-security-audit.md` | 本报告 |

## 4. 风险与待确认

| 项 | 说明 | 建议 |
|---|---|---|
| `.workbuddy-ai/` 是否入库 | 当前**排除**。内含项目记忆与决策记录，属本地 Agent 状态 | 若希望公开决策记录，可改为收录并先做脱敏 |
| 开源许可证 | 尚未确定 | 下一步补 `LICENSE`，建议 MIT 或 Apache-2.0 |
| 提交历史 | 目前仓库无任何提交，**是建立干净历史的唯一窗口期** | 首次提交前完成脱敏；避免"先提交再删" |
| 扫描器局限 | 规则基于正则，无法识别无固定格式的自定义密钥 | 提交前建议再跑一次人工复核 |

## 5. 下一步

进入 P0 工程实现：工程骨架 + SQLite Schema（任务 #2）。
