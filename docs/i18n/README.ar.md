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
  <img src="https://img.shields.io/badge/MCP-62%20tools-22bb33" alt="MCP Tools">
  <img src="https://img.shields.io/badge/中文-支持-ff6600" alt="中文支持">
  <br>
  <b>🤖 امنح وكيل الذكاء الاصطناعي محرك تعليم حقيقيًا لا مجرد تعليمة برمجية.</b>
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

## 🚀 ما هو LEAP؟

**LEAP (Learning Evolution & Adaptation Pipeline) هو وقت تشغيل تعليمي موجَّه بالحالة لوكلاء الذكاء الاصطناعي.** يوفّر حلقة تعلّم دائمة وقابلة للتدقيق، بدلًا من تعليمة واحدة بأسلوب «اشرح ثم اختبر».

- **حالة المتعلّم** وتقدير مستوى الإتقان
- **المتطلبات السابقة** وإمكانية الدخول إلى موضوع ما
- **كفاية التقييم** وجودة الأدلة
- **جدولة المراجعة** والحفظ طويل الأمد
- **انتقالات الحالة** — لا يتقدّم شيء دون اجتياز State Guard على الخادم

```bash
# يسأل الوكيل LEAP عن الخطوة التالية
get_teaching_context(session_id, "py.recursion.base_case")
# 👉 الاستراتيجية: Retrieval Practice · الإجراء: Generate Practice
```

## ⚡ البدء السريع

```bash
git clone https://github.com/Vinger-lee/leap-framework.git
cd leap-framework
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

```bash
python -m leap.server      # تشغيل خادم MCP
```

## 🧠 حلقة التعلّم

```
1. تحديد الهدف
2. تأصيل المجال
3. تشخيص المتعلّم
4. تمثيل المعرفة (DAG)
5. تهيئة حالة المتعلّم
6. حلقة التعليم الديناميكية
7. الحفظ (مراجعة FSRS)
8. النقل (قريب · متنوّع · بعيد · متكامل)
9. التأمل والحفظ
```

## 🔑 الآليات الأساسية

### 🔒 State Guard

State Guard هو المكوّن الوحيد المخوّل بالسماح بانتقال الحالة. عندما تُرجع أداة `REJECT`، يتكيّف الوكيل مع السبب بدلًا من الإلحاح عبر التعليمة. لا يتحوّل الاستدعاء الفاشل أبدًا إلى تحديث صامت للحالة.

### 📊 يُقدَّر الإتقان على الخادم

`mastery_probability` هو **تقدير نموذجي، وليس قيمة حقيقية**. تحسبه نموذج BKT يراعي النسيان ولا تصدره أبدًا نموذج اللغة المضيف. يدعم الرصيد الجزئي وتخفيض الوزن عند انخفاض الثقة، ولا تُسجَّل حالة «عدم اليقين» أبدًا كـ `mastery = 0`.

### 🪜 مراحل الأدلة (وقد تتراجع)

`estimated → practiced → demonstrated → retained → transferred`

الإجابة الصحيحة مرة واحدة تُنتج دليلًا واحدًا لا إتقانًا. **تتراجع** المراحل بعد غياب طويل أو فشل في سياق جديد.

## 🔧 أدوات MCP

62 أداة عبر stdio.

| المجموعة | أمثلة |
|---|---|
| الجلسة والهدف | `create_session`, `save_learning_goal`, `set_learning_configuration` |
| التشخيص | `generate_diagnostic`, `submit_diagnostic`, `save_diagnostic_result` |
| المعرفة | `decompose_topic`, `save_knowledge_nodes`, `validate_knowledge_dag` |
| السياسة | `get_teaching_context`, `evaluate_pedagogical_policy`, `commit_pedagogical_decision` |
| التقييم | `generate_assessment`, `assess_response`, `assess_misconception` |
| الحفظ | `schedule_review`, `get_due_reviews`, `submit_review` |
| State Guard | `start_unit`, `check_advance_unit`, `advance_unit`, `rollback_unit` |
| التقارير | `generate_final_report`, `get_learning_metrics` |

## 🧩 تصميم قابل للاستبدال

تُحلّ ستة مكوّنات عبر سجل إضافات، فيمكن استبدال التنفيذ من `config/default.yaml` دون تعديل الكود المستدعي.

| نقطة الامتداد | الافتراضي | البدائل |
|---|---|---|
| تقدير الحالة | `simplified_bkt` | PFA, DKT, Bayesian, hybrid |
| تجميع الدرجات | `weighted` | rubric, model-based |
| السياسة التعليمية | `rule_based` | LLM, hybrid, learned |
| جدولة المراجعة | `py-fsrs` | any scheduler |
| التخزين | `sqlite` | PostgreSQL, distributed |
| مخزن العناصر | `local` | object storage, knowledge base |

## 📚 للمزيد

- [[docs/ARCHITECTURE|البنية]]
- [[docs/INTEGRATION|دليل تكامل الوكيل المضيف]]
- [[docs/EXAMPLES|صفحات الأمثلة]]
- [[docs/LOCALIZATION|التعدد اللغوي]]
- [[README|English README]] · [[README_CN|中文说明]]

> مواصفة التصميم المرجعية ونظام التصميم البصري يحتفظ بهما مؤلف المشروع بشكل منفصل وليسا جزءًا من هذا المستودع.

## 📄 الترخيص

[MIT](../../LICENSE) © Vinger-lee

> [!note]- Reading and verification sequence: LEAP 🎓 LEAP Framework
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[README]] · [[README_CN]] · [[docs/i18n/README.es]] · [[docs/i18n/README.fr]] · [[docs/i18n/README.ja]] · [[docs/i18n/README.ko]] · [[docs/i18n/README.ru]]
