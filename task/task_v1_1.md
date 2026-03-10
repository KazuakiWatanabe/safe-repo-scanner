# safe-repo-scanner タスク定義 v1.1（全体仕様）

> **このファイルは参照用仕様書です。Codex への作業指示は以下の順で渡してください。**
>
> ```
> フェーズ1: task-test-v1.1.md のみ渡す → pytest で RED を人間が目視確認
> フェーズ2: task-impl-v1.1.md を渡す  → pytest で GREEN を確認 → エビデンス保存
> ```

---

## バージョン情報

| 項目 | 内容 |
|---|---|
| バージョン | v1.1 |
| ベース | v1.0（instruction.md 完了済み） |
| 対象ブランチ | `feature/P1-v1.1-export` |

---

## 追加機能概要

| # | 機能名 | 概要 |
|---|---|---|
| F-01 | **Step Export** | 各ステップ完了時の結果リストをファイルに出力する |
| F-02 | **Tree Export** | マスク実行後、対象ファイルのパスをツリー構造で出力する |

---

## F-01: Step Export 仕様

### 出力ファイル仕様

| ステップ | タイミング | ファイル名 | 形式 | 主な内容 |
|---|---|---|---|---|
| Step 1 | 対象ファイル一覧確定時 | `step1_target_files.csv` | CSV | `path`, `file_type`, `size`, `scan_reason`, `risk_level` |
| Step 2 | スキャン結果確定時 | `step2_scan_results.csv` | CSV | `file_path`, `line_no`, `key_name`, `preview`, `category`, `severity`, `replacement`, `auto_maskable` |
| Step 3 | dry-run 完了時 | `step3_dryrun_summary.md` | Markdown | 変更件数サマリー・ファイル別変更予定一覧 |
| Step 4 | マスク apply 完了時 | `step4_mask_report.json` | JSON | 全検出結果・置換結果・スキップファイル一覧 |

### 制約

- 出力先ディレクトリは UI 上で指定できること
- デフォルト出力先: `~/safe-repo-scanner-output/{YYYYMMDD_HHMMSS}/`
- 出力先ディレクトリが存在しない場合は自動生成すること
- 全ファイルを UTF-8 で出力すること
- `original_value`（生値）は出力に含めないこと。`preview` のみ記録する

### 実装箇所

- `src/reporter.py` に `export_step(step: int, results: list, output_dir: Path) -> Path` を追加
- `app.py` の各ステップ完了ボタン押下時に `export_step()` を呼び出す

---

## F-02: Tree Export 仕様

### 出力ファイル仕様

- **ファイル名:** `masked_file_tree.md`
- **形式:** Markdown

### 出力フォーマット例

```
# Masked File Tree
## Repository: {リポジトリ名}
## Masked at: {YYYY-MM-DD HH:MM:SS}
## Total masked files: {件数}

{リポジトリルート}/
├── config/
│   ├── app.php              [masked: 3 items]
│   ├── database.php         [masked: 5 items]
│   └── services.php         [masked: 2 items]
├── fuel/
│   └── app/
│       └── config/
│           └── production/
│               └── db.php   [masked: 4 items]
└── .env                     [masked: 6 items]

## Skipped files (3)
- vendor/autoload.php        [reason: excluded path]
- storage/logs/app.log       [reason: excluded path]
- config/legacy_sjis.php     [reason: encoding error]
```

### 仕様詳細

- マスク処理が適用されたファイルのみをツリーに表示する（未変更ファイルは除外）
- 各ファイルに `[masked: N items]` の形式でマスク件数を付記する
- スキップファイルは末尾に `[reason: ...]` 付きで一覧出力する
  - スキップ理由は `excluded path` / `encoding error` の2種類とする
- UI のマスク完了画面にも `st.expander` を用いてツリービューを表示する

### 実装箇所

- `src/reporter.py` に `export_tree(masked_results: list, skipped_files: list, repo_name: str, output_dir: Path) -> Path` を追加
- `app.py` の apply 完了後に `export_tree()` を呼び出す

---

## 受け入れ条件（AC）

| ID | 条件 |
|---|---|
| AC-01 | Step 1〜4 の各タイミングで所定のファイル名・形式でファイルが出力される |
| AC-02 | 出力ファイルに `original_value`（生値）が含まれない（`preview` のみ） |
| AC-03 | ツリー出力にはマスク適用ファイルのみが表示され、各ファイルに正しいマスク件数が付記される |
| AC-04 | スキップファイルがツリー末尾に `reason` 付きで出力される |
| AC-05 | 出力先ディレクトリが存在しない場合、自動生成されてからファイルが書き込まれる |
| AC-06 | 出力ファイルが UTF-8 で書き込まれる（日本語パス・値を含むケース） |

---

## 変更対象ファイル

| ファイル | 変更種別 |
|---|---|
| `src/reporter.py` | `export_step()` / `export_tree()` を追加 |
| `app.py` | 各ステップ完了時の呼び出しを追加 |
| `tests/test_reporter_export.py` | 新規作成（フェーズ1） |
| `tests/test_reporter_tree.py` | 新規作成（フェーズ1） |
| `tests/conftest.py` | 共通 fixture を追加（フェーズ1） |

> `src/models.py` / `src/masker.py` / `src/scanner.py` など他のモジュールは変更しないこと。
