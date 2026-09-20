# 🎓 LEAP Framework

<p align="center">
  <img src="https://img.shields.io/github/stars/Vinger-lee/leap-framework?style=social" alt="Stars">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-58%20tools-22bb33" alt="MCP Tools">
  <img src="https://img.shields.io/badge/中文-支持-ff6600" alt="中文支持">
  <br>
  <b>🤖 امنح وكيل الذكاء الاصطناعي محرك تعليم حقيقيًا لا مجرد تعليمة برمجية.</b>
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

58 أداة عبر stdio.

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

- [البنية](../../docs/ARCHITECTURE.md)
- [دليل تكامل الوكيل المضيف](../../docs/INTEGRATION.md)
- [صفحات الأمثلة](../../docs/EXAMPLES.md)
- [التعدد اللغوي](../../docs/LOCALIZATION.md)
- [English README](../../README.md) · [中文说明](../../README_CN.md)

> مواصفة التصميم المرجعية ونظام التصميم البصري يحتفظ بهما مؤلف المشروع بشكل منفصل وليسا جزءًا من هذا المستودع.

## 📄 الترخيص

[MIT](../../LICENSE) © Vinger-lee
