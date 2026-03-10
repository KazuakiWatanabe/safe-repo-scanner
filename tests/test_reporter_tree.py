"""reporter.export_tree の RED テスト。

概要:
    Tree Export v1.1 の受け入れ条件を pytest で固定し、未実装状態で RED を確認する。
入出力:
    検出結果一覧、スキップファイル一覧、リポジトリ名を `reporter.export_tree()` に渡す。
制約:
    ツリーにはマスク適用ファイルのみを表示し、スキップ一覧は末尾に出力する。
Note:
    Phase 1 では `export_tree()` 未実装による FAIL / ERROR を期待する。
"""

from __future__ import annotations

from pathlib import Path

from src import reporter


def test_tree_shows_only_masked_files(
    reporter_output_dir: Path,
    sample_detections,
    sample_skipped_files,
) -> None:
    """マスク適用ファイルのみがツリー本体に表示されることを検証する。

    Args:
        reporter_output_dir: ワークスペース配下の出力ディレクトリ。
        sample_detections: マスク済みファイルの検出結果一覧。
        sample_skipped_files: スキップファイル一覧。
    Returns:
        None
    Raises:
        AssertionError: ツリー本体に不要なファイルが混在する場合。
    Note:
        `## Skipped` より前をツリー本体とみなして確認する。
    """

    out = reporter.export_tree(sample_detections, sample_skipped_files, "my-repo", reporter_output_dir)
    content = out.read_text(encoding="utf-8")
    assert "config/database.php" in content
    assert "fuel/app/config/production/db.php" in content
    assert "vendor/autoload.php" not in content.split("## Skipped")[0]


def test_tree_masked_count_per_file(
    reporter_output_dir: Path,
    sample_detections,
    sample_skipped_files,
) -> None:
    """各ファイルの `[masked: N items]` 件数が正しいことを検証する。

    Args:
        reporter_output_dir: ワークスペース配下の出力ディレクトリ。
        sample_detections: マスク件数付きで集計する検出結果一覧。
        sample_skipped_files: スキップファイル一覧。
    Returns:
        None
    Raises:
        AssertionError: マスク件数表記が仕様と異なる場合。
    Note:
        `config/database.php` は fixture 上 1 件である前提を固定する。
    """

    out = reporter.export_tree(sample_detections, sample_skipped_files, "my-repo", reporter_output_dir)
    content = out.read_text(encoding="utf-8")
    assert "database.php" in content
    assert "[masked: 1 items]" in content


def test_tree_skipped_files_with_reason(
    reporter_output_dir: Path,
    sample_detections,
    sample_skipped_files,
) -> None:
    """スキップファイルが reason 付きで末尾に出力されることを検証する。

    Args:
        reporter_output_dir: ワークスペース配下の出力ディレクトリ。
        sample_detections: マスク済みファイルの検出結果一覧。
        sample_skipped_files: スキップファイル一覧。
    Returns:
        None
    Raises:
        AssertionError: スキップ理由または対象ファイルが欠落する場合。
    Note:
        `excluded path` と `encoding error` の両方を確認する。
    """

    out = reporter.export_tree(sample_detections, sample_skipped_files, "my-repo", reporter_output_dir)
    content = out.read_text(encoding="utf-8")
    assert "[reason: excluded path]" in content
    assert "[reason: encoding error]" in content
    assert "config/legacy_sjis.php" in content


def test_tree_deep_nested_path(
    reporter_output_dir: Path,
    sample_detections,
    sample_skipped_files,
) -> None:
    """4階層以上のネストでもツリーに含まれることを検証する。

    Args:
        reporter_output_dir: ワークスペース配下の出力ディレクトリ。
        sample_detections: 深い階層パスを含む検出結果一覧。
        sample_skipped_files: スキップファイル一覧。
    Returns:
        None
    Raises:
        AssertionError: 深い階層のファイルがツリーから欠落する場合。
    Note:
        `fuel/app/config/production/db.php` を対象にする。
    """

    out = reporter.export_tree(sample_detections, sample_skipped_files, "my-repo", reporter_output_dir)
    content = out.read_text(encoding="utf-8")
    assert "db.php" in content


def test_tree_output_filename(
    reporter_output_dir: Path,
    sample_detections,
    sample_skipped_files,
) -> None:
    """Tree Export の出力ファイル名が仕様通りであることを検証する。

    Args:
        reporter_output_dir: ワークスペース配下の出力ディレクトリ。
        sample_detections: マスク済みファイルの検出結果一覧。
        sample_skipped_files: スキップファイル一覧。
    Returns:
        None
    Raises:
        AssertionError: 出力ファイル名が仕様と異なる場合。
    Note:
        AC-05 とファイル命名仕様を合わせて確認する。
    """

    out = reporter.export_tree(sample_detections, sample_skipped_files, "my-repo", reporter_output_dir)
    assert out.name == "masked_file_tree.md"
