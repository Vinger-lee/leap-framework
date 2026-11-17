---
title: "宿主 MCP 配置与 Skill 安装"
tags: ["leap", "integration", "reference"]
aliases: ["宿主 MCP 配置与 Skill 安装 guide"]
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP 宿主 MCP 配置 mcpServers stdio 安装 档位 Skill 安装 排错 foundations definitions workflow`
> Extension: `LEAP 宿主 MCP 配置 mcpServers stdio 安装 档位 Skill 安装 排错 failure cases examples comparison`
> Advanced: `LEAP 宿主 MCP 配置 mcpServers stdio 安装 档位 Skill 安装 排错 invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [[docs/agent-skill]] · [[docs/FACADE_CN]] · [[docs/FACADE]] · [[docs/INTEGRATION_CN]] · [[docs/INTEGRATION]]

# 宿主 MCP 配置与 Skill 安装

本页只解决一件事：**让宿主真正连上 LEAP MCP，并能加载 `leap-tutor` Skill**。
所有示例都按"不修改 LEAP 仓库、不写项目 data/ 与 artifacts/"的隔离方式给出，可直接复制。
配置好之后的验收与已知限制见 [[docs/agent-skill|leap-tutor 接入与验收]]。

## 1. 前置检查（一次）

```bash
# 必须是 Python 3.12；仓库 .venv-dev 是开发用解释器，.venv 是旧版不要用
E:\...\LEAP_Framework\.venv-dev\Scripts\python.exe --version

# 方式 A（推荐）：源码可导入，无需安装
set PYTHONPATH=E:\...\LEAP_Framework\src
# 方式 B：可编辑安装进当前解释器（之后不需要 PYTHONPATH）
E:\...\LEAP_Framework\.venv-dev\Scripts\python.exe -m pip install -e .
```

MCP SDK 需要 **2.3+**（代码使用 `mcp.server.mcpserver.MCPServer`；1.x 没有该模块）。
`python -m leap.doctor --profile quickstart` 可检查安装、配置与工具目录。

## 2. 通用 stdio 配置（任何支持 `mcpServers` 的宿主）

下面是一份**已验证可启动**的最小配置（Windows 绝对路径；把 `E:\...` 换成你的仓库路径，
并确认目录存在）。它把数据库与 artifact 根都放到临时目录，不触碰仓库文件：

```json
{
  "mcpServers": {
    "leap": {
      "command": "E:\\...\\LEAP_Framework\\.venv-dev\\Scripts\\python.exe",
      "args": ["-m", "leap.server", "--tool-profile", "quickstart"],
      "env": {
        "PYTHONPATH": "E:\\...\\LEAP_Framework\\src",
        "LEAP__DATABASE_PATH": "E:\\...\\leap-work\\leap.db",
        "LEAP__ARTIFACT_ROOT": "E:\\...\\leap-work\\artifacts"
      }
    }
  }
}
```

- `command` 也可以用 `leap-mcp`（等价于 `python -m leap.server`），但只有 `pip install -e .`
  之后才存在；源码未安装时用上面的 `python -m leap.server`。
- `args` 里显式写 `--tool-profile quickstart` 最稳妥；也可以用单下划线环境变量
  `LEAP_TOOL_PROFILE=quickstart`，或 `config/default.yaml` 的 `tool_profile`。优先级：
  显式参数 > `LEAP_TOOL_PROFILE` > `config/default.yaml` > `full`。
- 路径解析规则（`database_path` 与 `artifact_root` 相同）：绝对路径原样使用；相对路径在
  设置了 `LEAP_HOME` 时相对 `LEAP_HOME`，否则相对**当前工作目录**（不是仓库根，也不是
  安装目录）。推荐二选一：写绝对路径，或设 `LEAP_HOME=E:\...\leap-work` 并保持相对值。
  不设置时默认 `data/leap.db` 与 `artifacts/`。
- 完整课程交付默认写到用户目录的 `~/LEAP/课程输出/`。可以设置独立的
  `LEAP__COURSE_OUTPUT_ROOT`，每次导出的教学 HTML 和 A4 PDF 都放在同一个课程标题文件夹中。
- server 把日志写到 stderr；stdout 保留给 MCP 协议。启动日志会打印实际数据库路径、配置
  值来源与 `LEAP_HOME` 状态（例如 `LEAP runtime ready: db=... (configured as 'data/leap.db',
  LEAP_HOME=(unset)) schema=2.1.0`），排错先看它。

## 3. 各宿主的放置位置

| 宿主 | MCP 配置位置 | Skill 扫描位置 |
|---|---|---|
| Claude Code | 项目 `.mcp.json` 或 `claude mcp add` | `.claude/skills/<name>/SKILL.md`（**不扫描** `.agents/skills`） |
| Claude Desktop | `claude_desktop_config.json`（`mcpServers` 同上） | 不支持仓库 Skill，用 [[docs/INTEGRATION|兼容提示词]] |
| Cursor | `.cursor/mcp.json`（`mcpServers` 同上） | 以 Cursor 当前版本为准，未验证 |
| DSH | 通过设置或 `plugin_manager` 添加 `dsh-mcp-client` 条目（`serverName` + `transport: stdio` + `command/args/env`），工具名形如 `mcp__leap__start_learning`；**不要手改 profile 组合文件** | 项目 `.agents/skills`、`.dsh/skills`、`~/.dsh/skills`、`~/.agents/skills`；只扫一层，`<name>/SKILL.md` |
| Codex / WorkBuddy | 宿主同类 stdio MCP 配置；仓库级 Skill 支持**未在本机验证** | 未验证；可先复制到宿主技能目录 |

