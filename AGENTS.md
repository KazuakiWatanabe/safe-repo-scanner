# AGENTS.md
safe-repo-scanner ― 最上位ルール定義書（日本語）

本ドキュメントは、本リポジトリに関わる **すべてのAI（Codex等）と人間**が遵守すべき最上位ルールです。  
README や設計資料よりも **AGENTS.md を優先**します。

本プロジェクトは `instruction.md` に基づいて実装します。

> **現在の実装フェーズ**  
> 現在は **Phase 1（コア機能実装）** です。  
> Phase 1 完了後、Phase 2（拡張検出・レポート強化）へ移行します。

---

## 1. プロジェクトの目的

本プロジェクトは、レガシーPHPプロジェクトの仕様調査前に、リポジトリ内の機密情報を安全にマスキングするローカルツールを提供することを目的とします。

具体的には、`.env` だけでなく PHP / YAML / config 配下のベタ書き設定も対象にし、

- **機密情報の検出（scan）**
- **検出結果の一覧化・レビュー（report）**
- **ダミー値への置換（mask）**
- **元ソースを変更せず、マスク済みコピーの出力**

を担います。対象フレームワークとして FuelPHP / Laravel / CakePHP / Symfony を想定します。

### 現在の目標（Phase 1）

- リポジトリ検索・選択 UI の実装
- 対象ファイル一覧の生成・ON/OFF 選択
- 機密情報のスキャン・結果一覧表示
- dry-run および マスク実行
- JSON / CSV / Markdown レポート出力
- CLI の実装

### 次の目標（Phase 2）

- 検出精度の向上（誤検知削減・カバレッジ拡大）
- Shift-JIS / EUC-JP エンコーディング対応の強化
- allowlist / 除外ルールの UI 上での編集
- レポートの差分ビューア強化

---

## 2. スコープ制約（必須）

- **元リポジトリの変更は禁止**。マスク処理はコピー先にのみ実施する
- **`.git/` のコピーは禁止**。コミット履歴からの機密情報復元を防ぐ
- **生値のログ出力は禁止**。レポートには `preview`（先頭3文字 + `***`）のみ出力する
- **`show raw` 等の生値表示機能は Phase 1 では実装しない**
- **バックアップまたはコピー先の作成なしに `apply` を実行しない**
- Phase 2 以降の機能（UI上でのルール編集・差分ビューア強化等）を先行実装しない
- 外部APIへの通信は行わない（完全ローカル動作）

---

## 3. リポジトリ構造

本リポジトリは以下の構造を前提とします（**変更禁止**）。

```
safe-repo-scanner/
  README.md
  requirements.txt
  app.py
  masking_rules.yaml
  AGENTS.md                    # 本ファイル（最上位ルール）
  instruction.md               # Codex向け実装指示書
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
    evidence/                  # pytest -v の出力結果（自動生成）
```

---

## 4. モジュール構成

本ツールのコアフローは **Scanner → Masker → Reporter** の3段構成です。

```
対象ファイル群
    ↓
Scanner       src/scanner.py
              detectors.py / dsn_parser.py を呼び出し
              機密情報候補を DetectionResult のリストとして返す
    ↓
Masker        src/masker.py
              dry-run: 変更内容のサマリーと差分を返す（ファイル非更新）
              apply:   コピー先ディレクトリに置換済みファイルを出力する
    ↓
Reporter      src/reporter.py
              JSON / CSV / Markdown 形式でレポートを出力する
              生値は含めず preview のみ記録する
```

```
UI (app.py / Streamlit)
    │
    ├─ repo_finder.py          Git リポジトリの検索・一覧表示
    ├─ target_file_selector.py 対象ファイル候補の生成・ON/OFF 選択
    ├─ scanner.py              スキャン実行・結果表示
    ├─ masker.py               dry-run / apply 実行
    └─ reporter.py             レポート出力
```

---

## 5. 処理フロー詳細

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

## 6. データモデル

```python
from dataclasses import dataclass
from typing import Literal, Optional

@dataclass
class RepoEntry:
    name: str
    path: str
    branch: str
    last_updated: str
    selected: bool = False

@dataclass
class TargetFileEntry:
    path: str
    file_type: str
    size: int
    scan_reason: str
    risk_level: Literal["high", "medium", "low"]
    selected: bool = True
    excluded_reason: Optional[str] = None

@dataclass
class DetectionResult:
    file_path: str
    line_no: int
    column_start: int
    column_end: int
    key_name: Optional[str]
    original_value: str
    original_value_preview: str   # 先頭3文字 + "***"（最大6文字）例: "p@s***"
    category: str
    rule_type: str
    confidence: Literal["high", "medium", "low"]
    severity: Literal["critical", "high", "medium", "low"]
    replacement: str
    auto_maskable: bool
    reason: str
```

