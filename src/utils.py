"""共通ユーティリティ。

概要:
    設定読込、preview 生成、エンコーディング判定、パス正規化、差分生成、
    安全なコピー処理などを提供する。
入出力:
    ファイルパスやテキストを受け取り、内部処理向けの標準化結果を返す。
制約:
    外部通信は行わず、レポート用途では生値を返さない。
Note:
    Windows 11 を主対象とするため、パスは表示用途で POSIX 形式に正規化する。
"""

from __future__ import annotations

import difflib
import os
import shutil
from pathlib import Path
from typing import Iterable, Sequence

import chardet
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".zip",
    ".gz",
    ".tar",
    ".7z",
    ".pdf",
    ".exe",
    ".dll",
    ".so",
    ".class",
    ".jar",
}


def load_masking_rules(config_path: str | Path | None = None) -> dict:
    """マスキング設定を読み込む。

    Args:
        config_path: 設定ファイルパス。未指定時はリポジトリ直下を使う。
    Returns:
        dict: 読み込んだ YAML 設定。
    Raises:
        FileNotFoundError: 設定ファイルが存在しない場合。
        yaml.YAMLError: YAML の構文が不正な場合。
    Note:
        Phase 1 では必須設定の欠落を補完せず、そのまま例外として扱う。
    """

    resolved_path = Path(config_path) if config_path else ROOT_DIR / "masking_rules.yaml"
    with resolved_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def preview_value(value: str) -> str:
    """生値から preview を生成する。

    Args:
        value: 元の生値。
    Returns:
        str: 先頭 3 文字 + "***" 形式の preview。
    Raises:
        ValueError: 送出しない。
    Note:
        値が空でも "***" を返し、ログやレポートに空文字を残さない。
    """

    return f"{value[:3]}***"


def normalise_path(path: str | Path) -> str:
    """パスを POSIX 形式へ正規化する。

    Args:
        path: 正規化対象パス。
    Returns:
        str: スラッシュ区切りの相対・絶対パス文字列。
    Raises:
        ValueError: 送出しない。
    Note:
        表示とマッチ判定を安定させるために使用する。
    """

    return str(path).replace("\\", "/")


def is_excluded_path(path: str | Path, exclude_paths: Sequence[str]) -> bool:
    """除外パスに一致するか判定する。

    Args:
        path: 判定対象の相対パスまたは絶対パス。
        exclude_paths: 除外パターン一覧。
    Returns:
        bool: 除外対象なら True。
    Raises:
        ValueError: 送出しない。
    Note:
        `.git/` や `vendor/` のようなディレクトリ除外を優先する。
    """

    normalized = normalise_path(path).strip("/")
    parts = [part for part in normalized.split("/") if part]
    for raw_pattern in exclude_paths:
        pattern = normalise_path(raw_pattern).strip("/")
        if not pattern:
            continue
        if normalized == pattern or normalized.startswith(f"{pattern}/"):
            return True
        if "/" not in pattern and pattern in parts:
            return True
    return False


def is_probably_binary(file_path: str | Path, raw_bytes: bytes) -> bool:
    """バイナリファイルらしさを判定する。

    Args:
        file_path: 判定対象ファイルパス。
        raw_bytes: 先頭を含むファイル生バイト列。
    Returns:
        bool: バイナリとみなす場合は True。
    Raises:
        ValueError: 送出しない。
    Note:
        明示的な拡張子と NULL バイトの両方で判定する。
    """

    suffix = Path(file_path).suffix.lower()
    return suffix in BINARY_EXTENSIONS or b"\x00" in raw_bytes


def detect_text_encoding(raw_bytes: bytes) -> str | None:
    """バイト列から文字エンコーディングを推定する。

    Args:
        raw_bytes: 判定対象バイト列。
    Returns:
        str | None: 推定エンコーディング。失敗時は None。
    Raises:
        ValueError: 送出しない。
    Note:
        chardet の結果に加え、日本語 Windows 環境で頻出の候補を順に試す。
    """

    detected = chardet.detect(raw_bytes)
    candidates = [detected.get("encoding"), "utf-8", "cp932", "shift_jis", "euc_jp"]
    for candidate in dict.fromkeys(candidate for candidate in candidates if candidate):
        try:
            raw_bytes.decode(candidate)
            return candidate
        except UnicodeDecodeError:
            continue
    return None


