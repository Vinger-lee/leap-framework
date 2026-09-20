# 🎓 LEAP Framework

<p align="center">
  <img src="https://img.shields.io/github/stars/Vinger-lee/leap-framework?style=social" alt="Stars">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-58%20tools-22bb33" alt="MCP Tools">
  <img src="https://img.shields.io/badge/中文-支持-ff6600" alt="中文支持">
  <br>
  <b>🤖 Donnez à votre agent IA un véritable moteur de tutorat — pas seulement un prompt.</b>
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

## 🚀 Qu'est-ce que LEAP ?

**LEAP (Learning Evolution & Adaptation Pipeline) est un runtime de tutorat piloté par l'état pour les agents IA.** Il offre une boucle d'apprentissage persistante et auditable, au lieu d'un prompt unique « expliquer puis interroger ».

- **l'état de l'apprenant** et l'estimation de la maîtrise
- **les prérequis** et la possibilité d'aborder un sujet
- **la suffisance de l'évaluation** et la qualité des preuves
- **la planification des révisions** et la rétention à long terme
- **les transitions d'état** — rien n'avance sans l'accord du State Guard côté serveur

```bash
# L'agent demande à LEAP quoi faire ensuite
get_teaching_context(session_id, "py.recursion.base_case")
# 👉 stratégie : Retrieval Practice · action : Generate Practice
```

## ⚡ Démarrage rapide

```bash
git clone https://github.com/Vinger-lee/leap-framework.git
cd leap-framework
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

```bash
python -m leap.server      # démarrer le serveur MCP
```

## 🧠 La boucle d'apprentissage

```
1. Définition de l'objectif
2. Ancrage du domaine
3. Diagnostic de l'apprenant
4. Représentation des connaissances (DAG)
5. Initialisation de l'état
6. Boucle d'enseignement dynamique
7. Rétention (révisions FSRS)
8. Transfert (proche · variante · lointain · intégré)
9. Réflexion et persistance
```

## 🔑 Mécanismes clés

### 🔒 State Guard

Le State Guard est le seul composant autorisé à valider une transition. Lorsqu'un outil renvoie `REJECT`, l'agent s'adapte à la raison au lieu de forcer par le prompt. Un appel échoué ne devient jamais une mise à jour d'état silencieuse.

### 📊 La maîtrise est estimée côté serveur

`mastery_probability` est une **estimation de modèle, pas une vérité terrain**. Elle est calculée par un modèle BKT tenant compte de l'oubli, jamais produite par le LLM hôte. Le crédit partiel et la pondération par faible confiance sont pris en charge, et l'incertitude n'est jamais écrite comme `mastery = 0`.

### 🪜 Les stades de preuve (et ils régressent)

`estimated → practiced → demonstrated → retained → transferred`

Une bonne réponse produit une preuve — pas la maîtrise. Les stades **régressent** après une longue absence ou un échec dans un nouveau contexte.

## 🔧 Outils MCP

58 outils exposés via stdio.

| Groupe | Exemples |
|---|---|
| Session et objectif | `create_session`, `save_learning_goal`, `set_learning_configuration` |
| Diagnostic | `generate_diagnostic`, `submit_diagnostic`, `save_diagnostic_result` |
| Connaissances | `decompose_topic`, `save_knowledge_nodes`, `validate_knowledge_dag` |
| Politique | `get_teaching_context`, `evaluate_pedagogical_policy`, `commit_pedagogical_decision` |
| Évaluation | `generate_assessment`, `assess_response`, `assess_misconception` |
| Rétention | `schedule_review`, `get_due_reviews`, `submit_review` |
| State Guard | `start_unit`, `check_advance_unit`, `advance_unit`, `rollback_unit` |
| Rapports | `generate_final_report`, `get_learning_metrics` |

## 🧩 Conçu pour être enfichable

Six composants sont résolus via un registre de plugins : une implémentation se remplace depuis `config/default.yaml` sans modifier le code appelant.

| Point d'extension | Par défaut | Alternatives |
|---|---|---|
| Estimation d'état | `simplified_bkt` | PFA, DKT, Bayesian, hybrid |
| Agrégation des scores | `weighted` | rubric, model-based |
| Politique pédagogique | `rule_based` | LLM, hybrid, learned |
| Planificateur de révisions | `py-fsrs` | any scheduler |
| Stockage | `sqlite` | PostgreSQL, distributed |
| Stockage d'artefacts | `local` | object storage, knowledge base |

## 📚 Aller plus loin

- [Architecture](../../docs/ARCHITECTURE.md)
- [Guide d'intégration de l'agent hôte](../../docs/INTEGRATION.md)
- [Pages d'exemple](../../docs/EXAMPLES.md)
- [Internationalisation](../../docs/LOCALIZATION.md)
- [English README](../../README.md) · [中文说明](../../README_CN.md)

> La spécification de conception de référence et le système de design visuel sont maintenus séparément par l'auteur du projet et ne font pas partie de ce dépôt.

## 📄 Licence

[MIT](../../LICENSE) © Vinger-lee