`.agents/skills/` 是 Agent Skills 生态的跨客户端共享约定（客户端实现指南建议同时扫描
`<project>/.agents/skills/` 与 `~/.agents/skills/`），但**是否扫描由宿主决定**；DSH 扫描，
Claude Code 只扫描 `.claude/skills`。因此 Windows 上把仓库 Skill 安装到 Claude Code 需要：

```powershell
# 复制（或建立目录联接）到 Claude Code 的项目技能目录；不要把 .claude/ 提交进仓库
New-Item -ItemType Directory -Force .claude\skills | Out-Null
Copy-Item -Recurse -Force .agents\skills\leap-tutor .claude\skills\leap-tutor
```

用户级安装（所有项目可用）则复制到 `~\.claude\skills\leap-tutor`。复制后重启会话，
并确认宿主把 `leap-tutor` 显示为已发现；**文件存在不等于已激活**，见
[[docs/agent-skill|验收矩阵]]。

## 4. 档位选择

| 档位 | 工具数 | 适用 | 主要限制 |
|---|---|---|---|
| `quickstart` | 36 | 预审来源校准与日常教学主流程 | 无细粒度证据读取、无 HTML 页面桥接全套接口 |
| `full` | 75 | 拆步评估、证据审查、教学草稿、页面 outbox | 工具 schema 占用较多宿主上下文 |

两档位共用同一套数据；切换档位不需要迁移。工具清单与档位归属以生成的
[MCP 工具参考](mcp-tools.md) 为准，不要凭本节数字硬编码。

## 5. 首次连接验收

1. 启动后先调用只读工具确认连接，例如 `get_teaching_delivery_policy`（无参数，quickstart 可用）；
   失败就停下报告，不要伪造回执。
2. 若加载了 Skill，可用「用 LEAP 学高等数学的极限和导数」检验。
   确认 `start_learning` 的主题为「高等数学」，然后调用 `get_grounding_sources`。
   普通一次性提问无需创建会话。
3. 检查工具目录中是否有 `get_grounding_sources`。两档都需要当前版本的预审证据；
   旧宿主自证与跳过请求会被拒绝。完整调用见 [[docs/INTEGRATION_CN]]。
4. 结束一次试用后，用 `get_learner_snapshot(session_id)` 核对会话状态；关闭用
   `complete_session(session_id)`，并确认回执（关闭后不得继续教学调用）。

## 6. 常见故障

| 现象 | 原因与处理 |
|---|---|
| `ModuleNotFoundError: leap` | 没设 `PYTHONPATH` 且没 `pip install -e .`；或用了错解释器（`.venv` 是 3.9）。 |
| `ImportError: mcp.server.mcpserver` | 安装的 MCP SDK 是 1.x；升级到 2.3+。 |
| 宿主看不到 `start_learning` | 连接的是 `full`/`quickstart` 之外的旧目录，或工具名拼错；重读工具目录。 |
| 宿主显示 Skill 但 MCP 未连接 | 两者独立配置；Skill 只组织流程，所有状态写入仍走 MCP。文件存在不代表 Skill 已激活。 |
| 数据库出现意外数据 | 默认 DB 是仓库根 `data/leap.db`；隔离实验请设置绝对路径 `LEAP__DATABASE_PATH`。 |
| 调用返回 `session_closed` | 会话已关闭；不要再继续教学，按用户意图用 `complete_session(status="active", reopen=True)` 显式重开。 |
| 返回 `grounding_unsupported`、`grounding_withdrawn` 或 `grounding_expired` | 暂停正式授课。首包仅覆盖「从极限到导数与可导性」，复核期限为 180 天。历史记录可读，沿用同一个 SQLite 路径以便重启后续学。 |

## 7. 维护预审来源

按需运行 `python scripts/review_grounding_sources.py` 预查已批准链接、定位和期限。
退出码 `0` 表示预查通过，`1` 表示需要人工复核，`2` 表示有来源的可达性待确认。
发布前由维护者核对原文和教学主张，手动更新预审包，再重启 MCP 服务加载新版本。
本机巡检暂未确认 MIT OCW 的可达性。巡检结果不会修改预审包，运行时继续按本地
批准版本、复核期限与会话回执判定。

> [!note]- 验证顺序：先只读、再建会话、最后写状态
> 先调 `get_teaching_delivery_policy` 确认连接，再执行一次最小 `start_learning`，
> 保留真实 `session_id` 与工具回执；出现失败时保留原始错误码与参数，修正后重试而非重复写入。

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[docs/agent-skill]] · [[docs/FACADE]] · [[docs/FACADE_CN]] · [[docs/INTEGRATION]] · [[docs/INTEGRATION_CN]]
