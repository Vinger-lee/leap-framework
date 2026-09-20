# 文档索引 · Documentation Index

> 本仓库**不包含**完整的框架设计与视觉规范。
> 这两份权威文档由项目作者另行维护，**未发布**在本仓库。
> 本仓库的代码（`src/leap/`）与示例（`examples/`）遵循那些规范；如有需要，请联系作者获取。


> 本仓库**不包含**完整的框架设计与视觉规范。
> 这两份权威文档由项目作者另行维护，**未发布**在本仓库。
> 本仓库的代码（`src/leap/`）与示例（`examples/`）遵循那些规范；如有需要，请联系作者获取。


**语言 / Language**: **简体中文** ｜ [English](README.en.md)

---

## 权威规范（改动前必读）

| 文档 | 语言 | 管什么 |
|---|---|---|
| *（文档不在本仓库）* | — | （作者另行维护的框架设计文档，不在本仓库）。代码以该文档为权威。 |
| *（文档不在本仓库）* | — | （作者另行维护的视觉规范，不在本仓库）。示例必须遵守。 |
| [`../examples/_shared/leap-web-spec.md`](../examples/_shared/leap-web-spec.md) | 中文 | 前端页面**结构与数据契约** |
| [`../examples/_shared/leap-bridge.md`](../examples/_shared/leap-bridge.md) | 中文 | **宿主桥接契约**：页面 ↔ Runtime 的双向接口 |
| [`../examples/_shared/interaction-output.schema.json`](../examples/_shared/interaction-output.schema.json) | — | 机器可读的 JSON 输出契约 |

> 冲突裁决：**结构**以 `leap-web-spec.md` 为准（在本仓库），**视觉与框架行为**以作者另行维护的设计文档为准（不在本仓库）。

---

## 接入指南

| 文档 | 语言 | 读者 |
|---|---|---|
| [`host-agent-system-prompt.md`](host-agent-system-prompt.md) | 中文 | 要接入 LEAP 的宿主 Agent 开发者 |
| [`host-agent-system-prompt.en.md`](host-agent-system-prompt.en.md) | English | Same, in English |
| [`i18n.md`](i18n.md) | 中文 | 要新增界面语言的人 |
| [`i18n.en.md`](i18n.en.md) | English | Same, in English |

---

## 项目说明

| 文档 | 内容 |
|---|---|
| [`../README.md`](../README.md) | 项目总览（中文） |
| [`../README.en.md`](../README.en.md) | Project overview (English) |
| [`../examples/README.md`](../examples/README.md) | 前端示例：命名规则 + 验收清单 + 自动化验收 |
| [`../reports/`](../reports/) | 分阶段实施报告（step-01 ~ step-10） |

---

## 自检脚本

发布或改动后建议依次运行：

```bash
pytest -q                                          # 全量测试
python scripts/spec_coverage.py                    # 设计文档 vs 代码 覆盖率
python scripts/security_scan.py --root .           # 隐私与密钥扫描
python scripts/verify_example.py --all             # 示例静态规范符合性
python scripts/verify_example_runtime.py --all     # 示例运行时行为（需 playwright）
python scripts/apply_leap_bridge.py --check        # 示例宿主桥接完整性
```

退出码约定：`0` 干净 / `1` 有阻断问题 / `2` 仅警告。前四个已接入 CI。

---

## 不参与上传的内容

本仓库是公开的，以下内容**只存在于本地**，不会进入任何提交：

| 路径 | 内容 | 原因 |
|---|---|---|
| `.workbuddy-ai/`、`.workbuddy*/` | AI 助手工作区（记忆、草稿、会话状态） | 属本地 Agent 状态，不是项目源码 |
| `.claude*/`、`.cursor*/`、`.aider*`、`.continue*/`、`.codeium/`、`.copilot/`、`.windsurf/`、`.zed/`、`.specstory/`、`.gemini/` 等 | 各类 AI 工具的配置与状态目录 | 同上，且常含个人化配置 |
| `agent-state/`、`.ai/`、`ai-cache/` | 通用 Agent 状态与缓存 | 同上 |
| `.mcp.json` | MCP 客户端配置 | `env` 块常含 API 凭据；如需发布请先脱敏再 `git add -f` |
| `_archive/` | 内部工作材料与临时产物 | 见 [`../_archive/README.md`](../_archive/README.md) |
| `.pytest_cache/`、`__pycache__/`、`data/`、`artifacts/`、`logs/` | 缓存、构建产物、本地运行数据 | 可随时重新生成 |

### 三重保障

不靠"记得别提交"来保证：

1. **`.gitignore`** —— 覆盖上述全部路径，并含通配形式（`.workbuddy*/`）以防变体名；
2. **扫描器规则 `AI001`** —— 路径级检测，即使 `.gitignore` 被绕过（如 `git add -f`）也会报 P1 并阻断；
3. **测试** —— `tests/test_infrastructure.py::TestAiWorkspaceIsolation` 直接查 `git ls-files` 与全部提交历史，断言零个 AI 工作区文件被跟踪。**CI 每次都会跑。**

> 也就是说：就算前两道防线都失效，CI 也会拦住。

---

## 新增语言

要新增界面语言，见 [`i18n.md`](i18n.md) §4。要新增**文档**语言，按本目录的命名约定加 `<name>.<locale>.md`，并在上表中补一行。
