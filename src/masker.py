"""マスキング実行ロジック。

概要:
    DetectionResult に基づいて dry-run 差分生成またはコピー先への apply を行う。
入出力:
    リポジトリパス・出力先・モードを受け取り、MaskRunResult を返す。
制約:
    元リポジトリは変更せず、`.git/` はコピー対象から除外する。
Note:
    dry-run 差分は preview ベースで生成し、生値を表示しない。
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .models import DetectionResult, MaskRunResult
from .reporter import save_reports
from .utils import (
    copy_repository_tree,
    group_by_file,
    load_masking_rules,
    normalise_path,
    read_text_file,
    remove_tree,
    render_unified_diff,
    write_text_file,
)


def mask_text(text: str, detections: list[DetectionResult]) -> str:
    """DetectionResult に基づいてテキストを置換する。

    Args:
        text: 元テキスト。
        detections: 同一ファイル向け検出結果一覧。
    Returns:
        str: 置換後テキスト。
    Raises:
        ValueError: 送出しない。
    Note:
        同一行の複数置換は後ろから適用して列位置のずれを防ぐ。
    """

    lines = text.splitlines(keepends=True)
    by_line: dict[int, list[DetectionResult]] = {}
    for detection in detections:
        by_line.setdefault(detection.line_no, []).append(detection)
    for line_no, line_detections in by_line.items():
        line = lines[line_no - 1]
        for detection in sorted(line_detections, key=lambda item: item.column_start, reverse=True):
            start = detection.column_start - 1
            end = detection.column_end
            line = f"{line[:start]}{detection.replacement}{line[end:]}"
        lines[line_no - 1] = line
    return "".join(lines)


def _preview_text(text: str, detections: list[DetectionResult]) -> str:
    """生値を preview へ置換した安全な変更前テキストを作る。

    Args:
        text: 元テキスト。
        detections: 同一ファイル向け検出結果一覧。
    Returns:
        str: preview 化した変更前テキスト。
    Raises:
        ValueError: 送出しない。
    Note:
        dry-run の差分表示から raw value を除外するために使う。
    """

    preview_detections = [replace(detection, replacement=detection.original_value_preview) for detection in detections]
    return mask_text(text, preview_detections)


def run(
    repo_path: str | Path,
    output_path: str | Path | None = None,
    mode: str = "dry-run",
    target_files: list[str] | None = None,
    detections: list[DetectionResult] | None = None,
    rules: dict | None = None,
) -> MaskRunResult:
    """dry-run または apply を実行する。

    Args:
        repo_path: 元リポジトリパス。
        output_path: apply 先パス。
        mode: `dry-run` または `apply`。
        target_files: 明示的な対象ファイル一覧。
        detections: 事前スキャン済み結果。
        rules: masking_rules.yaml の設定。
    Returns:
        MaskRunResult: 実行結果。
    Raises:
        ValueError: 不正な mode や危険な output_path の場合。
        FileExistsError: 出力先が既に存在する場合。
    Note:
        apply に失敗した場合は output_path を削除してロールバックする。
    """

    if mode not in {"dry-run", "apply"}:
        raise ValueError(f"Unsupported mode: {mode}")

    repository = Path(repo_path)
    resolved_rules = rules or load_masking_rules()
    if detections is None:
        from .scanner import scan_selected_files

        detections = scan_selected_files(repository, target_files=target_files, rules=resolved_rules)

    grouped = group_by_file(detections)
    changed_files: list[str] = []
    diffs: dict[str, str] = {}
    skipped_files: list[str] = []
    masked_cache: dict[str, tuple[str, str]] = {}

    for relative_file, file_detections in grouped.items():
        source_file = repository / relative_file
        text, encoding = read_text_file(source_file)
        if text is None or encoding is None:
            skipped_files.append(relative_file)
            continue
        masked_text = mask_text(text, file_detections)
        if masked_text == text:
            continue
        changed_files.append(relative_file)
        masked_cache[relative_file] = (masked_text, encoding)
        diffs[relative_file] = render_unified_diff(
            _preview_text(text, file_detections),
            masked_text,
            relative_file,
        )

    if mode == "dry-run":
        return MaskRunResult(
            mode="dry-run",
            detections=detections,
            changed_files=changed_files,
            diffs=diffs,
            skipped_files=skipped_files,
        )

    if output_path is None:
        raise ValueError("apply mode requires output_path.")

    destination = Path(output_path)
    if destination.exists():
        raise FileExistsError(f"Output path already exists: {destination}")
    if repository.resolve() in destination.resolve().parents:
        raise ValueError("output_path must be outside the source repository.")

    try:
        copy_repository_tree(repository, destination, resolved_rules["exclude_paths"])
        for relative_file, (masked_text, encoding) in masked_cache.items():
            target_file = destination / relative_file
            write_text_file(target_file, masked_text, encoding)
        report_paths = save_reports(detections, destination)
        return MaskRunResult(
            mode="apply",
            detections=detections,
            changed_files=changed_files,
            diffs=diffs,
            output_path=normalise_path(destination),
            report_paths=report_paths,
            skipped_files=skipped_files,
        )
    except Exception:
        remove_tree(destination)
        raise
