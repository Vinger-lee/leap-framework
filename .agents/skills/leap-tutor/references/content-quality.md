# 内容制作与验收

制作或更新内容时获取一次 `get_teaching_delivery_policy()`，遵循当前返回的政策、
manifest 契约和工具 schema；回包为紧凑 envelope（`policy_version`），不要每轮
重复取完整政策。需要教学点模板时调用 `get_teaching_context(include_template=True)`
一次，不要每轮把模板带回合上下文。政策应用于所有学科和模式，不因 core_only 降级。

## 实际来源与独立检查

- 实际阅读 `get_grounding_sources()` 返回的每个来源定位，独立解答检查题，
  核对教材版本、主张条件、推导和反例，并在 `report_text` 记录阅读与复核。
- `save_benchmark_report()` 使用返回的课程版本、全部片段 ID 和独立解答，
  来源与审核日期由版本化来源包提供。保留回执和版本以便续学。
- 结构检查与来源版本匹配只说明登记符合 Runtime 规则。独立的阅读和复核仍是宿主任务。
- 正式题目独立求解并另法复核；检查定义域、量词、定理条件、参数、边界和反例。
  单选题只有一个正确选项；接受等价表示和不同有效推理。数值抽样不能证明恒成立。

## Markdown、HTML 与 manifest

1. 校准后从 `get_grounding_sources(session_id, include_lesson=True)` 读取预审
   Markdown、HTML、manifest 和题目，按[生命周期](lifecycle.md)原样登记。
   检查 `validation` 和实际 `package_id`，登记题目时使用该 ID 与预审条目的来源 ID。
2. 交付交互页前按适用功能检查鼠标、键盘、触摸、公式、同步读数、静态/减少动态效果、
   宽屏和手机布局。查看部件只改变展示。报告实际完成的浏览器检查。
3. 新编解释、题目或图解可用 `save_artifact()`（full only），传
   `artifact_type="teaching_draft"`，保存为待审草稿。正式内容的变更由维护者复核并
   随来源包发布。制作草稿时继续使用完整 Markdown、派生离线 HTML 和当前视觉契约。

完整交互规范可用 `get_web_component_spec()`（full only）。quickstart 以当前
交付政策为准；如任务需要该档位未提供的规范或页面桥接工具，应调整档位或报告
能力缺口。不要向页面伪造调用回执。

## 作答和页面证据

开放式答案逐项检查定义、否定、条件、计算、逻辑步骤与等价表达；支持不足的
评分维度留空或说明不确定性。`commit_assessment()` 必须引用该作答的原始全文。

现有示例页面的 outbox 使用细粒度工具；需要完整页面桥接时选择 full。
取走 outbox 后由宿主保留调用与依赖，逐条核对回执再交回页面。新评分须匹配
本次 attempt；快照不能代替新评分回执。guard 允许与实际推进分开确认，本地
交互、候选分数和查看图解都不能确认掌握或结课。

分别报告结构验收、来源关联、学科内容审阅和浏览器验证，不把 Runtime 接受
描述为来源真实性、科学正确性或学习效果认证。
