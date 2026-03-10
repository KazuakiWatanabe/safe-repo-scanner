"""データモデル定義。

概要:
    リポジトリ探索、対象ファイル選択、検出結果、マスク実行結果で共有する
    dataclass を定義する。
入出力:
    他モジュールから import されるデータ構造を提供する。
制約:
    生値の永続化は内部処理に限定し、外部出力は preview を使う。
Note:
    DetectionResult.original_value は内部処理専用であり、レポート出力には使わない。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass(slots=True)
class RepoEntry:
    """Git リポジトリエントリ。"""

    name: str
    path: str
    branch: str
    last_updated: str
    selected: bool = False


@dataclass(slots=True)
class TargetFileEntry:
    """スキャン対象ファイルエントリ。"""

    path: str
    file_type: str
    size: int
    scan_reason: str
    risk_level: Literal["high", "medium", "low"]
    selected: bool = True
    excluded_reason: Optional[str] = None


@dataclass(slots=True)
class DetectionResult:
    """機密情報検出結果。"""

    file_path: str
    line_no: int
    column_start: int
    column_end: int
    key_name: Optional[str]
    original_value: str
    original_value_preview: str
    category: str
    rule_type: str
    confidence: Literal["high", "medium", "low"]
    severity: Literal["critical", "high", "medium", "low"]
    replacement: str
    auto_maskable: bool
    reason: str


@dataclass(slots=True)
class MaskRunResult:
    """dry-run / apply 実行結果。"""

    mode: Literal["dry-run", "apply"]
    detections: list[DetectionResult]
    changed_files: list[str]
    diffs: dict[str, str]
    output_path: Optional[str] = None
    report_paths: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)
