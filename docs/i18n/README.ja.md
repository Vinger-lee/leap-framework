# 🎓 LEAP Framework

<p align="center">
  <img src="https://img.shields.io/github/stars/Vinger-lee/leap-framework?style=social" alt="Stars">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-58%20tools-22bb33" alt="MCP Tools">
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

58 のツールを stdio 経由で提供します。

| グループ | 例 |
|---|---|
| セッションと目標 | `create_session`, `save_learning_goal`, `set_learning_configuration` |
| 診断 | `generate_diagnostic`, `submit_diagnostic`, `save_diagnostic_result` |
| 知識 | `decompose_topic`, `save_knowledge_nodes`, `validate_knowledge_dag` |
| 方針 | `get_teaching_context`, `evaluate_pedagogical_policy`, `commit_pedagogical_decision` |
| 評価 | `generate_assessment`, `assess_response`, `assess_misconception` |
| 保持 | `schedule_review`, `get_due_reviews`, `submit_review` |
| 状態ガード | `start_unit`, `check_advance_unit`, `advance_unit`, `rollback_unit` |
| レポート | `generate_final_report`, `get_learning_metrics` |

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

- [アーキテクチャ](../../docs/ARCHITECTURE.md)
- [ホストエージェント統合ガイド](../../docs/INTEGRATION.md)
- [サンプルページ](../../docs/EXAMPLES.md)
- [多言語対応](../../docs/LOCALIZATION.md)
- [English README](../../README.md) · [中文说明](../../README_CN.md)

> 権威あるフレームワーク設計書とビジュアル仕様はプロジェクト著者が別途管理しており、このリポジトリには含まれません。

## 📄 ライセンス

[MIT](../../LICENSE) © Vinger-lee
