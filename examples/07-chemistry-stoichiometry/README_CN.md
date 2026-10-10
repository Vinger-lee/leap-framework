---
title: 配平与限制反应物示例使用说明
tags:
- leap/examples
- chemistry/stoichiometry
aliases:
- 化学计量示例说明
---

> [!info] 学习资源
> 核心：`化学方程式 配平 系数 下标 区别`；`物质的量 mol 摩尔质量 n m M`。
> 拓展：`限制反应物 n 除以 系数 理论产量 剩余量`。
> 进阶：`OpenStax Chemistry 2e reaction yields reaction extent`；`BIPM mole Avogadro constant`。
> 这些是检索关键词，实际读取的权威文字资料见 [[examples/07-chemistry-stoichiometry/sources|来源记录]]。

# 示例7 · 化学配平与限制反应物

语言：简体中文 · [[examples/07-chemistry-stoichiometry/README|English guide]]

直接打开 `leap-07-chemistry-stoichiometry.html`，CSS、JavaScript、MathML、SVG与LEAP桥接内核全部内联，离线可用。完整教学与解答见 [[examples/07-chemistry-stoichiometry/knowledge|知识稿]]；实际读取BIPM和OpenStax的范围见 [[examples/07-chemistry-stoichiometry/sources|来源记录]]。

建议35–50分钟，先修为分子式、比值和单位换算。路线：系数/下标 → 原子守恒 → mol比与质量比 → g转mol → 比较n/系数 → 理论产量与剩余 → 理想模型边界。页面资源按核心、拓展、进阶提供关键词，不把未核验视频当推荐。

教学用2H₂+O₂→2H₂O，摩尔质量固定学校近似2.00、32.0、18.0 g/mol。整数粒子工具每整份消耗2氢/1氧生成2水；宏观计算器可用小数mol、不取整。默认6g氢/32g氧：氧限制、水36g、剩氢2g，38=36+2核对质量。

交互包括：

- H₂/O₂整数粒子滑块，SVG同步显示剩余与产物、原子总数。
- 播放/暂停、反应一份、上一步、恢复；改滑块重置旧进度。
- 宏观g→mol→ξ→g计算器，氢限制与恰好比例预设。
- 空/负/超范围输入校验，零理论产量与产率分母边界。
- 配平最简正整数题：倍数守恒给部分分并提示约分。
- 限制物、水量与剩余量客观题，概念辨析，保存所有重试。
- 完整文字解释采集，宿主语义审阅，关键词不判分。
- 主动递进提示、二次确认完整答案、新的后置变式。

桥接由内联 `examples/_shared/bridge-kernel.js` 的 `createLeapBridge(config)` 创建。宿主hydrate上下文、取契约、peek预览、drain取走调用；新客观评估provisional，其他维度未评估，item专属attempt引用。活动结束只请求guard检查，Runtime回执决定是否推进。标识：`chem.stoichiometry.limiting` / `chemistry` / `stoichiometry`。

浏览器场景在 `leap-07-chemistry-stoichiometry.runtime.json`：全117组粒子参数及各整份守恒、小数mol/零/过量/恰好质量、输入边界、部分分改错、文字采集、提示确认、后置验证与宿主桥。仓库根目录执行：

```powershell
.venv/quality-runtime/Scripts/python.exe scripts/verify_example.py examples/07-chemistry-stoichiometry/leap-07-chemistry-stoichiometry.html
.venv/quality-runtime/Scripts/python.exe scripts/verify_example_runtime.py examples/07-chemistry-stoichiometry/leap-07-chemistry-stoichiometry.html --chromium <path-to-chromium>
```

这些检查不等于真实MCP联调或实际实验，理想计量不预测机理、速率、温度、点火或平衡。内容审阅流程见 [[docs/content-quality|内容质量流程]]；返回 [[examples/README_CN|全部示例]]。

> [!note]- 复核与适用范围
> 整数粒子按完整份计数，宏观mol不取整；守恒核对需包含剩余物。题目与参数都属于给定理想模型，浏览器通过不构成实验结论；学习进度仍由Runtime回执决定。

Related: [[Knowledge_Index]]


Related: [[docs/teaching-delivery]]

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[examples/07-chemistry-stoichiometry/README]] · [[examples/07-chemistry-stoichiometry/knowledge]] · [[examples/07-chemistry-stoichiometry/sources]]
