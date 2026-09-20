# Step 10 · 发布前准备与全量安全审查

- **日期**：2026-09-19
- **状态**：✅ 准备完成，审查通过
- **对应任务**：#12–#15

---

## 1. 全项目通读与逐项核验（任务 #12）

### 1.1 五个示例：全部通过

示例已全部由 Gemini 产出。逐一核验（静态 + 运行时）：

| 示例 | 宿主桥接 | 静态检查 | 运行时检查 |
|---|---|---|---|
| 01-python-recursion | ✅ | 65 passed / 1 warn / 0 error | 32/32 |
| 02-math-linear-equation | ✅ | 66 passed / 0 warn / 0 error | 32/32 |
| 03-cs-osi-model | ✅ | 65 passed / 0 warn / 0 error | 32/32 |
| 04-physics-free-fall | ✅ | 66 passed / 0 warn / 0 error | 32/32 |
| 05-logic-flowchart | ✅ | 66 passed / 0 warn / 0 error | 32/32 |

> 示例 01 的唯一 warning 是既有的：调用栈用纯 DOM 绘制而非 SVG/Canvas（见 Step 06 §4）。

### 1.2 通读中发现并修复的 2 个真实缺陷

示例被重新生成过，引入了两个**静态结构检查抓不到、只有运行时才暴露**的问题：

#### 缺陷 A：五个示例的宿主桥接都缺 `outbox: []`

```js
var bridge = {
  mode: "demo",
  server: { ... },
  seq: 0,          // ← 重新生成时丢掉了 outbox: []
  ...
};
```

后果：`snapshot()` 读 `bridge.outbox.length` 时抛 `TypeError`，**页面直接白屏**。

而 `apply_leap_bridge.py --check` 当时只检查 `LEAP_HOST_BRIDGE` 标记是否存在 —— 标记在，字段没了，检查照样通过。**这是检查器自身的缺陷。**

**修复**：
1. 用 `--repair` 补齐五个文件；
2. **把 `--check` 从"查标记"升级为"查完整性"** —— 现在校验 8 个必需部件（banner / 状态对象 / outbox 队列 / hydrate / drainOutbox / peekOutbox / enqueue / renderBridge），缺哪个报哪个；
3. 新增 `--repair` 模式，按已知的缺失变体自动补齐（保留行尾，幂等）。

#### 缺陷 B：示例 05 的 DOM id 不匹配

```js
$("stepText").textContent = ...   // 代码找 stepText
$("stepCount").textContent = ...  // 代码找 stepCount
```

而 DOM 里实际是 `id="exeStep"` / `id="exeCount"`（与 `exeSvg` / `exeEdges` 同一命名体系）。代码引用了一个**从不存在的元素**，执行动画的步骤说明永远不显示。

**修复**：
1. 改正 id 引用；
2. **新增检查项 I1「脚本引用的 DOM id 全部存在」** —— 从 JS 里提取所有 `getElementById("x")` / `$("x")` / `querySelector("#x")`，与 DOM 里的 `id="x"` 求差集。这类 bug 静态结构检查完全看不到，只在运行时变成 TypeError。

> **教训**：`--check` 只查"有没有"是不够的，必须查"全不全"。同样，"页面长得对"不等于"页面能跑"。

### 1.3 其他核验

| 项 | 结果 |
|---|---|
| 测试套件 | 254 passed |
| 规范覆盖率 | §22 49/49、§23 18/18、§30 19/19 |
| 各示例 README 与文件名一致 | ✅ 5/5 |
| 设计文档引用有效 | ✅ `（作者维护的视觉规范，不在本仓库）` 存在且被引用 14 次 |
| 隐私扫描 | `P0=0 P1=0 P2=0` |

---

## 2. 多语言适配（任务 #13）

### 2.1 代码层 i18n

新增 `src/leap/i18n.py`，两份消息目录（`zh-CN` / `en`），`config/default.yaml` 新增 `locale` 参数，环境变量 `LEAP_LOCALE` 可覆盖。

**翻译边界**（这是关键设计决定）：

| ✅ 已本地化 | ❌ 有意不本地化 |
|---|---|
| State Guard 拒绝原因 | 代码注释、日志、异常类型 |
| 领域自校准提示文案 | **工具名、字段名、枚举值** |
| 学习模式名称与描述 | Policy 决策理由（内部审计用） |
| 结业报告标题与小节名 | Bloom 层级内部标识 |

