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

Related: [[Knowledge_Index]] · [[docs/teaching-delivery]]

# 🎓 LEAP Framework

<p align="center">
  <img src="https://img.shields.io/github/stars/Vinger-lee/leap-framework?style=social" alt="Stars">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-70%20tools-22bb33" alt="MCP Tools">
  <img src="https://img.shields.io/badge/中文-支持-ff6600" alt="中文支持">
  <br>
  <b>🤖 Дайте вашему ИИ-агенту настоящий тьюторский движок, а не просто промпт.</b>
</p>

<p align="center">
  [[README|English]] ·
  [[README_CN|中文]] ·
  [[docs/i18n/README.ja|日本語]] ·
  [[docs/i18n/README.ko|한국어]] ·
  [[docs/i18n/README.fr|Français]] ·
  [[docs/i18n/README.es|Español]] ·
  [[docs/i18n/README.ru|Русский]] ·
  [[docs/i18n/README.ar|العربية]]
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

70 инструментов через stdio.

| Группа | Примеры |
|---|---|
| Сессия и цель | `create_session`, `save_learning_goal`, `set_learning_configuration` |
| Диагностика | `generate_diagnostic`, `submit_diagnostic`, `save_diagnostic_result` |
| Знания | `decompose_topic`, `save_knowledge_nodes`, `validate_knowledge_dag` |
| Политика | `get_teaching_context`, `evaluate_pedagogical_policy`, `commit_pedagogical_decision` |
| Оценка | `generate_assessment`, `assess_response`, `assess_misconception` |
| Удержание | `schedule_review`, `get_due_reviews`, `submit_review` |
| State Guard | `start_unit`, `check_advance_unit`, `advance_unit`, `rollback_unit` |
| Отчёты | `generate_final_report`, `get_learning_metrics` |

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

- [[docs/ARCHITECTURE|Архитектура]]
- [[docs/INTEGRATION|Руководство по интеграции хостового агента]]
- [[docs/EXAMPLES|Примеры страниц]]
- [[docs/LOCALIZATION|Локализация]]
- [[README|English README]] · [[README_CN|中文说明]]

> Авторская спецификация фреймворка и визуальная дизайн-система поддерживаются отдельно и не входят в этот репозиторий.

## 📄 Лицензия

[MIT](../../LICENSE) © Vinger-lee

> [!note]- Reading and verification sequence: LEAP 🎓 LEAP Framework
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[README]] · [[README_CN]] · [[docs/i18n/README.ar]] · [[docs/i18n/README.es]] · [[docs/i18n/README.fr]] · [[docs/i18n/README.ja]] · [[docs/i18n/README.ko]]
