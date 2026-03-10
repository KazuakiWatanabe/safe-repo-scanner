"""スキャン CLI と統合フロー。

概要:
    対象ファイル候補の生成、ファイル単位スキャン、レポート出力、mask 実行を
    まとめる CLI エントリポイントを提供する。
入出力:
    リポジトリパスや CLI 引数を受け取り、DetectionResult や実行結果を返す。
制約:
    ファイル読み取りはローカルのみで行い、外部通信を行わない。
Note:
    `python -m src.scanner` から利用することを想定する。
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .detectors import detect_text
from .masker import run as run_masker
from .reporter import render_report, save_report
from .target_file_selector import generate_target_file_entries
from .utils import load_masking_rules, normalise_path, read_text_file


def scan_selected_files(
    repo_path: str | Path,
    target_files: list[str] | None = None,
    rules: dict | None = None,
) -> list:
    """選択済みファイル群をスキャンする。

    Args:
        repo_path: リポジトリルート。
        target_files: 対象ファイルの相対パス一覧。未指定時は候補一覧から selected 全件。
        rules: masking_rules.yaml の設定。
    Returns:
        list: DetectionResult 一覧。
    Raises:
        FileNotFoundError: 対象ファイルが存在しない場合。
    Note:
        文字エンコーディング判定に失敗したファイルは静かにスキップする。
    """

    repository = Path(repo_path)
    resolved_rules = rules or load_masking_rules()
    selected_paths = target_files
    if selected_paths is None:
        selected_paths = [entry.path for entry in generate_target_file_entries(repository, resolved_rules) if entry.selected]

    detections = []
    for relative_path in selected_paths:
        file_path = repository / relative_path
        text, _ = read_text_file(file_path)
        if text is None:
            continue
        detections.extend(detect_text(relative_path, text, resolved_rules))
    detections.sort(key=lambda item: (item.file_path, item.line_no, item.column_start))
    return detections


def scan_repository(repo_path: str | Path, rules: dict | None = None) -> tuple[list, list]:
    """候補生成とスキャンをまとめて実行する。

    Args:
        repo_path: リポジトリルート。
        rules: masking_rules.yaml の設定。
    Returns:
        tuple[list, list]: TargetFileEntry 一覧と DetectionResult 一覧。
    Raises:
        FileNotFoundError: リポジトリが存在しない場合。
    Note:
        UI 側の簡易フローで利用する。
    """

    resolved_rules = rules or load_masking_rules()
    entries = generate_target_file_entries(repo_path, resolved_rules)
    detections = scan_selected_files(repo_path, [entry.path for entry in entries if entry.selected], resolved_rules)
    return entries, detections


def build_parser() -> argparse.ArgumentParser:
    """CLI パーサーを構築する。

    Args:
        なし
    Returns:
        argparse.ArgumentParser: CLI パーサー。
    Raises:
        ValueError: 送出しない。
    Note:
        Phase 1 の `scan`, `report`, `mask` サブコマンドを提供する。
    """

    parser = argparse.ArgumentParser(prog="safe-repo-scanner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("repo_path")
    scan_parser.add_argument("--format", choices=("json", "csv", "md"), default="json")

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("repo_path")
    report_parser.add_argument("--format", choices=("json", "csv", "md"), default="md")
    report_parser.add_argument("--output")

    mask_parser = subparsers.add_parser("mask")
    mask_parser.add_argument("repo_path")
    mask_parser.add_argument("--output")
    mode_group = mask_parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--dry-run", action="store_true")
    mode_group.add_argument("--apply", action="store_true")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI を実行する。

    Args:
        argv: 解析対象引数。未指定時は sys.argv を使う。
    Returns:
        int: 終了コード。
    Raises:
        ValueError: 不正引数や危険な apply 条件の場合。
    Note:
        レポート未指定時は標準出力へ安全な preview レポートを表示する。
    """

    parser = build_parser()
    args = parser.parse_args(argv)
    rules = load_masking_rules()

    if args.command == "scan":
        detections = scan_selected_files(args.repo_path, rules=rules)
        print(render_report(detections, args.format))
        return 0

    if args.command == "report":
        detections = scan_selected_files(args.repo_path, rules=rules)
        if args.output:
            save_report(detections, args.output, args.format)
        else:
            print(render_report(detections, args.format))
        return 0

    mode = "apply" if args.apply else "dry-run"
    result = run_masker(args.repo_path, output_path=args.output, mode=mode, rules=rules)
    print(f"mode={result.mode}")
    print(f"detections={len(result.detections)}")
    print(f"changed_files={len(result.changed_files)}")
    if result.output_path:
        print(f"output_path={normalise_path(result.output_path)}")
    if result.report_paths:
        print("reports=" + ",".join(normalise_path(path) for path in result.report_paths))
    for file_path, diff_text in result.diffs.items():
        print(f"--- {file_path} ---")
        print(diff_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