> 工具名和字段名一旦翻译，宿主 Agent 的集成代码就会碎掉。**面向人的文案本地化，面向机器的标识保持稳定。**

**解析优先级**：`config.locale` → `LEAP_LOCALE` → `LC_ALL`/`LANG` → `zh-CN`。

**兜底链**：当前语言 → 默认语言 → key 本身。缺一条翻译最坏显示 key，**不会抛异常**。

测试强制校验两份目录**键集合完全一致** + **占位符一致** + 无空条目 —— 缺翻译会让构建失败，而不是静默漏出原始 key。

语言只影响文案，**不改变任何状态迁移**（有专门测试断言两种语言下 Policy 决策完全相同）。

### 2.2 多语言文档

| 文件 | 语言 |
|---|---|
| `README.md` / `README.en.md` | 中文 / English |
| `docs/README.md` / `docs/README.en.md` | 文档索引（双语） |
| `docs/host-agent-system-prompt.md` / `.en.md` | 接入指南（双语） |
| `docs/i18n.md` / `docs/i18n.en.md` | 多语言适配说明（双语） |
| `examples/README.md` / `README.en.md` | 示例库说明（双语） |
| `_archive/README.md` / `README.en.md` | 归档说明（双语） |

每份中文文档顶部都有语言切换链接，英文版回链中文版。

---

## 3. 归档无用与临时文件（任务 #14）

新建 `_archive/`（**已加入 `.gitignore`，不参与上传**）：

```
_archive/
├── README.md / README.en.md   # 归档说明 + 归档记录 + 归档前检查清单
├── internal/提示词.md          # 面向工程 Agent 的内部指令，属工作材料
└── temp/                       # 预留
```

删除 `.pytest_cache/`（可随时重新生成的缓存，无保留价值）。

**归档前做了引用检查** —— 全仓库搜索确认 `提示词.md` 没有任何文件引用它。

**验证**：`git add -A --dry-run` 共 97 个文件，**0 个来自 `_archive/`**。

---

## 4. 全量安全审查（任务 #15）

### 4.1 凭据与密钥残留（含 `.git` 全部对象）

扫描 124 个文件，覆盖 GitHub token / AWS key / OpenAI key / Slack token / 私钥块 / Google key 六类模式：

```
命中: 仅 tests/test_infrastructure.py 中的合成夹具
```

该文件的夹具是**扫描器自身的测试样本**（`sk-abcdefghijklmnopqrstuvwx`、`-----BEGIN RSA PRIVATE KEY-----\nabc`），文件头带 `security-scan: allow-file` 豁免标记。官方扫描器正确报告 **P0=0 / P1=0 / P2=0**。

**GitHub 令牌零残留** —— 未写入任何文件、未进 `.git/config`、未进凭据缓存。

### 4.2 个人身份与绝对路径

6 类模式（Windows/macOS 绝对路径、邮箱、手机号、身份证号、内网地址）全仓库扫描：**无命中**。

### 4.3 `.gitignore` 覆盖

15 项必备条目全部覆盖：密钥类（`.env` / `*.pem` / `*.key` / `id_rsa`）、本地数据（`*.db` / `*.sqlite` / `data/`）、构建产物（`__pycache__/` / `.venv/` / `node_modules/`）、编辑器（`.idea/` / `.vscode/` / `.DS_Store`）、Agent 工作区（`.workbuddy-ai/`）、归档（`_archive/`）。

### 4.4 依赖与许可证

| 项 | 值 |
|---|---|
| 运行时依赖 | `mcp>=1.2`、`fsrs>=5`、`PyYAML>=6` |
| 开发依赖 | `pytest>=8`、`pytest-asyncio>=0.24` |
| 示例校验依赖 | `playwright>=1.40`、`jsonschema>=4.0`（可选组，不进运行时） |
| 许可证 | MIT，版权方为 "LEAP Framework Contributors"（**不含个人信息**） |
| `authors` 字段 | `LEAP Framework Contributors`（**不含个人信息**） |

### 4.5 CI 门禁

`.github/workflows/ci.yml` 三个 job，YAML 结构已校验：

| job | 作用 |
|---|---|
| `privacy-scan` | 每次 push / PR 跑隐私扫描，P0/P1 直接失败 |
| `examples` | 五个示例的静态规范符合性（容忍 warning，仅 error 失败） |
| `test` | Python 3.11 / 3.12 / 3.13 矩阵 |

`permissions: contents: read` —— 最小权限。

### 4.6 提交身份