def read_text_file(file_path: str | Path) -> tuple[str | None, str | None]:
    """テキストファイルを安全に読み込む。

    Args:
        file_path: 読み込むファイルパス。
    Returns:
        tuple[str | None, str | None]: テキスト本体と使用エンコーディング。
    Raises:
        OSError: ファイル読み込みに失敗した場合。
    Note:
        判定不能またはバイナリとみなしたファイルは `(None, None)` を返す。
    """

    raw_bytes = Path(file_path).read_bytes()
    if is_probably_binary(file_path, raw_bytes):
        return None, None
    encoding = detect_text_encoding(raw_bytes)
    if not encoding:
        return None, None
    return raw_bytes.decode(encoding), encoding


def write_text_file(file_path: str | Path, text: str, encoding: str) -> None:
    """指定エンコーディングでテキストを書き込む。

    Args:
        file_path: 書き込み先パス。
        text: 書き込むテキスト。
        encoding: 書き込みエンコーディング。
    Returns:
        None
    Raises:
        OSError: 書き込みに失敗した場合。
    Note:
        newline を明示せず、入力テキスト内の改行をそのまま維持する。
    """

    with Path(file_path).open("w", encoding=encoding, newline="") as handle:
        handle.write(text)


def render_unified_diff(before_text: str, after_text: str, file_path: str) -> str:
    """統一 diff を生成する。

    Args:
        before_text: 変更前テキスト。
        after_text: 変更後テキスト。
        file_path: 表示用ファイルパス。
    Returns:
        str: unified diff 文字列。
    Raises:
        ValueError: 送出しない。
    Note:
        呼び出し元で preview 済みテキストを渡せば、生値を漏らさずに差分確認できる。
    """

    diff = difflib.unified_diff(
        before_text.splitlines(),
        after_text.splitlines(),
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm="",
    )
    return "\n".join(diff)


def copy_repository_tree(source_dir: str | Path, destination_dir: str | Path, exclude_paths: Sequence[str]) -> None:
    """除外ルール付きでリポジトリをコピーする。

    Args:
        source_dir: コピー元ディレクトリ。
        destination_dir: コピー先ディレクトリ。
        exclude_paths: 除外パターン一覧。
    Returns:
        None
    Raises:
        FileExistsError: コピー先が既に存在する場合。
        OSError: コピーに失敗した場合。
    Note:
        `.git/` は必ず除外し、元リポジトリの履歴を持ち込まない。
    """

    source = Path(source_dir)
    destination = Path(destination_dir)
    if destination.exists():
        raise FileExistsError(f"Output path already exists: {destination}")

    for current_root, dir_names, file_names in os.walk(source):
        relative_root = Path(current_root).relative_to(source)
        filtered_dirs = []
        for dir_name in dir_names:
            candidate = relative_root / dir_name
            if not is_excluded_path(candidate, exclude_paths):
                filtered_dirs.append(dir_name)
        dir_names[:] = filtered_dirs

        target_root = destination / relative_root
        target_root.mkdir(parents=True, exist_ok=True)
        for file_name in file_names:
            relative_file = relative_root / file_name
            if is_excluded_path(relative_file, exclude_paths):
                continue
            target_file = destination / relative_file
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative_file, target_file)


def remove_tree(path: str | Path) -> None:
    """ディレクトリを削除する。

    Args:
        path: 削除対象パス。
    Returns:
        None
    Raises:
        OSError: 削除に失敗した場合。
    Note:
        失敗時のクリーンアップ用途のみで使用する。
    """

    shutil.rmtree(path, ignore_errors=True)


def group_by_file(results: Iterable) -> dict[str, list]:
    """file_path 単位で結果をグループ化する。

    Args:
        results: DetectionResult の iterable。
    Returns:
        dict[str, list]: file_path をキーとした辞書。
    Raises:
        AttributeError: file_path 属性を持たない要素が混ざった場合。
    Note:
        マスキング適用時の再読み込み回数を減らすために使用する。
    """

    grouped: dict[str, list] = {}
    for result in results:
        grouped.setdefault(result.file_path, []).append(result)
    return grouped
