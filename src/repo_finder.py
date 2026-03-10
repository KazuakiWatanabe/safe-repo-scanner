"""Git リポジトリ探索ロジック。

概要:
    指定ルート配下を再帰的に走査し、`.git` ディレクトリを持つローカル Git
    リポジトリ一覧を返す。
入出力:
    検索ルートを受け取り、RepoEntry の一覧を返す。
制約:
    外部コマンドへ依存せず、`.git/HEAD` を直接読んでブランチ名を取得する。
Note:
    repo search 自体は read-only で実行する。
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from .models import RepoEntry


def _read_branch_name(repo_path: Path) -> str:
    """`.git/HEAD` からブランチ名を得る。

    Args:
        repo_path: リポジトリパス。
    Returns:
        str: ブランチ名または detached 指示。
    Raises:
        OSError: `.git/HEAD` の読み込みに失敗した場合。
    Note:
        detached HEAD の場合は短い commit 参照にフォールバックする。
    """

    head_path = repo_path / ".git" / "HEAD"
    if not head_path.exists():
        return "unknown"
    content = head_path.read_text(encoding="utf-8").strip()
    if content.startswith("ref: "):
        return content.rsplit("/", maxsplit=1)[-1]
    return f"detached:{content[:7]}"


def _last_updated(repo_path: Path) -> str:
    """リポジトリの最終更新日時を返す。

    Args:
        repo_path: リポジトリパス。
    Returns:
        str: `%Y-%m-%d %H:%M:%S` 形式の日時文字列。
    Raises:
        OSError: stat に失敗した場合。
    Note:
        `.git` を除くワークツリーの最大 mtime を使う。
    """

    latest_mtime = repo_path.stat().st_mtime
    for current_root, dir_names, file_names in os.walk(repo_path):
        dir_names[:] = [dir_name for dir_name in dir_names if dir_name != ".git"]
        for file_name in file_names:
            file_path = Path(current_root) / file_name
            latest_mtime = max(latest_mtime, file_path.stat().st_mtime)
    return datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d %H:%M:%S")


def discover_repositories(search_root: str | Path | None = None) -> list[RepoEntry]:
    """ローカル Git リポジトリを探索する。

    Args:
        search_root: 探索起点。未指定時はホームディレクトリ。
    Returns:
        list[RepoEntry]: 見つかったリポジトリ一覧。
    Raises:
        FileNotFoundError: search_root が存在しない場合。
    Note:
        ネストされた Git リポジトリも拾えるよう、`.git` だけを探索除外する。
    """

    root = Path(search_root or Path.home()).expanduser()
    repositories: list[RepoEntry] = []
    for current_root, dir_names, _ in os.walk(root):
        if ".git" in dir_names:
            repo_path = Path(current_root)
            repositories.append(
                RepoEntry(
                    name=repo_path.name,
                    path=str(repo_path),
                    branch=_read_branch_name(repo_path),
                    last_updated=_last_updated(repo_path),
                )
            )
            dir_names[:] = [dir_name for dir_name in dir_names if dir_name != ".git"]
    repositories.sort(key=lambda item: item.path.lower())
    return repositories
