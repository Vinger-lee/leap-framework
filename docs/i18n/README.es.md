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
  <b>🤖 Dale a tu agente de IA un motor de tutoría real, no solo un prompt.</b>
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

## 🚀 ¿Qué es LEAP?

**LEAP (Learning Evolution & Adaptation Pipeline) es un runtime de tutoría basado en estado para agentes de IA.** Ofrece un bucle de aprendizaje persistente y auditable, en lugar de un único prompt de «explicar y luego preguntar».

- **el estado del estudiante** y la estimación de dominio
- **los prerrequisitos** y si se puede abordar un tema
- **la suficiencia de la evaluación** y la calidad de la evidencia
- **la programación de repasos** y la retención a largo plazo
- **las transiciones de estado** — nada avanza sin pasar el State Guard del servidor

```bash
# El agente pregunta a LEAP qué hacer a continuación
get_teaching_context(session_id, "py.recursion.base_case")
# 👉 estrategia: Retrieval Practice · acción: Generate Practice
```

## ⚡ Inicio rápido

```bash
git clone https://github.com/Vinger-lee/leap-framework.git
cd leap-framework
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

```bash
python -m leap.server      # iniciar el servidor MCP
```

## 🧠 El bucle de aprendizaje

```
1. Definición del objetivo
2. Anclaje de dominio
3. Diagnóstico del estudiante
4. Representación del conocimiento (DAG)
5. Inicialización del estado
6. Bucle de enseñanza dinámico
7. Retención (repaso FSRS)
8. Transferencia (cercana · variante · lejana · integrada)
9. Reflexión y persistencia
```

## 🔑 Mecanismos clave

### 🔒 State Guard

El State Guard es el único componente que puede autorizar una transición. Cuando una herramienta devuelve `REJECT`, el agente se adapta al motivo en lugar de forzar mediante el prompt. Una llamada fallida nunca se convierte en una actualización silenciosa del estado.

### 📊 El dominio se estima en el servidor

`mastery_probability` es una **estimación del modelo, no un valor real**. Se calcula con un modelo BKT que considera el olvido, nunca lo emite el LLM anfitrión. Admite crédito parcial y descuento por baja confianza, y la incertidumbre nunca se escribe como `mastery = 0`.

### 🪜 Etapas de evidencia (y pueden retroceder)

`estimated → practiced → demonstrated → retained → transferred`

Una respuesta correcta produce evidencia, no dominio. Las etapas **retroceden** tras una ausencia prolongada o un fallo en un contexto nuevo.

## 🔧 Herramientas MCP

62 herramientas expuestas por stdio.

| Grupo | Ejemplos |
|---|---|
| Sesión y objetivo | `create_session`, `save_learning_goal`, `set_learning_configuration` |
| Diagnóstico | `generate_diagnostic`, `submit_diagnostic`, `save_diagnostic_result` |
| Conocimiento | `decompose_topic`, `save_knowledge_nodes`, `validate_knowledge_dag` |
| Política | `get_teaching_context`, `evaluate_pedagogical_policy`, `commit_pedagogical_decision` |
| Evaluación | `generate_assessment`, `assess_response`, `assess_misconception` |
| Retención | `schedule_review`, `get_due_reviews`, `submit_review` |
| State Guard | `start_unit`, `check_advance_unit`, `advance_unit`, `rollback_unit` |
| Informes | `generate_final_report`, `get_learning_metrics` |

## 🧩 Diseño conectable

Seis componentes se resuelven mediante un registro de plugins: una implementación se sustituye desde `config/default.yaml` sin tocar el código que la invoca.

| Punto de extensión | Por defecto | Alternativas |
|---|---|---|
| Estimación de estado | `simplified_bkt` | PFA, DKT, Bayesian, hybrid |
| Agregación de puntuaciones | `weighted` | rubric, model-based |
| Política pedagógica | `rule_based` | LLM, hybrid, learned |
| Planificador de repasos | `py-fsrs` | any scheduler |
| Almacenamiento | `sqlite` | PostgreSQL, distributed |
| Almacén de artefactos | `local` | object storage, knowledge base |

## 📚 Saber más

- [[docs/ARCHITECTURE|Arquitectura]]
- [[docs/INTEGRATION|Guía de integración del agente anfitrión]]
- [[docs/EXAMPLES|Páginas de ejemplo]]
- [[docs/LOCALIZATION|Internacionalización]]
- [[README|English README]] · [[README_CN|中文说明]]

> La especificación de diseño de referencia y el sistema de diseño visual los mantiene el autor del proyecto por separado y no forman parte de este repositorio.

## 📄 Licencia

[MIT](../../LICENSE) © Vinger-lee

> [!note]- Reading and verification sequence: LEAP 🎓 LEAP Framework
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[README]] · [[README_CN]] · [[docs/i18n/README.ar]] · [[docs/i18n/README.fr]] · [[docs/i18n/README.ja]] · [[docs/i18n/README.ko]] · [[docs/i18n/README.ru]]
