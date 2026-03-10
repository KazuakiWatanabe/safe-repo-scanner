"""機密情報検出ロジック。

概要:
    PHP / ENV / YAML / JSON / INI / CONF / XML の基本的なキー値形式を走査し、
    DetectionResult の一覧を返す。
入出力:
    ファイルパスと UTF-8 正規化済みテキストを受け取り、検出結果を返す。
制約:
    Phase 1 は正規表現 + 行コンテキスト判定のみを使用し、生値出力を行わない。
Note:
    DSN は dsn_parser を通じて部分置換可能な形で扱う。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

from .dsn_parser import build_dsn_detections, parse_dsn_components
from .models import DetectionResult
from .utils import preview_value

ENV_ASSIGNMENT_PATTERN = re.compile(
    r"^\s*(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.+?)\s*(?:#.*)?$"
)
PHP_ASSIGNMENT_PATTERN = re.compile(
    r"""^\s*['"](?P<key>[^'"]+)['"]\s*=>\s*(?P<value>'(?:\\.|[^'])*'|"(?:\\.|[^"])*"|[^,\r\n]+)"""
)
JSON_ASSIGNMENT_PATTERN = re.compile(
    r'^\s*"(?P<key>[^"]+)"\s*:\s*(?P<value>"(?:\\.|[^"])*"|[^,\r\n]+)'
)
MAPPING_ASSIGNMENT_PATTERN = re.compile(
    r"^\s*(?P<key>[A-Za-z0-9_.-]+)\s*[:=]\s*(?P<value>.+?)\s*$"
)
XML_ASSIGNMENT_PATTERN = re.compile(r"^\s*<(?P<key>[A-Za-z0-9_.-]+)>(?P<value>[^<]+)</(?P=key)>\s*$")
IPV4_PATTERN = re.compile(r"^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)$")
HOST_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z]{2,}$")
JWT_PATTERN = re.compile(r"^[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+$")
BEARER_PATTERN = re.compile(r"^Bearer\s+[A-Za-z0-9\-._~+/]+=*$")


def _unwrap_value(line: str, raw_value: str, start_hint: int) -> tuple[str, int, int]:
    """値トークンから実値と位置を取り出す。

    Args:
        line: 元の 1 行文字列。
        raw_value: 正規表現で抽出した値トークン。
        start_hint: line 内の探索開始位置。
    Returns:
        tuple[str, int, int]: 実値, 0-based 開始位置, 0-based 終了位置。
    Raises:
        ValueError: 送出しない。
    Note:
        引用符付き文字列は外側の引用符を除いて返す。
    """

    token = raw_value.strip()
    token_start = line.find(token, start_hint)
    if token.startswith(("'", '"')) and token.endswith(("'", '"')) and len(token) >= 2:
        value = token[1:-1]
        return value, token_start + 1, token_start + 1 + len(value)
    return token.rstrip(","), token_start, token_start + len(token.rstrip(","))


