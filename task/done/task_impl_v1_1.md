# フェーズ2: 実装指示 — v1.1 Step Export / Tree Export

---

## ⚠️ このファイルを渡す前に確認すること

```bash
pytest tests/test_reporter_export.py tests/test_reporter_tree.py -v
```

> **全テストが RED（FAIL / ERROR）になっていることを確認してからこのファイルを渡すこと。**  
> RED を確認していない場合はフェーズ1（`task-test-v1.1.md`）に戻ること。

---

## 0. タスク固有設定

```yaml
target_files:
  - "src/reporter.py"

target_functions:
  - "reporter.export_step(step, results, output_dir)"
  - "reporter.export_tree(masked_results, skipped_files, repo_name, output_dir)"

test_scope:
  include: "フェーズ1で作成済みのテストをすべて GREEN にすること"
  exclude: "新しいテストの追加・既存テストの変更"

source_spec: "task-v1.1.md"

task_constraints:
  refactor_policy: "src/reporter.py のみ変更可。tests/ は変更禁止"
```

---

## 1. このフェーズでやること・やらないこと

| やること | やらないこと |
|---|---|
| `src/reporter.py` に `export_step()` / `export_tree()` を実装する | テストコードを変更する |
| pytest を実行して **GREEN（PASS）を確認する** | テストを削除・スキップして PASS させる |
| エビデンスを `test/evidence/` に保存する | `src/reporter.py` 以外の `src/` 配下を変更する |

---

## 2. 実装仕様

### export_step()

```python
def export_step(step: int, results: list, output_dir: Path) -> Path:
    """
    概要: 各ステップの結果リストをファイルに出力する
    入力: step=1〜4, results=対象リスト, output_dir=出力先ディレクトリ
    出力: 生成したファイルの Path
    制約: original_value を出力に含めないこと
    Note: output_dir が存在しない場合は自動生成すること
    """
```

| step | 出力ファイル名 | 形式 | 出力フィールド |
|---|---|---|---|
| 1 | `step1_target_files.csv` | CSV | `path`, `file_type`, `size`, `scan_reason`, `risk_level` |
| 2 | `step2_scan_results.csv` | CSV | `file_path`, `line_no`, `key_name`, `preview`, `category`, `severity`, `replacement`, `auto_maskable` |
| 3 | `step3_dryrun_summary.md` | Markdown | 変更件数サマリー・ファイル別変更予定一覧 |
| 4 | `step4_mask_report.json` | JSON | 全検出結果・スキップファイル一覧（`original_value` は除外） |

- `results` が空の場合、ファイルは生成するが内容は空（CSV はヘッダーのみ、JSON は `[]`）
- 全ファイルを UTF-8 で書き込む

### export_tree()

```python
def export_tree(
    masked_results: list,
    skipped_files: list,
    repo_name: str,
    output_dir: Path,
) -> Path:
    """
    概要: マスク適用ファイルのパスをツリー構造で Markdown に出力する
    入力: masked_results=DetectionResult リスト, skipped_files=スキップ情報リスト,
          repo_name=リポジトリ名, output_dir=出力先ディレクトリ
    出力: masked_file_tree.md の Path
    制約: マスク適用ファイルのみをツリーに表示する。未変更ファイルは含めない
    Note: ファイルごとのマスク件数は masked_results を集計して算出する
    """
```

- 出力ファイル名: `masked_file_tree.md`
- ツリーはパスを `/` で分割して階層構造を構成する
- 各ファイルに `[masked: N items]`（N = そのファイルの `DetectionResult` 件数）を付記する
- スキップファイルは末尾の `## Skipped files` セクションに `[reason: ...]` 付きで出力する
- タイムスタンプは `datetime.now()` を使用する（テストでは mock が差し込まれる想定）

---

## 3. 実装後の自己検証ステップ

```bash
# Step 1: テストが GREEN になることを確認
pytest tests/test_reporter_export.py tests/test_reporter_tree.py -v

# Step 2: 核となるロジックを意図的に壊して RED になることを確認
# 例: export_step() で original_value をそのまま CSV に書き込む実装に変更し
#     test_export_does_not_contain_original_value が FAIL することを確認する

# Step 3: 壊した実装を元に戻して GREEN に戻ることを確認
pytest tests/test_reporter_export.py tests/test_reporter_tree.py -v

# Step 4: カバレッジ確認
pytest tests/test_reporter_export.py tests/test_reporter_tree.py \
  --cov=src/reporter --cov-report=term-missing

# Step 5: エビデンス保存
pytest tests/test_reporter_export.py tests/test_reporter_tree.py -v \
  > test/evidence/test_reporter_v1.1.txt
```

---

## 4. フェーズ2 終了条件

- [ ] `pytest` で全テストが GREEN（PASS）である
- [ ] `src/reporter.py` のカバレッジが 85% 以上である
- [ ] 自己検証ステップ（Step 2）で RED になることを確認済みである
- [ ] テストコードを一切変更していない
- [ ] `src/reporter.py` 以外の `src/` 配下を変更していない
- [ ] `test/evidence/test_reporter_v1.1.txt` が保存されている

---

## 5. 禁止事項

| 禁止パターン | 理由 |
|---|---|
| テストを削除・スキップして PASS させる | 仕様を証明していない |
| テストコードの期待値を実装に合わせて書き換える | テストが仕様でなく実装を追いかける状態になる |
| `original_value` を出力ファイルに含める | AC-02 違反・機密漏洩リスク |
| `src/reporter.py` 以外の `src/` を変更する | フェーズ2のスコープ外 |
