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
  <b>🤖 AI 에이전트에 프롬프트가 아닌 진짜 튜터링 엔진을 제공하세요.</b>
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

## 🚀 LEAP란?

**LEAP(Learning Evolution & Adaptation Pipeline)는 AI 에이전트용 상태 기반 튜터링 런타임입니다.** 일회성 ‘설명 후 퀴즈’ 프롬프트 대신, 지속 가능하고 감사 가능한 학습 루프를 제공합니다.

- **학습자 상태**와 숙달도 추정
- **선수 조건** 및 해당 주제로 진입 가능 여부
- **평가 충분성**과 증거 품질
- **복습 스케줄**과 장기 유지
- **상태 전이** — 서버 측 State Guard를 통과해야만 진행됩니다

```bash
# 에이전트가 LEAP에 다음 단계를 묻습니다
get_teaching_context(session_id, "py.recursion.base_case")
# 👉 전략: Retrieval Practice · 액션: Generate Practice
```

## ⚡ 빠른 시작

```bash
git clone https://github.com/Vinger-lee/leap-framework.git
cd leap-framework
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

```bash
python -m leap.server      # MCP 서버 실행
```

## 🧠 학습 루프

```
1. 목표 정의
2. 도메인 그라운딩
3. 학습자 진단
4. 지식 표현(DAG)
5. 학습자 상태 초기화
6. 동적 티칭 루프
7. 유지(FSRS 복습)
8. 전이(근·변형·원·통합)
9. 성찰 및 저장
```

## 🔑 핵심 메커니즘

### 🔒 State Guard

State Guard는 상태 전이를 승인할 수 있는 유일한 컴포넌트입니다. 도구가 `REJECT`를 반환하면, 에이전트는 프롬프트로 밀어붙이지 않고 이유에 맞춰 대응합니다. 실패한 호출이 조용한 상태 업데이트로 변하지 않습니다.

### 📊 숙달도는 서버에서 추정

`mastery_probability`는 **모델 추정값이며 실제 값이 아닙니다**. 망각을 고려한 BKT 모델이 서버에서 계산하며, 호스트 LLM이 확률을 출력하지 않습니다. 부분 점수와 낮은 신뢰도 할인도 지원하고, ‘불확실’을 `mastery = 0`으로 기록하지 않습니다.

### 🪜 증거 단계(후퇴합니다)

`estimated → practiced → demonstrated → retained → transferred`

한 번 맞혔다고 해서 숙달된 것은 아닙니다 — 그것은 하나의 증거일 뿐입니다. 오랫동안 접하지 않거나 새로운 상황에서 실패하면 단계는 **후퇴**합니다.

## 🔧 MCP 도구

stdio를 통해 62개 도구를 제공합니다.

| 그룹 | 예시 |
|---|---|
| 세션 및 목표 | `create_session`, `save_learning_goal`, `set_learning_configuration` |
| 진단 | `generate_diagnostic`, `submit_diagnostic`, `save_diagnostic_result` |
| 지식 | `decompose_topic`, `save_knowledge_nodes`, `validate_knowledge_dag` |
| 정책 | `get_teaching_context`, `evaluate_pedagogical_policy`, `commit_pedagogical_decision` |
| 평가 | `generate_assessment`, `assess_response`, `assess_misconception` |
| 유지 | `schedule_review`, `get_due_reviews`, `submit_review` |
| 상태 가드 | `start_unit`, `check_advance_unit`, `advance_unit`, `rollback_unit` |
| 보고 | `generate_final_report`, `get_learning_metrics` |

## 🧩 플러그인 설계

6개 컴포넌트는 플러그인 레지스트리로 해결되므로 `config/default.yaml`만 변경하면 구현을 교체할 수 있습니다. 호출부 코드는 수정할 필요가 없습니다.

| 구분 | 기본값 | 대안 |
|---|---|---|
| 상태 추정 | `simplified_bkt` | PFA, DKT, Bayesian, hybrid |
| 점수 집계 | `weighted` | rubric, model-based |
| 교수 정책 | `rule_based` | LLM, hybrid, learned |
| 복습 스케줄러 | `py-fsrs` | any scheduler |
| 스토리지 | `sqlite` | PostgreSQL, distributed |
| 아티팩트 저장소 | `local` | object storage, knowledge base |

## 📚 더 보기

- [[docs/ARCHITECTURE|아키텍처]]
- [[docs/INTEGRATION|호스트 에이전트 통합 가이드]]
- [[docs/EXAMPLES|예시 페이지]]
- [[docs/LOCALIZATION|다국어 지원]]
- [[README|English README]] · [[README_CN|中文说明]]

> 공식 프레임워크 설계 문서와 비주얼 디자인 시스템은 프로젝트 저자가 별도로 관리하며 이 저장소에는 포함되지 않습니다.

## 📄 라이선스

[MIT](../../LICENSE) © Vinger-lee

> [!note]- Reading and verification sequence: LEAP 🎓 LEAP Framework
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[[Knowledge_Index]] · [[README]] · [[README_CN]] · [[docs/i18n/README.ar]] · [[docs/i18n/README.es]] · [[docs/i18n/README.fr]] · [[docs/i18n/README.ja]] · [[docs/i18n/README.ru]]
