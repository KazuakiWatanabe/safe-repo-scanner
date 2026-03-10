"""対象ファイル候補の選定ロジック。

概要:
    リポジトリ配下のファイルを走査し、優先ルールと条件付きルールに基づいて
    スキャン対象候補を生成する。
入出力:
    リポジトリパスと設定を受け取り、TargetFileEntry の一覧を返す。
制約:
    `.git/` や vendor などの除外ディレクトリ、およびバイナリは候補にしない。
Note:
    Phase 1 は高再現率を優先し、suspicious key の軽量走査を併用する。
"""

from __future__ import annotations

import os
from pathlib import Path

from .models import TargetFileEntry
from .utils import BINARY_EXTENSIONS, is_excluded_path, normalise_path, read_text_file

CONDITIONAL_KEYWORDS = {"db", "database", "mail", "smtp", "service", "auth", "oauth", "secret"}


def _file_type(file_path: Path) -> str:
    """表示用ファイル種別を返す。

    Args:
        file_path: 対象パス。
    Returns:
        str: 拡張子ベースの種別名。
    Raises:
        ValueError: 送出しない。
    Note:
        `.env` は suffix が空になるため専用扱いにする。
    """

    if file_path.name == ".env" or file_path.name.startswith(".env."):
        return "env"
    return file_path.suffix.lower().lstrip(".") or "unknown"


def _priority_reasons(relative_path: str) -> list[tuple[str, str]]:
    """優先ルールに一致する理由一覧を返す。

    Args:
        relative_path: POSIX 形式のリポジトリ相対パス。
    Returns:
        list[tuple[str, str]]: `(理由, risk_level)` の一覧。
    Raises:
        ValueError: 送出しない。
    Note:
        明示的に指定された config 配下や `.env` を優先対象とする。
    """

    reasons: list[tuple[str, str]] = []
    if relative_path == ".env" or relative_path.startswith(".env."):
        reasons.append(("priority: env file", "high"))
    if relative_path.startswith("config/") and relative_path.endswith((".php", ".yaml", ".yml", ".json")):
        reasons.append(("priority: config path", "high"))
    if relative_path.startswith("fuel/app/config/") and relative_path.endswith(".php"):
        reasons.append(("priority: fuel config path", "high"))
    if relative_path.startswith("config/packages/") and relative_path.endswith((".yaml", ".yml")):
        reasons.append(("priority: package config path", "high"))
    if relative_path in {"config/services.php", "config/database.php", "config/app.php", "config/app_local.php"}:
        reasons.append(("priority: framework config file", "high"))
    return reasons


def _conditional_reasons(relative_path: str, file_path: Path, suspicious_keys: list[str]) -> list[tuple[str, str]]:
    """条件付きルールに一致する理由一覧を返す。

    Args:
        relative_path: POSIX 形式の相対パス。
        file_path: 実ファイルパス。
        suspicious_keys: 軽量走査に使う suspicious key 一覧。
    Returns:
        list[tuple[str, str]]: `(理由, risk_level)` の一覧。
    Raises:
        ValueError: 送出しない。
    Note:
        軽量走査は先頭数 KB のみを対象とし、全件読み込みを避ける。
    """

    reasons: list[tuple[str, str]] = []
    lowered_path = relative_path.lower()
    if lowered_path.startswith("config/") or "/config/" in lowered_path:
        reasons.append(("conditional: config directory", "medium"))
    if any(keyword in lowered_path for keyword in CONDITIONAL_KEYWORDS):
        reasons.append(("conditional: keyword in path", "medium"))

    text, _ = read_text_file(file_path)
    if text:
        header = text[:4096].lower()
        if any(key.lower() in header for key in suspicious_keys):
            reasons.append(("conditional: suspicious key in header", "high"))
    return reasons


def generate_target_file_entries(repo_path: str | Path, rules: dict) -> list[TargetFileEntry]:
    """対象ファイル候補一覧を生成する。

    Args:
        repo_path: リポジトリルート。
        rules: masking_rules.yaml の設定。
    Returns:
        list[TargetFileEntry]: スキャン候補一覧。
    Raises:
        FileNotFoundError: リポジトリが存在しない場合。
    Note:
        候補に採用しないファイルは一覧へ含めない。
    """

    repo = Path(repo_path)
    include_extensions = {item.lower() for item in rules["include_extensions"]}
    exclude_paths = rules["exclude_paths"]
    suspicious_keys = rules["suspicious_keys"]

    entries: list[TargetFileEntry] = []
    for current_root, dir_names, file_names in os.walk(repo):
        relative_root = Path(current_root).relative_to(repo)
        dir_names[:] = [
            dir_name for dir_name in dir_names if not is_excluded_path(relative_root / dir_name, exclude_paths)
        ]
        for file_name in file_names:
            file_path = Path(current_root) / file_name
            relative_path = normalise_path(file_path.relative_to(repo))
            if is_excluded_path(relative_path, exclude_paths):
                continue
            if file_path.suffix.lower() in BINARY_EXTENSIONS:
                continue

            extension = file_path.suffix.lower()
            is_env_file = file_path.name == ".env" or file_path.name.startswith(".env.")
            if not is_env_file and extension not in include_extensions:
                continue

            reasons = _priority_reasons(relative_path)
            reasons.extend(_conditional_reasons(relative_path, file_path, suspicious_keys))
            if not reasons:
                continue

            risk_level = "low"
            if any(level == "high" for _, level in reasons):
                risk_level = "high"
            elif any(level == "medium" for _, level in reasons):
                risk_level = "medium"

            entries.append(
                TargetFileEntry(
                    path=relative_path,
                    file_type=_file_type(file_path),
                    size=file_path.stat().st_size,
                    scan_reason=", ".join(dict.fromkeys(reason for reason, _ in reasons)),
                    risk_level=risk_level,  # type: ignore[arg-type]
                )
            )
    entries.sort(key=lambda item: item.path)
    return entries