def _classify_key(
    key_name: str | None,
    value: str,
    replacement_map: Mapping[str, str],
    non_maskable_keys: set[str],
) -> dict[str, str] | None:
    """キー名と値からカテゴリを推定する。

    Args:
        key_name: 抽出したキー名。
        value: 実値。
        replacement_map: 置換値マップ。
        non_maskable_keys: 非マスク対象キー集合。
    Returns:
        dict[str, str] | None: カテゴリ情報。該当なしなら None。
    Raises:
        ValueError: 送出しない。
    Note:
        キー名優先で判定し、値パターンは補助的にのみ利用する。
    """

    normalized = (key_name or "").strip().lower()
    if normalized in non_maskable_keys:
        return None

    direct_map = {
        "host": ("connection_host", replacement_map["connection_host"], "high"),
        "hostname": ("connection_host", replacement_map["connection_host"], "high"),
        "server": ("connection_host", replacement_map["connection_host"], "high"),
        "db_host": ("connection_host", replacement_map["connection_host"], "high"),
        "username": ("credential_user", replacement_map["credential_user"], "high"),
        "user": ("credential_user", replacement_map["credential_user"], "high"),
        "login": ("credential_user", replacement_map["credential_user"], "high"),
        "account": ("credential_user", replacement_map["credential_user"], "high"),
        "db_username": ("credential_user", replacement_map["credential_user"], "high"),
        "password": ("credential_password", replacement_map["credential_password"], "critical"),
        "pass": ("credential_password", replacement_map["credential_password"], "critical"),
        "passwd": ("credential_password", replacement_map["credential_password"], "critical"),
        "pwd": ("credential_password", replacement_map["credential_password"], "critical"),
        "db_password": ("credential_password", replacement_map["credential_password"], "critical"),
        "dbname": ("db_name", replacement_map["db_name"], "high"),
        "database": ("db_name", replacement_map["db_name"], "high"),
        "db_name": ("db_name", replacement_map["db_name"], "high"),
        "api_key": ("api_key", replacement_map["api_key"], "high"),
        "aws_access_key_id": ("api_key", replacement_map["api_key"], "high"),
        "secret": ("secret", replacement_map["secret"], "critical"),
        "secret_key": ("secret", replacement_map["secret"], "critical"),
        "client_secret": ("secret", replacement_map["secret"], "critical"),
        "aws_secret_access_key": ("secret", replacement_map["secret"], "critical"),
        "access_token": ("token", replacement_map["token"], "critical"),
        "refresh_token": ("token", replacement_map["token"], "critical"),
        "private_key": ("private_key", replacement_map["private_key"], "critical"),
    }
    if normalized in direct_map:
        category, replacement, severity = direct_map[normalized]
        return {
            "category": category,
            "replacement": replacement,
            "severity": severity,
            "confidence": "high",
            "rule_type": "key_name",
            "reason": f"Sensitive key '{key_name}' matched.",
        }

    if "password" in normalized:
        return {
            "category": "credential_password",
            "replacement": replacement_map["credential_password"],
            "severity": "critical",
            "confidence": "high",
            "rule_type": "key_name",
            "reason": f"Sensitive key '{key_name}' matched by heuristic.",
        }
    if normalized.endswith("_host") or normalized.endswith("host"):
        return {
            "category": "connection_host",
            "replacement": replacement_map["connection_host"],
            "severity": "high",
            "confidence": "medium",
            "rule_type": "key_name",
            "reason": f"Host-like key '{key_name}' matched by heuristic.",
        }
    if "token" in normalized:
        return {
            "category": "token",
            "replacement": replacement_map["token"],
            "severity": "critical",
            "confidence": "medium",
            "rule_type": "key_name",
            "reason": f"Token-like key '{key_name}' matched by heuristic.",
        }
    if "secret" in normalized:
        return {
            "category": "secret",
            "replacement": replacement_map["secret"],
            "severity": "critical",
            "confidence": "medium",
            "rule_type": "key_name",
            "reason": f"Secret-like key '{key_name}' matched by heuristic.",
        }
    if IPV4_PATTERN.fullmatch(value):
        return {
            "category": "ip_address",
            "replacement": replacement_map["ip_address"],
            "severity": "medium",
            "confidence": "medium",
            "rule_type": "value_pattern",
            "reason": "IPv4 address matched.",
        }
    if HOST_PATTERN.fullmatch(value):
        return {
            "category": "connection_host",
            "replacement": replacement_map["connection_host"],
            "severity": "medium",
            "confidence": "low",
            "rule_type": "value_pattern",
            "reason": "Host-like value matched.",
        }
    if JWT_PATTERN.fullmatch(value) or BEARER_PATTERN.fullmatch(value):
        return {
            "category": "token",
            "replacement": replacement_map["token"],
            "severity": "critical",
            "confidence": "medium",
            "rule_type": "value_pattern",
            "reason": "Token-like value matched.",
        }
    return None


