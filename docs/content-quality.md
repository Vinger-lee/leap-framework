# 内容质量与接入验收

LEAP 是教学状态 Runtime。领域学习、资料检索、出题和自由文本语义评分由宿主 Agent 执行；Runtime 不包含通用学科判题模型。保存报告、通过 JSON Schema、浏览器无报错，都不等于教材和答案正确。

## 1. 先确认真实连接

先通过宿主连接器调用 `get_available_actions`，保留成功响应。读取规范、复制示例、模拟 `get_teaching_context` 只能证明本地开发流程。客户端没有注册 `leap` 时，交付说明必须写明尚未接入；不要声称已调用 MCP。

客户端注册路径与信任操作取决于宿主产品。本项目不会修改客户端配置或替用户点击信任。

## 2. 自学必须留下可审阅证据

宿主先用自己的文件/浏览器/搜索工具阅读领域资料，再调用 `save_benchmark_report`。优先选原始教材、官方文档、权威定义；考试目标需要有适用年份和版本的大纲。没有读到大纲时，不得自称“最新考纲对齐”，也不得编造“每年至少一题”等统计。

`source_refs` 每项需要 `source`、`source_type`、`locator`、`excerpt`。`locator` 可以是章节、页码、文档小节或稳定 URL；`excerpt` 是实际读到的相关内容。报告的 `verification` 字段结构如下：

```json
{
  "scope": "本次学习的专题、版本、前置条件与不覆盖的范围",
  "claims": [
    {"claim": "带条件的核心论断", "source_index": 0}
  ],
  "worked_examples": [
    {
      "problem": "题目与条件",
      "solution": "完整推导与结论",
      "check_method": "代回、独立推导、符号验证或可执行测试",
      "check_result": "实际结果及其适用边界"
    }
  ],
  "limitations": ["未查阅最新考试大纲；不能承诺题频与分值"]
}
```

`source_index` 指向本次 `source_refs` 的下标。仅传文字报告或缺失证据时，报告仍会保存以便补充，但 `domain_grounding_stage` 保持 `pending`，响应列出 `missing_evidence`。

诊断、出题蓝图、迁移蓝图、教学上下文、开始单元、提交作答、提交评估都检查领域校准。旧版只有文字报告的会话需要补充证据。显式允许跳过的会话保留原有豁免；Agent 不得为了绕过拒绝而自行开启这个开关。

这些检查只保证证据记录存在，不能认证宿主真的读取过来源，也不能认证摘录真实或论断正确。要求更强的来源证明时，应由宿主保存实际读取工具日志和材料快照；不得把 `content_verified_by_runtime: false` 描述成已通过学科验证。`validate_claim` 的 `verified` 只涉及来源关联，见 `verification_scope: source_linkage_only`。

## 3. 出题前逐题复核并登记

使用 `save_assessment_item` 登记题目，保存 `question`、`expected_answer`、`solution`、`assumptions`、`verification_checks`；建议同时保存 `source_ids` 和 `rejected_answers`。题目 ID 不可覆盖，修改题意或答案时使用新版本 ID。

逐题检查：

1. 定义域、量词、极限方向、参数范围和定理条件是否齐全。
2. 独立解答后代回；另用一种方法复核关键结论。数值抽样只支持样本结论，不能证明“恒成立”。
3. 单选题是否恰好一个正确选项；不同写法表示同一个集合或公式时，不得把其中一种判错。
4. 正确答案、推导、提示、反馈和后置变式是否一致。不要只测标准答案，还要测反例、否定句、错误数值、同义改写。
5. 排序题是否有真正的依赖关系；逻辑上可交换的步骤不能强行按唯一顺序判错。

`verification_checks` 至少包含一个带 `method` 和 `result` 的独立检查记录。这是内容复核的记录入口，不是数学证明器。错误的复核记录仍可能被宿主提交，需由内容审校发现。

`assessor_scope` 的取值为 `exact_answer`、`numeric_tolerance`、`executable_test`、`host_semantic_review`。自由文本默认最后一种；`commit_assessment(..., assessor_type="rule")` 不得为这类题目写入成绩。宿主必须阅读原始作答，检查否定、条件、计算与推理，再以 model/human/hybrid 提交经过语义审阅的评分。不能把“包含连续二字”当成“正确理解连续”。

带 `item_id` 的作答须引用本会话已登记题目。Runtime 会拒绝未登记或跨会话引用，避免页面第一次真实调用时才遇到 SQLite 外键错误。原有不传 `item_id` 的通用作答仍受支持；因此本入口不能强制宿主在 Runtime 外生成的所有内容都接受审校。

## 4. 页面到 Runtime 的闭环

1. 宿主从 `get_teaching_context` 读取上下文并调用 `LEAP.hydrate(ctx)`。
2. 页面采集动作，`submit_attempt` 在前，`commit_assessment` 在后。宿主依次执行并替换 `{{call_N.attempt_id}}` 引用。
3. 后置验证必须提交自己的 attempt，不能把分数挂到上一题；`raw_answer` 必须与所引用 attempt 的原文一致。
4. 对自由文本题，宿主先语义审阅再执行评分调用；页面给出的本地分数只是候选反馈。
5. 每条调用检查 `ok`，失败不能默默推进；提交后重新读取上下文回填页面。
6. `item_completed` 只表示页面活动完成，产生 `check_advance_unit`；宿主在 guard 允许时才提议 `advance_unit`，后者仍由服务端裁决。

demo 模式也不得推算掌握度和证据阶段，只保留初始占位值。`provisional` 表示本地评估尚未获 Runtime 确认；单纯切换 hosted 模式不能确认新分数。查看 outbox 使用 `peekOutbox`，只有执行方领取队列才使用 `drainOutbox`。`drainOutbox` 是取走接口，并无持久重试/确认机制，执行方应先保存领取结果，失败时保留待重试调用及依赖关系。

## 5. 分开报告三种验收

```bash
python scripts/verify_example.py --all
python scripts/verify_example_runtime.py --all --json runtime-verification.json
python scripts/verify_mcp_bridge.py
python scripts/generate_tool_reference.py --check
pytest
```

浏览器运行校验读取与 HTML 同名的 `.runtime.json` 场景清单。每个场景从重新加载页面开始，明确操作和断言；缺失清单是失败。清单覆盖哪些路径才能声称哪些路径通过，不能从几次按钮点击推导“所有交互正确”。

`verify_mcp_bridge.py` 启动真正的 MCP stdio 子进程，用 Chromium 操作数学示例，在临时 SQLite 中登记题目、提交原始作答、提交评分、执行完成检查并回填状态。使用的是明确标注的合成测试材料；它不证明真实学科来源已经阅读，也不改变 WorkBuddy 等客户端配置。

这两项均不验证学科内容。交付还需要独立的内容审校记录，列出材料版本、逐题答案和复核结果、未解决的不确定性。运行测试次数不能替代这份记录。
