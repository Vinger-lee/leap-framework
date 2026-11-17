---
title: "高数来源库实施计划"
tags: ["leap", "grounding", "calculus"]
aliases: ["Grounded calculus implementation plan"]
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] 学习资源
> [OpenStax Calculus Volume 1，导数定义](https://openstax.org/books/calculus-volume-1/pages/3-1-defining-the-derivative)
> [LangGraph Python Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)

# 高数来源库实施计划

> [!note]- 验收依据
> 按[已确认设计](../specs/2026-11-15-grounded-calculus-design.md)验证同一来源版本贯穿校准、课堂与派生材料。

- [x] 在 `tests/test_grounded_calculus.py` 建立红灯。两档真实 MCP 均拒绝格式齐全的假来源与跳过校准。测试使用独立 SQLite。补测旧报告恢复、跨课复用及过期。
- [x] 在 `src/leap/runtime/grounding.py` 加载并校验版本化来源包，使用 LangChain `Document` 提供基于教学点的检索，使用 LangGraph 执行解析、检索和验证。
- [x] 接入 `src/leap/tools/evidence.py`、State Guard 和会话路由。正式服务默认使用预审证据，回执绑定包哈希、证据片段及例题检查。旧报告保留历史用途。
- [x] 接入课程制品、题目、复习和打印入口。高数首包包括极限、导数定义、可导性，正式交付物按已审版本校验，宿主新增内容留在草稿。
- [x] 增加维护者复核命令与运行手册。验证过期、撤回、原始来源变化、离线和并发重试。旧示例使用显式测试夹具完成独立的结构验收。
- [x] 在两档真实 MCP 验证高数来源门禁及跨档恢复，再运行 pytest、仓库门禁、文档生成和隐私检查。

Related: [[Knowledge_Index]]
