# 🎓 LEAP Framework

<p align="center">
  <img src="https://img.shields.io/github/stars/Vinger-lee/leap-framework?style=social" alt="Stars">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-58%20tools-22bb33" alt="MCP Tools">
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

58 инструментов через stdio.

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

- [Архитектура](../../docs/ARCHITECTURE.md)
- [Руководство по интеграции хостового агента](../../docs/INTEGRATION.md)
- [Примеры страниц](../../docs/EXAMPLES.md)
- [Локализация](../../docs/LOCALIZATION.md)
- [English README](../../README.md) · [中文说明](../../README_CN.md)

> Авторская спецификация фреймворка и визуальная дизайн-система поддерживаются отдельно и не входят в этот репозиторий.

## 📄 Лицензия

[MIT](../../LICENSE) © Vinger-lee
