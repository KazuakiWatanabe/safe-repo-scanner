# フェーズ1: テストコード作成指示 — v1.1 Step Export / Tree Export

---

## ⚠️ このフェーズでやること・やらないこと

| やること | やらないこと |
|---|---|
| テストコードを書く | `src/reporter.py` に `export_step()` / `export_tree()` を実装する |
| pytest を実行して **RED（FAIL）を確認する** | テストを通すために実装を書く |
| `tests/conftest.py` に fixture を追加する | `src/` 配下の既存コードを変更する |

> **テストが RED にならない場合はフェーズ1が完了していません。**  
> RED を確認してから `task-impl-v1.1.md`（フェーズ2）に進んでください。

---

## 0. タスク固有設定

```yaml
target_files:
  - "tests/test_reporter_export.py"   # 新規作成
  - "tests/test_reporter_tree.py"     # 新規作成
  - "tests/conftest.py"               # fixture 追加

target_functions:
  - "reporter.export_step"    # 未実装。テストは必ず FAIL する
  - "reporter.export_tree"    # 未実装。テストは必ず FAIL する

test_scope:
  include: |
    - Step 1〜4 それぞれで所定のファイル名・形式のファイルが生成されること
    - 出力ファイルに original_value（生値）が含まれないこと
    - ツリー出力がマスク適用ファイルのみを正しい階層・件数で表示すること
    - スキップファイルが末尾に理由付きで出力されること
    - 出力先ディレクトリが存在しない場合に自動生成されること
    - 出力ファイルが UTF-8 で書き込まれること
  exclude: |
    - UI（app.py）の描画テスト
    - CLI 経由の出力検証
    - パフォーマンス・並行実行

source_spec: "task-v1.1.md"
ac_ids:
  - "AC-01: Step 1〜4 の各タイミングで所定のファイル名・形式でファイルが出力される"
  - "AC-02: 出力ファイルに original_value（生値）が含まれない（preview のみ）"
  - "AC-03: ツリー出力にはマスク適用ファイルのみが表示され、各ファイルに正しいマスク件数が付記される"
  - "AC-04: スキップファイルがツリー末尾に reason 付きで出力される"
  - "AC-05: 出力先ディレクトリが存在しない場合、自動生成されてからファイルが書き込まれる"
  - "AC-06: 出力ファイルが UTF-8 で書き込まれる（日本語パス・値を含むケース）"

language: "Python"
test_framework: "pytest"
mock_library: "unittest.mock"
coverage_tool: "pytest-cov"
coverage_threshold: 85

task_constraints:
  max_test_cases: 12
  min_test_cases: 5
  refactor_policy: "tests/ と conftest.py のみ変更可。src/ は変更禁止"
```

---

## 1. 作成するファイル

### tests/conftest.py（fixture 追加）

以下の fixture を追加すること。

```python
import pytest
from src.models import DetectionResult, TargetFileEntry

@pytest.fixture
def sample_detections():
    """
    AC-01, AC-02, AC-03 共通サンプル。
    original_value に実値を含めることで AC-02 の漏洩テストを成立させる。
    """
    return [
        DetectionResult(
            file_path="config/database.php",
            line_no=5, column_start=14, column_end=28,
            key_name="password",
            original_value="p@ssw0rd",        # 出力に含まれてはならない
            original_value_preview="p@s***",  # 出力に含めてよい
            category="credential_password",
            rule_type="key_match",
            confidence="high", severity="critical",
            replacement="********",
            auto_maskable=True,
            reason="password key detected",
        ),
        DetectionResult(
            file_path="fuel/app/config/production/db.php",
            line_no=3, column_start=10, column_end=22,
            key_name="hostname",
            original_value="db.example.com",  # 出力に含まれてはならない
            original_value_preview="db.***",
            category="connection_host",
            rule_type="key_match",
            confidence="high", severity="high",
            replacement="dummy-host",
            auto_maskable=True,
            reason="hostname key detected",
        ),
    ]

@pytest.fixture
def sample_target_files():
    """AC-01 Step 1 用サンプル"""
    return [
        TargetFileEntry(
            path="config/database.php",
            file_type=".php", size=1024,
            scan_reason="config配下", risk_level="high",
        ),
        TargetFileEntry(
            path=".env",
            file_type=".env", size=256,
            scan_reason="優先対象ファイル", risk_level="high",
        ),
    ]

@pytest.fixture
def sample_skipped_files():
    """AC-04 スキップファイルサンプル"""
    return [
        {"path": "vendor/autoload.php",    "reason": "excluded path"},
        {"path": "storage/logs/app.log",   "reason": "excluded path"},
        {"path": "config/legacy_sjis.php", "reason": "encoding error"},
    ]
```

