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
  <img src="https://img.shields.io/badge/MCP-71%20tools-22bb33" alt="MCP Tools">
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

[مرجع أدوات MCP المُولَّد: الأسماء والمعاملات وملفات الأدوات](../mcp-tools.md).

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

- [البنية](../ARCHITECTURE.md)
- [دليل تكامل الوكيل المضيف](../INTEGRATION.md)
- [صفحات الأمثلة](../EXAMPLES.md)
- [التعدد اللغوي](../LOCALIZATION.md)
- [English README](../../README.md) · [中文说明](../../README_CN.md)

> مواصفة التصميم المرجعية ونظام التصميم البصري يحتفظ بهما مؤلف المشروع بشكل منفصل وليسا جزءًا من هذا المستودع.

## 📄 الترخيص

[MIT](../../LICENSE) © Vinger-lee

> [!note]- Reading and verification sequence: LEAP 🎓 LEAP Framework
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

## 🤖 Agent Skill (اختياري)

تتوفر مهارة `.agents/skills/leap-tutor/` فقط في المضيفين الذين يحمّلون مهارات المستودع؛ راجع [docs/agent-skill.md](../../docs/agent-skill.md) لنطاق الدعم و[docs/host-config.md](../../docs/host-config.md) لنماذج إعداد `mcpServers`. لا توجد ادعاءات بشأن مضيفين غير مُتحقق منهم.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[Knowledge_Index](../../Knowledge_Index.md) · [README](../../README.md) · [README_CN](../../README_CN.md) · [docs/i18n/README.es](README.es.md) · [docs/i18n/README.fr](README.fr.md) · [docs/i18n/README.ja](README.ja.md) · [docs/i18n/README.ko](README.ko.md) · [docs/i18n/README.ru](README.ru.md)