---

## 7. ブランチ戦略

### 基本方針

本リポジトリは **Git Flow** を採用します。  
`main` および `develop` への直接 push は禁止です。すべての変更は Pull Request 経由でマージします。

### ブランチ構成

```
main        リリース済み安定版
develop     統合ブランチ
feature/    機能実装（develop から分岐）
hotfix/     main の緊急修正
```

### ブランチ命名規則

```
feature/{タスクID}-{説明}
hotfix/{内容}

例：
  feature/P1-repo-finder          # Phase 1: リポジトリ検索実装
  feature/P1-scanner-php          # Phase 1: PHPスキャン実装
  feature/P1-dsn-parser           # Phase 1: DSNパーサー実装
  feature/P1-masker-apply         # Phase 1: マスク実行実装
  feature/P1-ui-streamlit         # Phase 1: Streamlit UI実装
  feature/P2-encoding-euc         # Phase 2: EUC-JPエンコーディング対応
  hotfix/preview-leak-fix         # 生値がpreviewに漏れるバグ修正
```

### PR のルール

| 項目 | ルール |
|---|---|
| タイトル | `{フェーズ-タスク}: {内容}` の形式 |
| base ブランチ | feature → `develop`、hotfix → `main` |
| 説明 | 完了条件を箇条書きで転記すること |
| エビデンス | `test/evidence/` に対応する結果ファイルが含まれていること |
| テスト | PR 時点で全件 PASS していること |
| セキュリティ | §12 のコードレビューチェックリストを確認済みであること |
| レビュー | セルフマージ可（1名運用を前提） |

---

## 8. 起動方法

```bash
# UI 起動
streamlit run app.py

# CLI
python -m src.scanner scan <repo_path>
python -m src.scanner report <repo_path> --format md
python -m src.scanner mask <repo_path> --output <masked_repo_path> --dry-run
python -m src.scanner mask <repo_path> --output <masked_repo_path> --apply
```

---

## 9. 実行環境・依存関係

| 項目 | 内容 |
|---|---|
| Python | 3.11 以上 |
| 主対象OS | Windows 11 |
| UI フレームワーク | Streamlit |
| エンコーディング検出 | chardet |
| テスト | pytest |
| 外部通信 | **なし（完全ローカル動作）** |

### requirements.txt に含めるパッケージ（最小構成）

```
streamlit
chardet
pyyaml
pytest
```

> `requirements.txt` に記載のないパッケージの使用は禁止。  
> 新規追加時は §12 のセキュリティチェックを実施すること。

---

## 10. テスト・エビデンス運用ルール

### テストケース（必須 / 全件 PASS が完了条件）

| Case | 内容 |
|---|---|
| Case 1 | PHP 基本キー値（username / password）のマスク |
| Case 2 | PHP SMTP 配列の部分マスク（port / timeout は非マスク） |
| Case 3 | PHP DSN 文字列の部分置換（charset は非マスク） |
| Case 4 | `.env` ファイルの検出・置換・レポート出力 |

### 実行方法

```bash
# 全テスト一括実行
pytest

# モジュール単位で実行してエビデンス保存
pytest tests/test_detector_php.py -v > test/evidence/test_detector_php.txt
pytest tests/test_detector_env.py -v > test/evidence/test_detector_env.txt
pytest tests/test_detector_dsn.py -v > test/evidence/test_detector_dsn.txt
pytest tests/test_masker.py       -v > test/evidence/test_masker.txt
```

### ルール

- タスク完了の定義は **pytest が全件 PASS** かつ **`test/evidence/` にエビデンスが保存されている** こと
- `test/evidence/` の `.txt` ファイルはコミット対象とする（証跡として残す）
- テストを削除・スキップして PASS させることは **禁止**

---

## 11. AI（Codex等）への指示

AIが本リポジトリで作業する際は以下を遵守します。