---

### tests/test_reporter_export.py（新規作成）

```python
# tests/test_reporter_export.py
import csv
import json
from pathlib import Path
import pytest
from src import reporter  # この時点では export_step が未実装 → ImportError or AttributeError


# AC-01: Step 1〜4 の各タイミングで所定のファイル名・形式でファイルが出力される
def test_step1_export_creates_target_files_csv(tmp_path, sample_target_files):
    out = reporter.export_step(1, sample_target_files, tmp_path)
    assert out.name == "step1_target_files.csv"
    assert out.exists()


# AC-01: Step 2 CSV のカラムが仕様通りであること
def test_step2_export_columns_match_spec(tmp_path, sample_detections):
    out = reporter.export_step(2, sample_detections, tmp_path)
    with open(out, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
    expected = [
        "file_path", "line_no", "key_name", "preview",
        "category", "severity", "replacement", "auto_maskable",
    ]
    assert cols == expected


# AC-01: Step 3 で Markdown ファイルが生成される
def test_step3_dryrun_export_is_markdown(tmp_path, sample_detections):
    out = reporter.export_step(3, sample_detections, tmp_path)
    assert out.name == "step3_dryrun_summary.md"
    assert out.read_text(encoding="utf-8").startswith("#")


# AC-01: Step 4 で JSON ファイルが生成されパースできる
def test_step4_mask_report_is_valid_json(tmp_path, sample_detections):
    out = reporter.export_step(4, sample_detections, tmp_path)
    assert out.name == "step4_mask_report.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(data, (list, dict))


# AC-02: 全出力ファイルに original_value の実値が含まれない
def test_export_does_not_contain_original_value(tmp_path, sample_detections):
    for step in [2, 4]:
        out = reporter.export_step(step, sample_detections, tmp_path)
        content = out.read_text(encoding="utf-8")
        assert "p@ssw0rd" not in content
        assert "db.example.com" not in content


# AC-05: 出力先ディレクトリが存在しない場合に自動生成される
def test_export_creates_output_dir_if_not_exists(tmp_path, sample_target_files):
    new_dir = tmp_path / "new" / "nested" / "dir"
    assert not new_dir.exists()
    reporter.export_step(1, sample_target_files, new_dir)
    assert new_dir.exists()


# AC-06: 出力ファイルが UTF-8 で書き込まれる（日本語パスを含むケース）
def test_export_is_utf8_encoded(tmp_path, sample_target_files):
    sample_target_files[0].path = "設定/データベース.php"
    out = reporter.export_step(1, sample_target_files, tmp_path)
    content = out.read_text(encoding="utf-8")
    assert "設定/データベース.php" in content


# AC-01: 空リストでもファイルが生成される（ヘッダーのみ）
def test_export_empty_results_creates_empty_file(tmp_path):
    out = reporter.export_step(1, [], tmp_path)
    assert out.exists()
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1  # ヘッダー行のみ
```

---

### tests/test_reporter_tree.py（新規作成）

