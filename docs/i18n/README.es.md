# 🎓 LEAP Framework

<p align="center">
  <img src="https://img.shields.io/github/stars/Vinger-lee/leap-framework?style=social" alt="Stars">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-58%20tools-22bb33" alt="MCP Tools">
  <img src="https://img.shields.io/badge/中文-支持-ff6600" alt="中文支持">
  <br>
  <b>🤖 Dale a tu agente de IA un motor de tutoría real, no solo un prompt.</b>
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

58 herramientas expuestas por stdio.

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

- [Arquitectura](../../docs/ARCHITECTURE.md)
- [Guía de integración del agente anfitrión](../../docs/INTEGRATION.md)
- [Páginas de ejemplo](../../docs/EXAMPLES.md)
- [Internacionalización](../../docs/LOCALIZATION.md)
- [English README](../../README.md) · [中文说明](../../README_CN.md)

> La especificación de diseño de referencia y el sistema de diseño visual los mantiene el autor del proyecto por separado y no forman parte de este repositorio.

## 📄 Licencia

[MIT](../../LICENSE) © Vinger-lee
