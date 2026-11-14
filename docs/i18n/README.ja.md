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
  <b>🤖 AI エージェントに、プロンプトではなく本物のチュータリングエンジンを。</b>
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

## 🚀 LEAP とは

**LEAP（Learning Evolution & Adaptation Pipeline）は、AI エージェント向けの状態駆動チュータリングランタイムです。** 単発の「説明してから出題する」プロンプトではなく、永続的で監査可能な学習ループを提供します。

- **学習者状態**と熟達度の推定
- **前提条件**と、トピックに進めるかどうか
- **評価の十分性**とエビデンスの質
- **復習スケジュール**と長期保持
- **状態遷移** —— サーバー側 State Guard を通らない限り何も進みません

```bash
# エージェントが LEAP に次の一手を尋ねる
get_teaching_context(session_id, "py.recursion.base_case")
# 👉 戦略: Retrieval Practice · アクション: Generate Practice
```

## ⚡ クイックスタート

```bash
git clone https://github.com/Vinger-lee/leap-framework.git
cd leap-framework
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

```bash
python -m leap.server      # MCP サーバーの起動
```

## 🧠 学習ループ

```
1. 目標の定義
2. ドメイン・グラウンディング
3. 学習者診断
4. 知識表現（DAG）
5. 学習者状態の初期化
6. 動的ティーチング・ループ
7. 保持（FSRS 復習）
8. 転移（近・変形・遠・統合）
9. 振り返りと永続化
```

## 🔑 主要な仕組み

### 🔒 State Guard

State Guard は状態遷移を承認できる唯一のコンポーネントです。ツールが `REJECT` を返した場合、エージェントはプロンプトで押し切るのではなく、理由に沿って対応します。失敗した呼び出しが暗黙のうちに状態更新になることはありません。

### 📊 熟達度はサーバー側で推定

`mastery_probability` は**モデル推定値であり、真値ではありません**。忘却を考慮した BKT モデルがサーバー側で計算し、ホスト LLM が確率を出力することはありません。部分点と低信頼度の割引に対応し、「不確実」を `mastery = 0` として書き込むことはありません。

### 🪜 エビデンス段階（後退します）

`estimated → practiced → demonstrated → retained → transferred`

一度正解しても、それは 1 つのエビデンスであり「習得」ではありません。長期間触れなかった場合や新しい場面で失敗した場合、段階は**後退**します。

## 🔧 MCP ツール

[自動生成された MCP ツール一覧・引数・プロファイル](../mcp-tools.md).

## 🧩 プラグイン設計

6 つのコンポーネントはプラグインレジストリで解決されるため、`config/default.yaml` の変更だけで実装を差し替えられます。呼び出し側のコードは変更不要です。

| 接缝 | 既定 | 代替 |
|---|---|---|
| 状態推定 | `simplified_bkt` | PFA, DKT, Bayesian, hybrid |
| スコア集約 | `weighted` | rubric, model-based |
| 教授方針 | `rule_based` | LLM, hybrid, learned |
| 復習スケジューラ | `py-fsrs` | any scheduler |
| ストレージ | `sqlite` | PostgreSQL, distributed |
| 成果物ストア | `local` | object storage, knowledge base |

## 📚 さらに詳しく

- [アーキテクチャ](../ARCHITECTURE.md)
- [ホストエージェント統合ガイド](../INTEGRATION.md)
- [サンプルページ](../EXAMPLES.md)
- [多言語対応](../LOCALIZATION.md)
- [English README](../../README.md) · [中文说明](../../README_CN.md)

> 権威あるフレームワーク設計書とビジュアル仕様はプロジェクト著者が別途管理しており、このリポジトリには含まれません。

## 📄 ライセンス

[MIT](../../LICENSE) © Vinger-lee

> [!note]- Reading and verification sequence: LEAP 🎓 LEAP Framework
> Start with the definitions and scope in this note. Follow each prerequisite link before applying the workflow.
> Work through a concrete input and retain intermediate results; compare the output with the applicable contract or definition.
> For a failure, preserve the original input, the exact rejection reason and the corrected next action. A successful transport call is evidence of execution, not of domain correctness or learning.
> After the worked case, change one condition and state which conclusion still follows. Store the result as a timestamped observation rather than promoting evidence locally.

## 🤖 Agent Skill（任意）

`.agents/skills/leap-tutor/` は、リポジトリ内 Skill を読み込めるホストでのみ利用できます。対応範囲は [docs/agent-skill.md](../../docs/agent-skill.md)、設定例は [docs/host-config.md](../../docs/host-config.md) を参照してください。未検証のホストを主張しません。

<!-- LEAP_BACKLINKS -->

## Backlinks / 反向关联

[Knowledge_Index](../../Knowledge_Index.md) · [README](../../README.md) · [README_CN](../../README_CN.md) · [docs/i18n/README.ar](README.ar.md) · [docs/i18n/README.es](README.es.md) · [docs/i18n/README.fr](README.fr.md) · [docs/i18n/README.ko](README.ko.md) · [docs/i18n/README.ru](README.ru.md)
