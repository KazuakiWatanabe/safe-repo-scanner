"""DSN 解析ユーティリティ。

概要:
    PDO 形式および URL 形式の DSN を解析し、部分的なマスク対象を抽出する。
入出力:
    DSN 文字列を受け取り、検出対象コンポーネントまたはマスク済み DSN を返す。
制約:
    DSN 全体を置換せず、`host` / `user` / `password` / `dbname` のみを対象にする。
Note:
    Phase 1 では AST 解析を使わず、文字列位置に基づいて安全に部分置換する。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from .models import DetectionResult
from .utils import preview_value

URL_DSN_PATTERN = re.compile(
    r"^(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*://)"
    r"(?:(?P<user>[^:/@?#]+)(?::(?P<password>[^@/?#]*))?@)?"
    r"(?P<host>\[[^\]]+\]|[^:/?#]+)?"
    r"(?::(?P<port>\d+))?"
    r"(?:/(?P<dbname>[^?#;]+))?"
)


@dataclass(slots=True)
class DsnComponent:
    """DSN 内の検出対象要素。"""

    key: str
    value: str
    start: int
    end: int
    category: str
    replacement: str
    severity: str
    reason: str


def _classify_dsn_key(key_name: str, replacement_map: Mapping[str, str]) -> tuple[str, str, str, str] | None:
    """DSN キー名からカテゴリ情報を返す。

    Args:
        key_name: DSN 内キー名。
        replacement_map: 置換値マップ。
    Returns:
        tuple[str, str, str, str] | None: category, replacement, severity, reason。
    Raises:
        ValueError: 送出しない。
    Note:
        DSN 専用のキーのみを扱い、未知キーは None を返す。
    """

    normalized = key_name.lower()
    if normalized == "host":
        return ("connection_host", replacement_map["connection_host"], "high", "DSN host matched.")
    if normalized in {"user", "username"}:
        return ("credential_user", replacement_map["credential_user"], "high", "DSN user matched.")
    if normalized in {"password", "pass"}:
        return (
            "credential_password",
            replacement_map["credential_password"],
            "critical",
            "DSN password matched.",
        )
    if normalized in {"dbname", "database"}:
        return ("db_name", replacement_map["db_name"], "high", "DSN database matched.")
    return None


def _parse_pdo_dsn(dsn: str, replacement_map: Mapping[str, str]) -> list[DsnComponent]:
    """PDO 形式 DSN を解析する。

    Args:
        dsn: DSN 文字列。
        replacement_map: 置換値マップ。
    Returns:
        list[DsnComponent]: 抽出した DSN 要素一覧。
    Raises:
        ValueError: 送出しない。
    Note:
        `mysql:host=...;dbname=...` のような形式を想定する。
    """

    if "://" in dsn or ":" not in dsn:
        return []

    components: list[DsnComponent] = []
    cursor = dsn.index(":") + 1
    for segment in dsn[cursor:].split(";"):
        if "=" not in segment:
            cursor += len(segment) + 1
            continue
        key_name, value = segment.split("=", 1)
        classification = _classify_dsn_key(key_name.strip(), replacement_map)
        value_start = cursor + segment.index("=") + 1
        value_end = value_start + len(value)
        if classification and value:
            category, replacement, severity, reason = classification
            components.append(
                DsnComponent(
                    key=key_name.strip(),
                    value=value,
                    start=value_start,
                    end=value_end,
                    category=category,
                    replacement=replacement,
                    severity=severity,
                    reason=reason,
                )
            )
        cursor += len(segment) + 1
    return components


def _parse_url_dsn(dsn: str, replacement_map: Mapping[str, str]) -> list[DsnComponent]:
    """URL 形式 DSN を解析する。

    Args:
        dsn: DSN 文字列。
        replacement_map: 置換値マップ。
    Returns:
        list[DsnComponent]: 抽出した DSN 要素一覧。
    Raises:
        ValueError: 送出しない。
    Note:
        `mysql://user:pass@host:3306/dbname` のような形式を想定する。
    """

    match = URL_DSN_PATTERN.match(dsn)
    if not match:
        return []

    components: list[DsnComponent] = []
    for group_name, logical_key in (
        ("user", "user"),
        ("password", "password"),
        ("host", "host"),
        ("dbname", "dbname"),
    ):
        value = match.group(group_name)
        if not value:
            continue
        classification = _classify_dsn_key(logical_key, replacement_map)
        if not classification:
            continue
        start, end = match.span(group_name)
        category, replacement, severity, reason = classification
        components.append(
            DsnComponent(
                key=logical_key,
                value=value,
                start=start,
                end=end,
                category=category,
                replacement=replacement,
                severity=severity,
                reason=reason,
            )
        )
    return components


def parse_dsn_components(dsn: str, replacement_map: Mapping[str, str]) -> list[DsnComponent]:
    """DSN 文字列から機密対象を抽出する。

    Args:
        dsn: DSN 文字列。
        replacement_map: 置換値マップ。
    Returns:
        list[DsnComponent]: 抽出結果一覧。
    Raises:
        ValueError: 送出しない。
    Note:
        PDO 形式と URL 形式の両方を順に試す。
    """

    return _parse_url_dsn(dsn, replacement_map) or _parse_pdo_dsn(dsn, replacement_map)


def mask_dsn_string(dsn: str, replacement_map: Mapping[str, str]) -> str:
    """DSN を部分マスクする。

    Args:
        dsn: マスク対象 DSN。
        replacement_map: 置換値マップ。
    Returns:
        str: 部分マスク済み DSN。
    Raises:
        ValueError: 送出しない。
    Note:
        コンポーネントは後ろから適用し、位置ずれを防ぐ。
    """

    masked = dsn
    for component in sorted(parse_dsn_components(dsn, replacement_map), key=lambda item: item.start, reverse=True):
        masked = f"{masked[:component.start]}{component.replacement}{masked[component.end:]}"
    return masked


def build_dsn_detections(
    file_path: str,
    line_no: int,
    column_offset: int,
    dsn: str,
    replacement_map: Mapping[str, str],
    key_name: str | None = None,
) -> list[DetectionResult]:
    """DSN 文字列から DetectionResult を組み立てる。

    Args:
        file_path: リポジトリ相対パス。
        line_no: 行番号。
        column_offset: 行頭から DSN 値開始までの 0-based オフセット。
        dsn: DSN 文字列。
        replacement_map: 置換値マップ。
        key_name: 外側のキー名。
    Returns:
        list[DetectionResult]: DSN 由来の検出結果。
    Raises:
        ValueError: 送出しない。
    Note:
        column_start / column_end は行全体基準の 1-based 値へ変換する。
    """

    detections: list[DetectionResult] = []
    for component in parse_dsn_components(dsn, replacement_map):
        detections.append(
            DetectionResult(
                file_path=file_path,
                line_no=line_no,
                column_start=column_offset + component.start + 1,
                column_end=column_offset + component.end,
                key_name=key_name,
                original_value=component.value,
                original_value_preview=preview_value(component.value),
                category=component.category,
                rule_type="dsn_component",
                confidence="high",
                severity=component.severity,  # type: ignore[arg-type]
                replacement=component.replacement,
                auto_maskable=True,
                reason=component.reason,
            )
        )
    return detections
