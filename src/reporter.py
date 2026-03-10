"""レポート出力ロジック。

概要:
    DetectionResult の一覧を JSON / CSV / Markdown に整形し、preview のみを
    含む安全なレポートを出力する。v1.1 では Step Export / Tree Export も担う。
入出力:
    検出結果と出力形式を受け取り、文字列または保存ファイルパスを返す。
制約:
    `original_value` は一切出力しない。
Note:
    apply 実行時は 3 形式をまとめて保存でき、追加でステップ別証跡も出力できる。
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .models import DetectionResult


def serialise_results(results: Iterable[DetectionResult]) -> list[dict[str, object]]:
    """DetectionResult を安全な辞書へ変換する。

    Args:
        results: 検出結果一覧。
    Returns:
        list[dict[str, object]]: preview のみを含む辞書一覧。
    Raises:
        ValueError: 送出しない。
    Note:
        original_value は明示的に除外する。
    """

    return [
        {
            "category": result.category,
            "key_name": result.key_name,
            "preview": result.original_value_preview,
            "file_path": result.file_path,
            "line_no": result.line_no,
            "column_start": result.column_start,
            "column_end": result.column_end,
            "rule_type": result.rule_type,
            "confidence": result.confidence,
            "severity": result.severity,
            "replacement": result.replacement,
            "auto_maskable": result.auto_maskable,
            "reason": result.reason,
        }
        for result in results
    ]


def _extract_row_value(item: object, field_name: str) -> object:
    """dict または dataclass 風オブジェクトから値を取り出す。

    Args:
        item: 変換対象の要素。
        field_name: 取得したいフィールド名。
    Returns:
        object: 取得した値。
    Raises:
        AttributeError: dict でも属性でも該当項目が見つからない場合。
    Note:
        Step Export の入力型を緩く保つために使用する。
    """

    return item[field_name] if isinstance(item, dict) else getattr(item, field_name)


def _write_csv_rows(fieldnames: list[str], rows: list[dict[str, object]], output_path: Path) -> Path:
    """CSV を UTF-8 で保存する。

    Args:
        fieldnames: CSV ヘッダー順。
        rows: 書き込む行データ。
        output_path: 保存先ファイルパス。
    Returns:
        Path: 保存したファイルパス。
    Raises:
        OSError: 保存に失敗した場合。
    Note:
        改行は csv モジュールに委ね、UTF-8 固定で出力する。
    """

    with output_path.open("w", encoding="utf-8", newline="") as file_pointer:
        writer = csv.DictWriter(file_pointer, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def _render_dry_run_summary(results: Iterable[DetectionResult]) -> str:
    """dry-run 向け Markdown サマリーを生成する。

    Args:
        results: 検出結果一覧。
    Returns:
        str: Markdown 形式のサマリー文字列。
    Raises:
        ValueError: 送出しない。
    Note:
        ファイルごとの変更予定件数だけを出力し、生値は含めない。
    """

    counts_by_file: dict[str, int] = {}
    total_changes = 0
    for result in results:
        counts_by_file[result.file_path] = counts_by_file.get(result.file_path, 0) + 1
        total_changes += 1

    lines = [
        "# Dry-run Summary",
        "",
        f"- Total planned changes: {total_changes}",
        f"- Changed files: {len(counts_by_file)}",
        "",
        "## Planned changes by file",
    ]
    file_lines = [f"- {file_path}: {counts_by_file[file_path]} items" for file_path in sorted(counts_by_file)]
    lines.extend(file_lines or ["- (no changes)"])
    return "\n".join(lines) + "\n"


def export_step(step: int, results: list[Any], output_dir: Path) -> Path:
    """各ステップの結果を証跡ファイルとして保存する。

    Args:
        step: ステップ番号。1 から 4 を受け付ける。
        results: ステップごとの出力対象一覧。
        output_dir: 出力先ディレクトリ。
    Returns:
        Path: 保存したファイルパス。
    Raises:
        ValueError: 未対応の step が指定された場合。
        OSError: ファイル保存に失敗した場合。
    Note:
        出力先ディレクトリは存在しない場合に自動生成し、UTF-8 固定で書き込む。
    """

    output_base = Path(output_dir)
    output_base.mkdir(parents=True, exist_ok=True)

    if step == 1:
        fieldnames = ["path", "file_type", "size", "scan_reason", "risk_level"]
        rows = [
            {field_name: _extract_row_value(result, field_name) for field_name in fieldnames}
            for result in results
        ]
        return _write_csv_rows(fieldnames, rows, output_base / "step1_target_files.csv")

    if step == 2:
        fieldnames = [
            "file_path",
            "line_no",
            "key_name",
            "preview",
            "category",
            "severity",
            "replacement",
            "auto_maskable",
        ]
        rows = [
            {
                "file_path": result.file_path,
                "line_no": result.line_no,
                "key_name": result.key_name,
                "preview": result.original_value_preview,
                "category": result.category,
                "severity": result.severity,
                "replacement": result.replacement,
                "auto_maskable": result.auto_maskable,
            }
            for result in results
        ]
        return _write_csv_rows(fieldnames, rows, output_base / "step2_scan_results.csv")

    if step == 3:
        target = output_base / "step3_dryrun_summary.md"
        target.write_text(_render_dry_run_summary(results), encoding="utf-8")
        return target

    if step == 4:
        saved_paths = save_reports(results, output_base, base_name="step4_mask_report", formats=("json",))
        return Path(saved_paths[0])

    raise ValueError(f"Unsupported step: {step}")


def _build_masked_tree(masked_results: Iterable[DetectionResult]) -> dict[str, Any]:
    """マスク済みファイル一覧を階層辞書へ変換する。

    Args:
        masked_results: マスク済み検出結果一覧。
    Returns:
        dict[str, Any]: ディレクトリとファイルを表す入れ子辞書。
    Raises:
        ValueError: 送出しない。
    Note:
        葉ノードは `__files__` に `(file_name, full_path, count)` を保持する。
    """

    counts_by_file: dict[str, int] = {}
    for result in masked_results:
        counts_by_file[result.file_path] = counts_by_file.get(result.file_path, 0) + 1

    tree: dict[str, Any] = {}
    for file_path in sorted(counts_by_file):
        parts = file_path.split("/")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node.setdefault("__files__", []).append((parts[-1], file_path, counts_by_file[file_path]))
    return tree


def _render_tree_lines(tree: dict[str, Any], depth: int = 0) -> list[str]:
    """階層辞書を Markdown の箇条書きツリーへ変換する。

    Args:
        tree: `_build_masked_tree()` が返す階層辞書。
        depth: 現在の深さ。
    Returns:
        list[str]: 1 行ずつのツリー文字列。
    Raises:
        ValueError: 送出しない。
    Note:
        テストで全文字列検索できるよう、葉にはフルパスも併記する。
    """

    lines: list[str] = []
    indent = "  " * depth
    directory_names = sorted(name for name in tree if name != "__files__")
    for directory_name in directory_names:
        lines.append(f"{indent}- {directory_name}/")
        lines.extend(_render_tree_lines(tree[directory_name], depth + 1))

    files = sorted(tree.get("__files__", []), key=lambda item: item[1])
    for file_name, full_path, count in files:
        lines.append(f"{indent}- {file_name} [masked: {count} items] ({full_path})")
    return lines


def export_tree(
    masked_results: list[DetectionResult],
    skipped_files: list[dict[str, str]],
    repo_name: str,
    output_dir: Path,
) -> Path:
    """マスク済みファイルのツリーを Markdown として保存する。

    Args:
        masked_results: マスク済み検出結果一覧。
        skipped_files: スキップファイル情報一覧。
        repo_name: 対象リポジトリ名。
        output_dir: 出力先ディレクトリ。
    Returns:
        Path: 保存した `masked_file_tree.md` のパス。
    Raises:
        OSError: ファイル保存に失敗した場合。
    Note:
        ツリー本体にはマスク適用ファイルのみを出し、スキップ一覧は末尾に分離する。
    """

    output_base = Path(output_dir)
    output_base.mkdir(parents=True, exist_ok=True)

    tree = _build_masked_tree(masked_results)
    tree_lines = _render_tree_lines(tree)
    counts_by_file = {result.file_path for result in masked_results}
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# Masked File Tree",
        f"## Repository: {repo_name}",
        f"## Masked at: {timestamp}",
        f"## Total masked files: {len(counts_by_file)}",
        "",
        f"{repo_name}/",
    ]
    lines.extend(tree_lines or ["- (no masked files)"])

    lines.extend(["", f"## Skipped files ({len(skipped_files)})"])
    for skipped_file in skipped_files:
        lines.append(f"- {skipped_file['path']} [reason: {skipped_file['reason']}]")

    target = output_base / "masked_file_tree.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def render_report(results: Iterable[DetectionResult], output_format: str) -> str:
    """指定形式でレポート文字列を生成する。

    Args:
        results: 検出結果一覧。
        output_format: `json` / `csv` / `md`。
    Returns:
        str: 整形済みレポート文字列。
    Raises:
        ValueError: 未対応形式が指定された場合。
    Note:
        Markdown は GitHub 互換の簡易テーブル形式を返す。
    """

    rows = serialise_results(results)
    if output_format == "json":
        return json.dumps(rows, ensure_ascii=False, indent=2)
    if output_format == "csv":
        buffer = io.StringIO()
        fieldnames = list(rows[0].keys()) if rows else ["category", "key_name", "preview"]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue()
    if output_format == "md":
        header = "| category | key_name | preview | file_path | line_no | rule_type | confidence | replacement | auto_maskable |\n"
        divider = "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        body = "".join(
            f"| {row['category']} | {row['key_name'] or ''} | {row['preview']} | {row['file_path']} | "
            f"{row['line_no']} | {row['rule_type']} | {row['confidence']} | {row['replacement']} | "
            f"{row['auto_maskable']} |\n"
            for row in rows
        )
        return header + divider + body
    raise ValueError(f"Unsupported report format: {output_format}")


def save_report(results: Iterable[DetectionResult], output_path: str | Path, output_format: str) -> str:
    """レポートをファイル保存する。

    Args:
        results: 検出結果一覧。
        output_path: 保存先パス。
        output_format: `json` / `csv` / `md`。
    Returns:
        str: 保存したファイルパス。
    Raises:
        OSError: ファイル保存に失敗した場合。
        ValueError: 未対応形式が指定された場合。
    Note:
        文字コードは UTF-8 固定とする。
    """

    content = render_report(results, output_format)
    target = Path(output_path)
    target.write_text(content, encoding="utf-8")
    return str(target)


def save_reports(
    results: Iterable[DetectionResult],
    output_dir: str | Path,
    base_name: str = "mask_report",
    formats: tuple[str, ...] = ("json", "csv", "md"),
) -> list[str]:
    """複数形式のレポートを一括保存する。

    Args:
        results: 検出結果一覧。
        output_dir: 保存先ディレクトリ。
        base_name: ベースファイル名。
        formats: 保存形式一覧。
    Returns:
        list[str]: 保存したファイルパス一覧。
    Raises:
        OSError: 保存に失敗した場合。
    Note:
        apply 時の証跡をまとめて残すために使用する。
    """

    output_base = Path(output_dir)
    saved_paths: list[str] = []
    for output_format in formats:
        file_path = output_base / f"{base_name}.{output_format}"
        saved_paths.append(save_report(results, file_path, output_format))
    return saved_paths
