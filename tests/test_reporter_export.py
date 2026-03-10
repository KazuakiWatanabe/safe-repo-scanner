"""reporter.export_step の RED テスト。

概要:
    Step Export v1.1 の受け入れ条件を pytest で固定し、未実装状態で RED を確認する。
入出力:
    fixture から渡した対象ファイル一覧や検出結果を `reporter.export_step()` に渡す。
制約:
    `src/reporter.py` は変更せず、テストだけを追加する。
Note:
    Phase 1 では `export_step()` 未実装による FAIL / ERROR を期待する。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src import reporter


def test_step1_export_creates_target_files_csv(
    reporter_output_dir: Path,
    sample_target_files,
) -> None:
    """Step 1 で対象ファイル CSV が生成されることを検証する。

    Args:
        reporter_output_dir: ワークスペース配下の出力ディレクトリ。
        sample_target_files: Step 1 用の対象ファイル一覧。
    Returns:
        None
    Raises:
        AssertionError: ファイル名または生成結果が仕様と異なる場合。
    Note:
        Phase 1 では `reporter.export_step()` 未実装のため RED を期待する。
    """

    out = reporter.export_step(1, sample_target_files, reporter_output_dir)
    assert out.name == "step1_target_files.csv"
    assert out.exists()


def test_step2_export_columns_match_spec(
    reporter_output_dir: Path,
    sample_detections,
) -> None:
    """Step 2 CSV のカラムが仕様通りであることを検証する。

    Args:
        reporter_output_dir: ワークスペース配下の出力ディレクトリ。
        sample_detections: Step 2 用の検出結果一覧。
    Returns:
        None
    Raises:
        AssertionError: カラム定義が仕様と一致しない場合。
    Note:
        preview のみを含む CSV ヘッダー順を固定する。
    """

    out = reporter.export_step(2, sample_detections, reporter_output_dir)
    with open(out, encoding="utf-8") as file_pointer:
        reader = csv.DictReader(file_pointer)
        cols = reader.fieldnames
    expected = [
        "file_path",
        "line_no",
        "key_name",
        "preview",
        "category",
        "severity",
        "replacement",
        "auto_maskable",
    ]
    assert cols == expected


def test_step3_dryrun_export_is_markdown(
    reporter_output_dir: Path,
    sample_detections,
) -> None:
    """Step 3 で Markdown サマリーが生成されることを検証する。

    Args:
        reporter_output_dir: ワークスペース配下の出力ディレクトリ。
        sample_detections: dry-run サマリー入力用の検出結果一覧。
    Returns:
        None
    Raises:
        AssertionError: 生成ファイル名または Markdown 形式が不正な場合。
    Note:
        先頭 `#` により Markdown 見出し出力を確認する。
    """

    out = reporter.export_step(3, sample_detections, reporter_output_dir)
    assert out.name == "step3_dryrun_summary.md"
    assert out.read_text(encoding="utf-8").startswith("#")


def test_step4_mask_report_is_valid_json(
    reporter_output_dir: Path,
    sample_detections,
) -> None:
    """Step 4 で JSON レポートが生成されることを検証する。

    Args:
        reporter_output_dir: ワークスペース配下の出力ディレクトリ。
        sample_detections: Step 4 用の検出結果一覧。
    Returns:
        None
    Raises:
        AssertionError: JSON ファイル名またはパース結果が仕様と異なる場合。
    Note:
        JSON の最上位型は list または dict のいずれかを許容する。
    """

    out = reporter.export_step(4, sample_detections, reporter_output_dir)
    assert out.name == "step4_mask_report.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(data, (list, dict))


def test_export_does_not_contain_original_value(
    reporter_output_dir: Path,
    sample_detections,
) -> None:
    """全出力に `original_value` の実値が含まれないことを検証する。

    Args:
        reporter_output_dir: ワークスペース配下の出力ディレクトリ。
        sample_detections: 生値を含む検出結果一覧。
    Returns:
        None
    Raises:
        AssertionError: 生値が出力に含まれる場合。
    Note:
        AC-02 に対応し、preview のみ出力される前提を固定する。
    """

    for step in [2, 4]:
        out = reporter.export_step(step, sample_detections, reporter_output_dir)
        content = out.read_text(encoding="utf-8")
        assert "p@ssw0rd" not in content
        assert "db.example.com" not in content


def test_export_creates_output_dir_if_not_exists(
    reporter_output_dir: Path,
    sample_target_files,
) -> None:
    """出力先ディレクトリが未作成でも自動生成されることを検証する。

    Args:
        reporter_output_dir: ワークスペース配下の出力ディレクトリ。
        sample_target_files: Step 1 用の対象ファイル一覧。
    Returns:
        None
    Raises:
        AssertionError: ディレクトリ自動生成に失敗した場合。
    Note:
        AC-05 の自動生成要件を固定する。
    """

    new_dir = reporter_output_dir / "new" / "nested" / "dir"
    assert not new_dir.exists()
    reporter.export_step(1, sample_target_files, new_dir)
    assert new_dir.exists()


def test_export_is_utf8_encoded(
    reporter_output_dir: Path,
    sample_target_files,
) -> None:
    """日本語パスを含めても UTF-8 で書き込まれることを検証する。

    Args:
        reporter_output_dir: ワークスペース配下の出力ディレクトリ。
        sample_target_files: Step 1 用の対象ファイル一覧。
    Returns:
        None
    Raises:
        AssertionError: UTF-8 で読み戻せない、または日本語が欠落する場合。
    Note:
        AC-06 の日本語ケースに対応する。
    """

    sample_target_files[0].path = "設定/データベース.php"
    out = reporter.export_step(1, sample_target_files, reporter_output_dir)
    content = out.read_text(encoding="utf-8")
    assert "設定/データベース.php" in content


def test_export_empty_results_creates_empty_file(reporter_output_dir: Path) -> None:
    """空リストでもヘッダーのみのファイルが生成されることを検証する。

    Args:
        reporter_output_dir: ワークスペース配下の出力ディレクトリ。
    Returns:
        None
    Raises:
        AssertionError: 空入力時にファイル生成されない場合。
    Note:
        Phase 1 の原則対応観点としてヘッダーのみ出力を固定する。
    """

    out = reporter.export_step(1, [], reporter_output_dir)
    assert out.exists()
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
