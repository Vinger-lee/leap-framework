---
title: OSI 七层模型示例使用说明
tags:
- leap/examples
- computer-science/network
aliases:
- OSI 示例说明
---

> [!info] 学习资源
> 核心：`OSI seven layers encapsulation protocols definitions beginner`
> 拓展：`OSI seven layers encapsulation protocols examples conditions`
> 进阶：`OSI seven layers encapsulation protocols proof transfer`

# 示例 3 · OSI 七层职责、边界与跨网封装

语言：简体中文 · [[examples/03-cs-osi-model/README|English guide]]

直接用浏览器打开 `leap-03-cs-osi-model.html`。CSS、JavaScript、SVG全部内联，离线可用，不需要服务器或构建。完整教学内容与解答见 [[examples/03-cs-osi-model/knowledge|知识稿]]；它还补充NAT、TCP字节流、最小帧填充、选项/VLAN等反例。

建议35–50分钟：先读bit/byte、MAC/IP/端口与协议/服务/接口 → 点七层图 → 做八张卡片匹配 → 走13步两跳动画 → 职责辨析与200 byte计算变式 → 提交排错推理。顶部按核心、拓展、进阶提供可复制资源关键词，不把未核验视频当推荐。

本课限定设备具体功能，避免“网卡唯一属于L1”“所有交换机只有L2”。OSI是参考模型，Internet四/五层与它不保证逐项对应；上三层、TLS、UDP、TCP和IP的保证范围均有解释。

动画以100 byte明文HTTP数据为例：已有TCP连接、IPv4无选项、无NAT/分片/VLAN/隧道，两跳均为以太网。展示120 byte段、140 byte数据报、158 byte帧（计至FCS），入口帧去除、TTL64→63、出口G2/B帧重封装与最终交付。L1是信号编码，不新增统一“H1头”；受控示意不等于抓包或波形模拟。

交互支持：

- 两张七层SVG，可点击或Enter查看职责。
- 拖拽匹配或先选卡片再选目标；一层可多张、已放卡片可重移。
- 播放/暂停、向前/向后和重置；键盘快捷键仅在控制区生效。
- 每次重试保存，计算逐项部分计分。
- 排错文字完整采集，宿主语义评估，不用关键词判正确。
- L1/L2/L3主动提示，L4二次确认；展示完整答案后仍须做新变式。

宿主使用 `window.LEAP.hydrate/getInteractionResult/peekOutbox/drainOutbox`。页面队列按钮只预览，不清空。新评分待核验，本地不提升掌握度或证据阶段；活动结束产生 `check_advance_unit`，不等同于Runtime批准推进。标识：`cs.network.osi_model` / `computer-science` / `osi-model`。

`leap-03-cs-osi-model.runtime.json`覆盖SVG、拖拽/点击/键盘归位、改错、所有封装步骤与倒退、路由器字段、播放暂停、重复选择、部分分、语义采集、确认、后置验证和队列/JSON。仓库根目录执行：

```powershell
.venv/quality-runtime/Scripts/python.exe scripts/verify_example.py examples/03-cs-osi-model/leap-03-cs-osi-model.html
.venv/quality-runtime/Scripts/python.exe scripts/verify_example_runtime.py examples/03-cs-osi-model/leap-03-cs-osi-model.html --chromium <path-to-chromium>
```

浏览器验证不等于真实MCP联调或独立学科审校。来源与解答见 [[examples/03-cs-osi-model/knowledge#十、内容依据与维护检查|知识稿]]；流程见 [[docs/content-quality|内容质量流程]]。返回 [[examples/README_CN|示例索引]]。

> [!note]- 复核记录
> 逐项核对条件、原始输入、推导和回执；使用新输入完成迁移，不能把答案揭示作为掌握证据。


Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[examples/03-cs-osi-model/README]] · [[examples/03-cs-osi-model/knowledge]]