```python
# tests/test_reporter_tree.py
import pytest
from src import reporter  # この時点では export_tree が未実装 → ImportError or AttributeError


# AC-03: マスク適用ファイルのみがツリーに表示される
def test_tree_shows_only_masked_files(tmp_path, sample_detections, sample_skipped_files):
    out = reporter.export_tree(sample_detections, sample_skipped_files, "my-repo", tmp_path)
    content = out.read_text(encoding="utf-8")
    assert "config/database.php" in content
    assert "fuel/app/config/production/db.php" in content
    # マスク対象でないファイルは含まれない
    assert "vendor/autoload.php" not in content.split("## Skipped")[0]


# AC-03: [masked: N items] の件数が正しい
def test_tree_masked_count_per_file(tmp_path, sample_detections, sample_skipped_files):
    out = reporter.export_tree(sample_detections, sample_skipped_files, "my-repo", tmp_path)
    content = out.read_text(encoding="utf-8")
    # config/database.php は sample_detections に1件
    assert "database.php" in content
    assert "[masked: 1 items]" in content


# AC-04: スキップファイルが末尾に reason 付きで出力される
def test_tree_skipped_files_with_reason(tmp_path, sample_detections, sample_skipped_files):
    out = reporter.export_tree(sample_detections, sample_skipped_files, "my-repo", tmp_path)
    content = out.read_text(encoding="utf-8")
    assert "[reason: excluded path]" in content
    assert "[reason: encoding error]" in content
    assert "config/legacy_sjis.php" in content


# AC-03: 4階層以上のネストでもツリーが正しく構成される
def test_tree_deep_nested_path(tmp_path, sample_detections, sample_skipped_files):
    out = reporter.export_tree(sample_detections, sample_skipped_files, "my-repo", tmp_path)
    content = out.read_text(encoding="utf-8")
    # fuel/app/config/production/db.php（4階層）が含まれる
    assert "db.php" in content


# AC-05 / AC-03: 出力ファイル名が仕様通りである
def test_tree_output_filename(tmp_path, sample_detections, sample_skipped_files):
    out = reporter.export_tree(sample_detections, sample_skipped_files, "my-repo", tmp_path)
    assert out.name == "masked_file_tree.md"
```

---

## 2. テスト観点チェックリスト

### Phase 0（必須）

- [ ] **AC-01** Step 1〜4 それぞれで所定のファイル名のファイルが生成される
- [ ] **AC-01** 各出力ファイルのカラム／キーが仕様通りである
- [ ] **AC-02** 出力ファイルに `original_value` の実値が含まれない
- [ ] **AC-03** ツリー出力にマスク適用ファイルのみが表示される
- [ ] **AC-03** `[masked: N items]` の件数が正しい
- [ ] **AC-04** スキップファイルが末尾に `[reason: ...]` 付きで出力される
- [ ] **AC-05** 出力先ディレクトリが存在しない場合に自動生成される
- [ ] **AC-06** 出力ファイルが UTF-8 で書き込まれる

### Phase 1（原則対応）

- [ ] **AC-01** 空リストでもファイルが生成される（ヘッダーのみ）
- [ ] **AC-03** 4階層以上のネストでもツリーが正しく構成される
- [ ] **AC-04** スキップ理由が `excluded path` / `encoding error` で正しく分類される

---

## 3. フェーズ1 終了条件

```bash
# 実行コマンド
pytest tests/test_reporter_export.py tests/test_reporter_tree.py -v
```

以下をすべて満たしたらフェーズ1完了。

- [ ] テストコードが `tests/test_reporter_export.py` / `tests/test_reporter_tree.py` に存在する
- [ ] `tests/conftest.py` に3つの fixture が追加されている
- [ ] pytest を実行すると **全テストが RED（FAIL / ERROR）になる**
- [ ] `src/reporter.py` の `export_step()` / `export_tree()` には **一切手を加えていない**
- [ ] `src/` 配下の既存コードを変更していない

> ✅ RED を確認したら `task-impl-v1.1.md`（フェーズ2）に進んでください。

---

## 4. 禁止事項

| 禁止パターン | 理由 |
|---|---|
| テストを書きながら `reporter.py` の実装も進める | RED を確認できなくなる |
| `assert result is not None` のみのアサーション | 仕様を何も証明しない |
| fixture から `original_value` を省く | AC-02 の漏洩テストが成立しない |
| AC ID のないテストを追加する | 仕様外の観点はスコープ外 |
| `src/` 配下のコードを変更する | フェーズ1のスコープ外 |
