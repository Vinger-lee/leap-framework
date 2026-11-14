---
title: 🎓 LEAP Framework
tags:
- leap
- engineering
aliases:
- 🎓 LEAP Framework guide
canonical_role: full_knowledge_source
delivery_policy: '3.0'
---

> [!info] Learning resources / 学习资源
> Core: `LEAP 🎓 LEAP Framework foundations definitions workflow`
> Extension: `LEAP 🎓 LEAP Framework failure cases examples comparison`
> Advanced: `LEAP 🎓 LEAP Framework invariants verification transfer`
> These are search queries; no video has been certified for this note.

Related: [Knowledge_Index](../../Knowledge_Index.md) · [docs/teaching-delivery](../teaching-delivery.md)

# 🎓 LEAP Framework

<p align="center">
  <img src="https://img.shields.io/github/stars/Vinger-lee/leap-framework?style=social" alt="Stars">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-74%20tools-22bb33" alt="MCP Tools">
  <img src="https://img.shields.io/badge/中文-支持-ff6600" alt="中文支持">
  <br>
  <b>🤖 Дайте вашему ИИ-агенту настоящий тьюторский движок, а не просто промпт.</b>
</p>

<p align="center">
  <a href="../../README.md">English</a> ·
  <a href="../../README_CN.md">中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="README.ar.md">العربية</a>
</p>

---

## 🚀 Что такое LEAP?

**LEAP (Learning Evolution & Adaptation Pipeline) — это тьюторский рантайм, управляемый состоянием, для ИИ-агентов.** Он даёт устойчивый и проверяемый цикл обучения вместо разового промпта «объясни, потом спроси».

- **состояние ученика** и оценка уровня освоения
- **предварительные требования** и можно ли переходить к теме
- **достаточность оценки** и качество свидетельств
- **расписание повторений** и долгосрочное удержание
- **переходы состояния** — ничто не продвигается без серверного State Guard

```bash
# Агент спрашивает LEAP, что делать дальше
get_teaching_context(session_id, "py.recursion.base_case")
# 👉 стратегия: Retrieval Practice · действие: Generate Practice
```

## ⚡ Быстрый старт

```bash
git clone https://github.com/Vinger-lee/leap-framework.git
cd leap-framework
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

```bash
python -m leap.server      # запуск MCP-сервера
```

## 🧠 Цикл обучения

```
1. Определение цели
2. Освоение предметной области
3. Диагностика ученика
4. Представление знаний (DAG)
5. Инициализация состояния
6. Динамический цикл обучения
7. Удержание (повторения FSRS)
8. Перенос (близкий · вариативный · далёкий · интегральный)
9. Рефлексия и сохранение
```

## 🔑 Ключевые механизмы

### 🔒 State Guard

State Guard — единственный компонент, который может разрешить переход. Если инструмент вернул `REJECT`, агент подстраивается под причину, а не продавливает через промпт. Неудачный вызов никогда не превращается в скрытое изменение состояния.

### 📊 Уровень освоения оценивается на сервере

`mastery_probability` — это **оценка модели, а не истинное значение**. Её вычисляет BKT-модель с учётом забывания, а не языковая модель хоста. Поддерживаются частичный балл и снижение веса при низкой уверенности; неопределённость никогда не записывается как `mastery = 0`.

### 🪜 Этапы свидетельств (и они откатываются)

`estimated → practiced → demonstrated → retained → transferred`

Один правильный ответ даёт свидетельство, а не освоение. Этапы **откатываются** после долгого перерыва или неудачи в новом контексте.

## 🔧 Инструменты MCP

[Генерируемый справочник MCP: имена, параметры и профили](../mcp-tools.md).

## 🧩 Подключаемая архитектура

Шесть компонентов разрешаются через реестр плагинов: реализация меняется из `config/default.yaml` без правки вызывающего кода.

| Точка расширения | По умолчанию | Альтернативы |
|---|---|---|
| Оценка состояния | `simplified_bkt` | PFA, DKT, Bayesian, hybrid |
| Агрегация баллов | `weighted` | rubric, model-based |
| Педагогическая политика | `rule_based` | LLM, hybrid, learned |
| Планировщик повторений | `py-fsrs` | any scheduler |
| Хранилище | `sqlite` | PostgreSQL, distributed |
| Хранилище артефактов | `local` | object storage, knowledge base |

## 📚 Подробнее

- [Архитектура](../ARCHITECTURE.md)
- [Руководство по интеграции хостового агента](../INTEGRATION.md)
- [Примеры страниц](../EXAMPLES.md)
- [Локализация](../LOCALIZATION.md)
- [English README](../../README.md) · [中文说明](../../README_CN.md)

> Авторская спецификация фреймворка и визуальная дизайн-система поддерживаются отдельно и не входят в этот репозиторий.

## 📄 Лицензия

[MIT](../../LICENSE) © Vinger-lee

> [!note]- Reading and verification sequence: LEAP 🎓 LEAP Framework
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

## 🤖 Agent Skill (необязательно)

Skill `.agents/skills/leap-tutor/` доступен только в хостах, которые загружают skills из репозитория; поддерживаемый объём — [docs/agent-skill.md](../../docs/agent-skill.md), примеры настройки — [docs/host-config.md](../../docs/host-config.md). Непроверенные хосты не заявляются.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[Knowledge_Index](../../Knowledge_Index.md) · [README](../../README.md) · [README_CN](../../README_CN.md) · [docs/i18n/README.ar](README.ar.md) · [docs/i18n/README.es](README.es.md) · [docs/i18n/README.fr](README.fr.md) · [docs/i18n/README.ja](README.ja.md) · [docs/i18n/README.ko](README.ko.md)