1. **実装指示に従う**：`instruction.md` の仕様・完了条件を厳守する
2. **スコープを超えない**：Phase 2 以降の機能を先行実装しない
3. **パスを変更しない**：§3 のディレクトリ構造は変更禁止
4. **元リポジトリを変更しない**：`masker.apply()` はコピー先にのみ書き込む
5. **生値をログに出力しない**：レポート・ログには必ず `preview` のみ使用する
6. **`.git/` を除外する**：コピー処理では `.git/` を必ず除外する
7. **テストを先に確認する**：実装前に対応するテストコードを読み、完了条件を把握する
8. **エビデンスを保存する**：タスク完了時に必ず `test/evidence/` へ出力する
9. **ブランチルールを守る**：`main`・`develop` への直接 push 禁止。必ず `feature/` ブランチを切って PR を出す
10. **Pythonコメント規約を守る**：Pythonファイル先頭に「概要」「入出力」「制約」「Note」を含む日本語 docstring を記述する。関数/メソッドでは `Args / Returns / Raises / Note` を明示し、分岐意図が読み取りづらい処理には1〜2行の補助コメントを追加する
11. **既存コードの import を無条件に踏襲しない**：新しいファイルで `import` する前に §12 のセキュリティチェックを実施する。`requirements.txt` に記載のないパッケージは使用禁止

---

## 12. セキュリティルール

> **背景**  
> 本ツール自体が機密情報を扱うため、ツール実装に潜むリスクへの対策が特に重要です。  
> AIは「既存コードで使われているパッケージ」を既知・安全なものとして扱い、  
> 悪意あるコードをそのまま新しいファイルへ踏襲する場合があります。  
> このセクションはその盲点を補うための多重防御として機能します。

### AI・人間の双方が遵守するルール

| ルール | 詳細 |
|---|---|
| **既存 import の盲信禁止** | 既存コードに含まれる `import` / `from ... import` であっても、初めて別ファイルで使う際は下記チェックを必ず実施する |
| **差分確認だけで安全と判断しない** | 新規追加コードの差分確認だけでは不十分。追加コードが参照する既存モジュール・依存パッケージ本体の実装まで確認すること |
| **依存パッケージ本体の重点監査** | ログ・HTTP・認証・設定読込・telemetry・monitoring・analytics 系ライブラリは優先的に実装を目視確認する |
| **環境変数の外部送信禁止** | `os.environ` / `os.getenv` の値を外部 URL へ送信するコードを一切書かない |
| **外部通信の禁止** | 本ツールは完全ローカル動作を前提とする。外部 URL への HTTP リクエストを実装しない |
| **許可リスト外パッケージの使用禁止** | `requirements.txt` に記載のないパッケージを追加する場合は、PyPI 公式ページ・ソースコードを確認してからのみ追加可とする |
| **auto-accept モードの使用禁止** | Claude Code を auto-accept で運用しない。生成コードは必ず確認してから適用する |

### 外部通信先 allowlist

本ツールは外部通信を行いません。以下のみ許可します。

```
# パッケージ取得時のみ（開発・インストール時）
pypi.org
files.pythonhosted.org
```

> 実行時の外部通信は **一切禁止**。

### セキュリティチェック手順（パッケージ追加・変更時）

```bash
pip install pip-audit
pip-audit

# スキャン結果をエビデンスとして保存
pip-audit > test/evidence/security_audit.txt
```

確認ポイント（新規パッケージのソースコードを目視）：

- `httpx` / `requests` / `urllib` 等による外部通信
- `os.environ` / `os.getenv` の参照と送信
- `subprocess` / `eval` / `exec` の使用
- `logging` / `telemetry` / `monitoring` / `analytics` 系の内部実装（外部送信が隠れていないか）
- hook / plugin 的な拡張ポイントの存在

### コードレビューチェックリスト（PR 時）

- [ ] 新規 `import` 文はすべて `requirements.txt` 記載のパッケージか
- [ ] 差分コードだけでなく、そのコードが参照する既存モジュール・依存パッケージ本体を確認したか
- [ ] ログ・HTTP・認証・設定読込・SDK ラッパー系パッケージの実装を目視したか
- [ ] 環境変数（`os.environ` / `os.getenv`）を外部へ送信していないか
- [ ] 実行時の外部 HTTP リクエストが存在しないか
- [ ] `logging` / `telemetry` / `monitoring` 系ライブラリが裏で外部送信していないか
- [ ] レポート・ログに `original_value`（生値）が含まれていないか（`preview` のみであるか）
- [ ] `masker.apply()` が元リポジトリのファイルを変更していないか
- [ ] `.git/` がコピー対象から除外されているか
