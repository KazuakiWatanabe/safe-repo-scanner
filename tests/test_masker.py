"""Masker の統合テスト。

概要:
    dry-run の安全な差分と apply の安全なコピー出力を検証する。
入出力:
    ワークスペース内に一時リポジトリを作成し、戻り値と出力ファイルを確認する。
制約:
    元リポジトリは変更せず、`.git/` はコピーしない。
Note:
    Windows sandbox で `tempfile.mkdtemp()` 配下が書込不可になるため、
    ワークスペース直下に手動で一意ディレクトリを作成する。
"""

import shutil
from pathlib import Path
from uuid import uuid4

from src.masker import run
from src.utils import load_masking_rules


def test_masker_dry_run_and_apply_keep_source_safe() -> None:
    """dry-run と apply の両方で安全要件を満たす。"""

    runtime_root = Path("test/.pytest_tmp/runtime")
    runtime_root.mkdir(parents=True, exist_ok=True)
    workspace = runtime_root / f"masker-{uuid4().hex}"
    workspace.mkdir(parents=True, exist_ok=False)

    try:
        repo_path = workspace / "legacy-repo"
        output_path = workspace / "legacy-repo-masked"
        (repo_path / ".git").mkdir(parents=True)
        (repo_path / "config").mkdir(parents=True)

        database_file = repo_path / "config" / "database.php"
        env_file = repo_path / ".env"
        database_text = "<?php\nreturn [\n    'username' => 'A',\n    'password' => 'B',\n];\n"
        env_text = "DB_HOST=db.example.com\nDB_PASSWORD=p@ssw0rd\nAWS_SECRET_ACCESS_KEY=xxxxxxxx\n"
        database_file.write_text(database_text, encoding="utf-8")
        env_file.write_text(env_text, encoding="utf-8")

        rules = load_masking_rules()
        dry_run_result = run(repo_path, output_path=output_path, mode="dry-run", rules=rules)

        assert database_file.read_text(encoding="utf-8") == database_text
        assert env_file.read_text(encoding="utf-8") == env_text
        assert "p@ssw0rd" not in "\n".join(dry_run_result.diffs.values())
        assert "p@s***" in "\n".join(dry_run_result.diffs.values())

        apply_result = run(repo_path, output_path=output_path, mode="apply", rules=rules)
        masked_database_text = (output_path / "config" / "database.php").read_text(encoding="utf-8")
        masked_env_text = (output_path / ".env").read_text(encoding="utf-8")
        report_text = (output_path / "mask_report.json").read_text(encoding="utf-8")

        assert not (output_path / ".git").exists()
        assert "'username' => 'dummy_user'" in masked_database_text
        assert "'password' => '********'" in masked_database_text
        assert "DB_HOST=dummy-host" in masked_env_text
        assert "DB_PASSWORD=********" in masked_env_text
        assert "AWS_SECRET_ACCESS_KEY=dummy_secret" in masked_env_text
        assert database_file.read_text(encoding="utf-8") == database_text
        assert env_file.read_text(encoding="utf-8") == env_text
        assert "p@ssw0rd" not in report_text
        assert "p@s***" in report_text
        assert any(path.endswith("mask_report.json") for path in apply_result.report_paths)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
