# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **最上位ルール: AGENTS.md はこのファイルより優先されます。**  
> 本ファイルは AGENTS.md の内容を統合した Claude Code 向けガイドです。  
> 矛盾が生じた場合は AGENTS.md に従ってください。

---

## Project Overview

safe-repo-scanner は、レガシーPHPプロジェクトの仕様調査前に、リポジトリ内の機密情報を安全にマスキングするローカル専用 Python ツールです。元リポジトリを変更せず、マスク済みコピーを生成します。  
対象フレームワーク: FuelPHP / Laravel / CakePHP / Symfony  
すべての docstring・コメント・ドキュメントは**日本語**で記述します。

**現在のフェーズ: Phase 1（コア機能実装）。Phase 2 の機能を先行実装しないこと。**

### Phase 1 の目標

- リポジトリ検索・選択 UI の実装
- 対象ファイル一覧の生成・ON/OFF 選択
- 機密情報のスキャン・結果一覧表示
- dry-run およびマスク実行
- JSON / CSV / Markdown レポート出力
- CLI の実装

### Phase 2 の目標（先行実装禁止）

- 検出精度の向上（誤検知削減・カバレッジ拡大）
- Shift-JIS / EUC-JP エンコーディング対応の強化
- allowlist / 除外ルールの UI 上での編集
- レポートの差分ビューア強化

---

## Commands

```bash
# セットアップ（PowerShell）
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# UI 起動
streamlit run app.py

# CLI
python -m src.scanner scan <repo_path>
python -m src.scanner report <repo_path> --format md --output report.md
python -m src.scanner mask <repo_path> --output <path> --dry-run
python -m src.scanner mask <repo_path> --output <path> --apply

# 全テスト実行
pytest

# モジュール単位でテスト実行 & エビデンス保存
pytest tests/test_detector_php.py -v > test/evidence/test_detector_php.txt
pytest tests/test_detector_env.py -v > test/evidence/test_detector_env.txt
pytest tests/test_detector_dsn.py -v > test/evidence/test_detector_dsn.txt
pytest tests/test_masker.py       -v > test/evidence/test_masker.txt

# セキュリティ監査
pip install pip-audit
pip-audit > test/evidence/security_audit.txt
```

---

## Architecture

3段構成パイプライン: **Scanner → Masker → Reporter**

```
repo_finder.py          ローカル Git リポジトリの検索・一覧表示
target_file_selector.py スキャン候補ファイルの生成・リスクレベル付与
scanner.py              detectors.py / dsn_parser.py を使ってスキャンを統括
masker.py               dry-run（差分プレビュー）または apply（マスク済みコピー出力）
reporter.py             JSON / CSV / Markdown レポートの出力
```

- `app.py` — Streamlit UI エントリーポイント
- `models.py` — データクラス: `RepoEntry`, `TargetFileEntry`, `DetectionResult`, `MaskRunResult`
- `detectors.py` — PHP / ENV / YAML / JSON / INI / XML 向けパターンマッチング
- `dsn_parser.py` — DSN 文字列の解析と部分置換
- `utils.py` — ファイル I/O・エンコーディング検出（chardet + 日本語フォールバックチェーン）・`preview_value()`
- `masking_rules.yaml` — 検出ルール・置換マップ・suspicious_keys・non_maskable_keys

### masker.run() の処理フロー

```
masker.run(repo_path, output_path, mode)
    │
    ├─ mode == "dry-run"
    │     └─ 変更件数サマリーと差分を返す（ファイルは書き換えない）
    │
    └─ mode == "apply"
          ├─ output_path が未指定 → エラーを返す（apply 禁止）
          ├─ output_path へリポジトリをコピー（.git/ は除外）
          ├─ Scanner の検出結果に基づき置換を実行
          ├─ reporter.save(results, output_path) でレポートを保存
          └─ 失敗時は output_path を削除して元リポジトリを保護する
```

---

## Repository Structure（変更禁止）

```
safe-repo-scanner/
  README.md
  requirements.txt
  app.py
  masking_rules.yaml
  AGENTS.md
  CLAUDE.md
  instruction.md
  src/
    __init__.py
    models.py
    repo_finder.py
    target_file_selector.py
    scanner.py
    detectors.py
    dsn_parser.py
    masker.py
    reporter.py
    utils.py
  tests/
    test_detector_php.py
    test_detector_env.py
    test_detector_dsn.py
    test_masker.py
  test/
    evidence/
```

---

## Critical Rules

### スコープ制約

- **元リポジトリの変更は禁止。** `masker.apply()` はコピー先にのみ書き込む
- **`.git/` のコピーは禁止。** コミット履歴からの機密情報復元を防ぐ
- **生値のログ出力は禁止。** レポートには `preview`（先頭3文字 + `***`）のみ出力する
- **`show raw` 等の生値表示機能は Phase 1 では実装しない**
- **バックアップまたはコピー先の作成なしに `apply` を実行しない**
- **外部 API への通信は禁止。** 完全ローカル動作のみ