def _is_dsn_candidate(key_name: str | None, value: str, replacement_map: Mapping[str, str]) -> bool:
    """値が DSN として扱えるか判定する。

    Args:
        key_name: 外側のキー名。
        value: 実値。
        replacement_map: 置換値マップ。
    Returns:
        bool: DSN として解析すべきなら True。
    Raises:
        ValueError: 送出しない。
    Note:
        キー名ヒントまたは値パターンのどちらかで判定する。
    """

    normalized = (key_name or "").lower()
    if normalized == "dsn" or "dsn" in normalized or normalized.endswith("_url"):
        return bool(parse_dsn_components(value, replacement_map))
    return bool(parse_dsn_components(value, replacement_map))


def _build_detection(
    file_path: str,
    line_no: int,
    key_name: str | None,
    value: str,
    value_start: int,
    value_end: int,
    metadata: Mapping[str, str],
) -> DetectionResult:
    """DetectionResult を構築する。"""

    return DetectionResult(
        file_path=file_path,
        line_no=line_no,
        column_start=value_start + 1,
        column_end=value_end,
        key_name=key_name,
        original_value=value,
        original_value_preview=preview_value(value),
        category=metadata["category"],
        rule_type=metadata["rule_type"],
        confidence=metadata["confidence"],  # type: ignore[arg-type]
        severity=metadata["severity"],  # type: ignore[arg-type]
        replacement=metadata["replacement"],
        auto_maskable=True,
        reason=metadata["reason"],
    )


def _detect_line(
    line: str,
    file_path: str,
    line_no: int,
    pattern: re.Pattern[str],
    replacement_map: Mapping[str, str],
    non_maskable_keys: set[str],
) -> list[DetectionResult]:
    """1 行に対してパターンベース検出を実行する。"""

    match = pattern.match(line)
    if not match:
        return []

    key_name = match.group("key")
    raw_value = match.group("value")
    value, value_start, value_end = _unwrap_value(line, raw_value, match.start("value"))
    if not value:
        return []

    if _is_dsn_candidate(key_name, value, replacement_map):
        dsn_detections = build_dsn_detections(
            file_path=file_path,
            line_no=line_no,
            column_offset=value_start,
            dsn=value,
            replacement_map=replacement_map,
            key_name=key_name,
        )
        if dsn_detections:
            return dsn_detections

    metadata = _classify_key(key_name, value, replacement_map, non_maskable_keys)
    if not metadata:
        return []
    return [_build_detection(file_path, line_no, key_name, value, value_start, value_end, metadata)]


def detect_text(file_path: str, text: str, rules: Mapping[str, object]) -> list[DetectionResult]:
    """テキスト全体を走査して機密候補を返す。

    Args:
        file_path: リポジトリ相対パス。
        text: UTF-8 正規化済みテキスト。
        rules: masking_rules.yaml の設定。
    Returns:
        list[DetectionResult]: 検出結果一覧。
    Raises:
        ValueError: 送出しない。
    Note:
        対象フォーマットに応じて最小限のパターンを使い分ける。
    """

    replacement_map = rules["replacement_map"]  # type: ignore[index]
    non_maskable_keys = {item.lower() for item in rules["non_maskable_keys"]}  # type: ignore[index]
    path_obj = Path(file_path)
    suffix = path_obj.suffix.lower()
    file_name = path_obj.name.lower()

    if file_name == ".env" or file_name.startswith(".env."):
        pattern = ENV_ASSIGNMENT_PATTERN
    elif suffix == ".php":
        pattern = PHP_ASSIGNMENT_PATTERN
    elif suffix in {".yaml", ".yml", ".ini", ".conf"}:
        pattern = MAPPING_ASSIGNMENT_PATTERN
    elif suffix == ".json":
        pattern = JSON_ASSIGNMENT_PATTERN
    elif suffix == ".xml":
        pattern = XML_ASSIGNMENT_PATTERN
    else:
        pattern = MAPPING_ASSIGNMENT_PATTERN

    detections: list[DetectionResult] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//")):
            continue
        detections.extend(_detect_line(line, file_path, line_no, pattern, replacement_map, non_maskable_keys))
    detections.sort(key=lambda item: (item.file_path, item.line_no, item.column_start))
    return detections
