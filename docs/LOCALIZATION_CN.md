---
title: 多语言与本地化
tags: [leap, engineering, i18n]
aliases: [LEAP 简体中文本地化指南]
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] 学习资源
> 核心：`Python 字典消息目录 本地化 消息键`
> 拓展：`语言回退 占位符一致性 环境变量配置`
> 进阶：`gettext Babel 复数规则 日期格式 国际化`
> 这些是检索建议，未声称已核验相关视频。

关联：[[Knowledge_Index]] · [[docs/teaching-delivery]] · [[docs/LOCALIZATION]] · [[docs/ARCHITECTURE_CN]]

# 多语言与本地化

**语言**：简体中文 ｜ [[docs/LOCALIZATION|English]]

LEAP 由宿主 Agent 调用。学习者和操作者实际看到的消息使用消息目录，机器接口标识保持稳定。

## 1. 本地化范围

| 翻译内容 | 保持稳定的内容 |
|---|---|
| 状态守卫的拒绝原因 | 代码注释、日志、异常类型 |
| 领域校准提示 | 工具名、字段名、枚举值 |
| 学习模式名称与描述 | 内部审计使用的策略理由 |
| 结课报告标题与章节 | 内部 Bloom 层级标识，如 `apply` |

翻译工具名或字段名会破坏宿主集成。完整接口参考见 [[docs/mcp-tools]]。

## 2. 选择语言

在配置中选择语言：

```yaml
# config/default.yaml
locale: zh-CN
```

进程环境可以通过配置覆盖机制选择英语：

```bash
LEAP__LOCALE=en python -m leap.server
```

PowerShell 的对应写法：

```powershell
$env:LEAP__LOCALE = 'en'
python -m leap.server
```

语言解析顺序为：有效的配置 `locale` → `LEAP_LOCALE` → `LC_ALL` / `LC_MESSAGES` / `LANG` → 默认 `zh-CN`。
`LEAP__LOCALE` 先覆盖配置，所以能覆盖 `default.yaml` 中的显式语言；`LEAP_LOCALE` 只在配置没有有效语言时生效。

支持别名 `zh`、`zh-CN`、`zh_Hans`、`cn`、`中文`、`en`、`en-US`、`english`，解析时忽略大小写和下划线差异。

## 3. 在代码中读取消息

工具实现可直接使用上下文中的翻译器：

```python
msg = self.t("domain_grounding.notice")
```

其他位置可从配置构造翻译器：

```python
from leap.i18n import translator_for

translator = translator_for(cfg)
msg = translator.t("report.title")
```

消息查找顺序为：当前语言 → 默认语言 → 消息键本身。缺少翻译不会抛出异常；占位符格式化失败时返回原始模板。

## 4. 添加语言

1. 在 `src/leap/i18n.py` 的 `SUPPORTED_LOCALES` 中增加语言代码。
2. 在 `MESSAGES` 中添加与默认语言拥有完全相同消息键的目录。
3. 在 `_LOCALE_ALIASES` 中添加常见语言别名。
4. 运行 `python -m pytest tests/test_i18n.py`，然后按 [[CONTRIBUTING|贡献指南]] 完成验证。

测试检查各目录的消息键集合一致、占位符一致且没有空消息。新增 `{name}` 等变量时，各语言必须同时更新。

## 5. 消息目录的实现选择

当前消息数量较少。字典和一个 `t()` 函数便于阅读，不引入额外运行时依赖，也能直接测试键集合与占位符约束。
如果未来需要大量消息、复数规则或日期格式，可迁移到 gettext / Babel，同时保留 `Translator.t()` 调用入口。

## 6. 相关文件

| 文件 | 用途 |
|---|---|
| `src/leap/i18n.py` | 消息目录、语言解析和翻译器 |
| `config/default.yaml` | 默认语言 |
| `tests/test_i18n.py` | 消息目录完整性与语言行为测试 |
| [[docs/LOCALIZATION]] | 英文说明 |

> [!note]- 验证记录
> 分别使用中文与英语配置运行消息查询，核对拒绝原因、报告标题和占位符。
> 删除一个翻译键时应回退到默认语言；两种目录都没有该键时，应显示消息键本身。
> 语言变化不应改变工具名、字段名或枚举值。

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[docs/ARCHITECTURE_CN]] · [[docs/LOCALIZATION]]
