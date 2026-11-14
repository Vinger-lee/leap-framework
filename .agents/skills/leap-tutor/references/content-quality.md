# 内容制作与验收

制作或更新内容时获取一次 `get_teaching_delivery_policy()`，遵循当前返回的政策、
manifest 契约和工具 schema；回包为紧凑 envelope（`policy_version`），不要每轮
重复取完整政策。需要教学点模板时调用 `get_teaching_context(include_template=True)`
一次，不要每轮把模板带回合上下文。政策应用于所有学科和模式，不因 core_only 降级。

## 实际来源与独立检查

- 实际阅读后才记录 source、source_type、locator、excerpt；不编造章节、页码
  或最新考纲适配。限制中说明未读到、无法验证或版本不符的内容。
- `save_benchmark_report()` 的 verification 包含 scope、带 source_index 的
  claims、worked_examples（problem/solution/check_method/check_result）和
  limitations。source_index 引用本次提交来源下标；保存返回的 sources_saved。
- 校验结构只能说明记录符合规则，不能证明实际阅读或学科真伪。
- 正式题目独立求解并另法复核；检查定义域、量词、定理条件、参数、边界和反例。
  单选题只有一个正确选项；接受等价表示和不同有效推理。数值抽样不能证明恒成立。

## Markdown、HTML 与 manifest

1. 写完整 canonical Obsidian Markdown，包含前置、机制和条件、完整推导、
   检查过的例题、误解、边界、比较、梯度练习、迁移及解析。
2. 再派生离线 HTML，覆盖一致的教学内容并保留 Markdown 扩展。双方顶部有
   核验过的相关视频或 core/extension/advanced 精确检索词及适用的互链。
   检索词不能描述为已核验视频，HTML 不替代完整知识源。
3. manifest 提供实际 teaching_points、resources、html_segments、
   markdown_extensions 和同会话 source_ids；可视化 selector 必须对应真实元素。
4. 新建或修改图解按 `get_teaching_delivery_policy()` 返回的当前视觉契约先研究与建模，再
   构造图形。保存真实结构/形式来源及 evidence_source_id，映射部件或状态、
   连接关系、假设与限制，独立复核典型和边界结果。所有读数共用领域状态。
5. 部件说明适用时：悬停/聚焦预览；点击、Enter、Space、触摸选择；离开恢复
   选择；Escape/清除恢复总览。查看部件不改变模型状态或学习证据。
6. 注册前实际测试鼠标、键盘、触摸、控制器、公式、代码、同步读数、静态/减少
   动态效果、宽屏和手机布局。报告测试范围，不把静态检查说成浏览器已执行。
7. `save_teaching_package()` 必须提交完整 markdown、html 与 manifest 正文，
   不能只传路径或“已验证”声明。读取 validation 和 package_id，修复真实缺失项。
8. 接受后才 `save_assessment_item()`，关联 teaching_package_id、同会话
   source_ids，并保存解答、条件与独立 verification_checks。开放式题的
   assessor_scope 为 host_semantic_review。
9. 内容实质变化时重登记教学包；题目 ID 不可覆盖，变更题意或答案用新版本 ID。

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