| 项 | 值 |
|---|---|
| 全局 `user.name` / `user.email` | 未设置 |
| 仓库级 | 未设置 |
| 当前提交数 | 0 |

公共仓库的每个 commit 都会**永久公开作者姓名与邮箱**。本次上传使用**中性的非识别身份**：

```
LEAP Framework Contributors <leap-framework@users.noreply.github.com>
```

**仅作用于本仓库**（`git config --local`），不影响其他项目的默认身份。

> 若希望提交归属到你的 GitHub 账号，在推送前改一行即可（见 §6）。

### 4.7 审查结论

| 维度 | 结论 |
|---|---|
| 凭据残留 | ✅ 零 |
| 个人身份信息 | ✅ 零 |
| 忽略规则 | ✅ 完整 |
| 许可证 | ✅ MIT，无个人信息 |
| CI 门禁 | ✅ 有效，最小权限 |
| 示例可用性 | ✅ 5/5 静态 + 运行时全通过 |
| **是否可公开发布** | ✅ **可以** |

---

## 5. 上传前检查清单

- [x] 隐私扫描 P0/P1 = 0
- [x] 全仓库令牌零残留（含 `.git`）
- [x] 无个人绝对路径、邮箱、手机号、内网地址
- [x] `.gitignore` 覆盖密钥 / 数据 / 缓存 / Agent 工作区 / 归档目录
- [x] 许可证与作者字段不含个人信息
- [x] CI 门禁有效且为最小权限
- [x] 254 项测试通过
- [x] 5 个示例静态 + 运行时全通过
- [x] 多语言 README 与说明文档齐备
- [x] 无用与临时文件已归档
- [x] 首次提交完成（`952d5d4`，98 个文件）
- [ ] ~~推送到远端~~ **受阻：本机代理 502，GitHub 不可达（详见 §6.2）**

---

## 6. 上传执行结果（任务 #16）

### 6.1 已完成

| 步骤 | 结果 |
|---|---|
| 设置提交身份（仅本仓库） | ✅ `LEAP Framework Contributors <leap-framework@users.noreply.github.com>` |
| 首次提交 | ✅ `952d5d4`，98 个文件，30821 行 |
| 暂存内容校验 | ✅ `_archive/` 0 个、`.workbuddy-ai/` 0 个 |
| 工作区 | ✅ 干净 |
| 令牌临时文件 | ✅ 覆写后删除，全仓库零残留 |

### 6.2 未完成：推送

**原因：本机所有 HTTPS 出网被代理拦截，代理返回 502。**

```
$ curl https://api.github.com/user
curl: (56) CONNECT tunnel failed, response 502

$ git ls-remote https://github.com/git/git.git HEAD
fatal: unable to access ...: CONNECT tunnel failed, response 502
```

- 代理地址：`http://127.0.0.1:9918`（由 `HTTPS_PROXY` / `HTTP_PROXY` 注入）
- DNS 正常：`api.github.com` 可正常解析
- 沙箱内外均失败，排除沙箱策略因素
- **问题在代理，不在网络、不在令牌**

会话早期有一次请求成功（拿到账号 `Vinger-lee`），说明代理是**间歇性故障**而非持续封禁。

**结论**：本地准备已 100% 就绪，**仅剩网络这一步**。重试即可完成。

### 6.3 交接

完整的上传指引（含三条可选路径、逐条命令、上传后验证清单）写在：

```
_archive/internal/上传指引.md
```

**推荐路径 C**：用 `gh auth login` 走浏览器授权，**全程不需要明文令牌**。

---

## 7. ⚠️ 令牌安全（务必阅读）

推送后若想改成自己的 GitHub 账号归属，在**别人克隆之前**执行：

```bash
git config --local user.name  "<你的公开显示名>"
git config --local user.email "<你的 GitHub noreply 邮箱>"
git commit --amend --reset-author --no-edit
git push --force-with-lease origin main
```

---

## 8. 若需修改提交身份

对话中粘贴的那枚 GitHub PAT **仍然应当吊销**，无论本次上传是否顺利：

1. 它已经以明文出现在对话记录里，等同于已泄露；
2. 本次上传**不会把它写入仓库任何位置**（已扫描验证），但这不改变它已暴露的事实；
3. 用户提到该令牌有时效限制 —— 时效到期前它仍然是有效凭据。

**建议**：上传完成后立即吊销并重新签发；后续如需自动化，改用**细粒度令牌**（Fine-grained PAT）并只授予目标仓库的 `Contents: Read and write`，而不是全权限账号令牌。