### パッケージ・依存関係

- `requirements.txt` に記載のないパッケージの使用は禁止（`streamlit`, `chardet`, `pyyaml`, `pytest`）
- 新規パッケージ追加時は PyPI 公式ページ・ソースコードを確認してから `requirements.txt` に追記すること
- **既存コードの `import` を無条件に踏襲しない。** 新しいファイルで使う前に必ずセキュリティチェックを実施する

---

## Security Rules

> 本ツール自体が機密情報を扱うため、実装に潜むリスクへの対策が特に重要です。

### 実行時の外部通信 allowlist

本ツールは実行時の外部通信を一切行いません。以下はパッケージ取得時（開発・インストール時）のみ許可します。

```
pypi.org
files.pythonhosted.org
```

### 新規パッケージ追加・変更時のチェック項目

ソースコードを目視で確認すること。

- `httpx` / `requests` / `urllib` 等による外部通信
- `os.environ` / `os.getenv` の参照と外部送信
- `subprocess` / `eval` / `exec` の使用
- `logging` / `telemetry` / `monitoring` / `analytics` 系の内部実装（外部送信が隠れていないか）
- hook / plugin 的な拡張ポイントの存在

### PR 時のコードレビューチェックリスト

- [ ] 新規 `import` 文はすべて `requirements.txt` 記載のパッケージか
- [ ] 追加コードが参照する既存モジュール・依存パッケージ本体を確認したか
- [ ] ログ・HTTP・認証・設定読込・SDK ラッパー系パッケージの実装を目視したか
- [ ] 環境変数（`os.environ` / `os.getenv`）を外部へ送信していないか
- [ ] 実行時の外部 HTTP リクエストが存在しないか
- [ ] `logging` / `telemetry` / `monitoring` 系ライブラリが裏で外部送信していないか
- [ ] レポート・ログに `original_value`（生値）が含まれていないか（`preview` のみか）
- [ ] `masker.apply()` が元リポジトリのファイルを変更していないか
- [ ] `.git/` がコピー対象から除外されているか

---

## Testing

- フレームワーク: pytest（設定は `pytest.ini`、テストは `tests/`）
- 共通 fixture: `tests/conftest.py`
- エビデンスファイル（`test/evidence/*.txt`）はコミット対象（証跡として残す）
- **タスク完了の定義: pytest が全件 PASS かつ `test/evidence/` にエビデンスが保存されていること**
- テストを削除・スキップして PASS させることは禁止

### 必須テストケース

| Case | 内容 |
|---|---|
| Case 1 | PHP 基本キー値（username / password）のマスク |
| Case 2 | PHP SMTP 配列の部分マスク（port / timeout は非マスク） |
| Case 3 | PHP DSN 文字列の部分置換（charset は非マスク） |
| Case 4 | `.env` ファイルの検出・置換・レポート出力 |

---

## Branch Strategy（Git Flow）

- `main` および `develop` への直接 push は禁止。すべての変更は Pull Request 経由
- feature → `develop`、hotfix → `main`

### ブランチ命名規則

```
feature/{タスクID}-{説明}
hotfix/{内容}

例:
  feature/P1-scanner-php
  feature/P1-dsn-parser
  feature/P1-v1.1-export
  feature/P1-v1.2-email-masking
  hotfix/preview-leak-fix
```

### PR のルール

| 項目 | ルール |
|---|---|
| タイトル | `{フェーズ-タスク}: {内容}` の形式 |
| 説明 | 完了条件を箇条書きで転記すること |
| エビデンス | `test/evidence/` に対応する結果ファイルが含まれていること |
| テスト | PR 時点で全件 PASS していること |
| セキュリティ | コードレビューチェックリストを確認済みであること |
| レビュー | セルフマージ可（1名運用を前提） |

---

## Code Style

- Python docstring は**日本語**で記述し、`概要 / 入出力 / 制約 / Note` を含めること
- 関数・メソッドでは `Args / Returns / Raises / Note` を明示すること
- 分岐意図が読み取りづらい処理には 1〜2行の補助コメントを追加すること
- クラス名: PascalCase、関数・変数名: snake_case
- 内部パスはすべて POSIX 形式（フォワードスラッシュ）を使用する
- エンコーディングフォールバックチェーン: `detected → utf-8 → cp932 → shift_jis → euc_jp`

---

## AI（Claude Code）への追加指示

1. **実装指示に従う**: `instruction.md` の仕様・完了条件を厳守する
2. **スコープを超えない**: Phase 2 以降の機能を先行実装しない
3. **パスを変更しない**: 上記ディレクトリ構造は変更禁止
4. **テストを先に確認する**: 実装前に対応するテストコードを読み、完了条件を把握する
5. **エビデンスを保存する**: タスク完了時に必ず `test/evidence/` へ出力する
6. **ブランチルールを守る**: `main`・`develop` への直接 push 禁止
7. **auto-accept モードを使用しない**: 生成コードは必ず確認してから適用する
