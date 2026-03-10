"""レポート出力ロジック。

概要:
    DetectionResult の一覧を JSON / CSV / Markdown に整形し、preview のみを
    含む安全なレポートを出力する。
入出力:
    検出結果と出力形式を受け取り、文字列または保存ファイルパスを返す。
制約:
    `original_value` は一切出力しない。
Note:
    apply 実行時は 3 形式をまとめて保存できる。
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Iterable

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
