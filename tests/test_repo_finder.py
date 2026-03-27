"""repo_finder のテスト。

概要:
    Git ルート探索が `.git` ディレクトリ、`.git` ファイル、管理下サブディレクトリを
    正しく扱うことを検証する。
入出力:
    ワークスペース配下の一時ディレクトリを作成し、repo_finder の戻り値を確認する。
制約:
    実 Git コマンドは使わず、`.git` と `HEAD` を手動生成して期待値を固定する。
Note:
    Windows sandbox で安定させるため `test/.pytest_tmp/runtime` 配下を利用する。
"""

import shutil
from pathlib import Path
from uuid import uuid4

from src.repo_finder import discover_repositories, find_enclosing_repository_root


def test_find_enclosing_repository_root_accepts_git_managed_subdirectory() -> None:
    """Git 管理下のサブディレクトリを対象として受け入れる。"""

    runtime_root = Path("test/.pytest_tmp/runtime")
    runtime_root.mkdir(parents=True, exist_ok=True)
    workspace = runtime_root / f"repo-finder-{uuid4().hex}"
    workspace.mkdir(parents=True, exist_ok=False)

    try:
        repo_path = workspace / "mono-repo"
        target_path = repo_path / "packages" / "management-develop"
        (repo_path / ".git").mkdir(parents=True)
        (repo_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        target_path.mkdir(parents=True, exist_ok=False)

        resolved_root = find_enclosing_repository_root(target_path)

        assert resolved_root == repo_path
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_discover_repositories_supports_git_file_worktree() -> None:
    """`.git` ファイルで参照される linked worktree も探索できる。"""

    runtime_root = Path("test/.pytest_tmp/runtime")
    runtime_root.mkdir(parents=True, exist_ok=True)
    workspace = runtime_root / f"repo-finder-{uuid4().hex}"
    workspace.mkdir(parents=True, exist_ok=False)

    try:
        metadata_dir = workspace / "git-metadata" / "worktree-repo"
        worktree_repo = workspace / "worktree-repo"
        metadata_dir.mkdir(parents=True, exist_ok=False)
        worktree_repo.mkdir(parents=True, exist_ok=False)
        (metadata_dir / "HEAD").write_text("ref: refs/heads/develop\n", encoding="utf-8")
        (worktree_repo / ".git").write_text("gitdir: ../git-metadata/worktree-repo\n", encoding="utf-8")

        repositories = discover_repositories(workspace)

        assert [repo.path for repo in repositories] == [str(worktree_repo)]
        assert repositories[0].branch == "develop"
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
