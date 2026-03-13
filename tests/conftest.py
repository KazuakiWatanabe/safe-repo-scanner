"""pytest 共通 fixture 定義。

概要:
    reporter v1.1 の Step Export / Tree Export テストで共通利用する
    DetectionResult と TargetFileEntry のサンプルを提供する。
    v1.2 ではメールアドレス検出テスト用の fixture を追加する。
入出力:
    pytest fixture としてサンプルデータを返す。
制約:
    `original_value` には実値を含め、出力漏洩テストを成立させる。
Note:
    `src/` 実装は変更せず、テスト側のみで仕様を固定する。
"""

from __future__ import annotations

import shutil
import textwrap
from pathlib import Path
from uuid import uuid4

import pytest

from src.models import DetectionResult, TargetFileEntry


@pytest.fixture
def reporter_output_dir() -> Path:
    """ワークスペース配下の書込可能な出力ディレクトリを返す。

    Args:
        なし。
    Returns:
        Path: テスト専用の一意な出力ディレクトリ。
    Raises:
        OSError: ディレクトリ作成に失敗した場合。
    Note:
        Windows sandbox で `tmp_path` が権限エラーになるため手動生成する。
    """

    runtime_root = Path("test/.pytest_tmp/runtime")
    runtime_root.mkdir(parents=True, exist_ok=True)
    output_dir = runtime_root / f"reporter-{uuid4().hex}"
    output_dir.mkdir(parents=True, exist_ok=False)
    try:
        yield output_dir
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


@pytest.fixture
def sample_detections() -> list[DetectionResult]:
    """Step Export / Tree Export 共通の検出結果を返す。

    Args:
        なし。
    Returns:
        list[DetectionResult]: 生値を含むサンプル検出結果。
    Raises:
        なし。
    Note:
        AC-02 のため `original_value` は出力へ含まれてはならない値を持つ。
    """

    return [
        DetectionResult(
            file_path="config/database.php",
            line_no=5,
            column_start=14,
            column_end=28,
            key_name="password",
            original_value="p@ssw0rd",
            original_value_preview="p@s***",
            category="credential_password",
            rule_type="key_match",
            confidence="high",
            severity="critical",
            replacement="********",
            auto_maskable=True,
            reason="password key detected",
        ),
        DetectionResult(
            file_path="fuel/app/config/production/db.php",
            line_no=3,
            column_start=10,
            column_end=22,
            key_name="hostname",
            original_value="db.example.com",
            original_value_preview="db.***",
            category="connection_host",
            rule_type="key_match",
            confidence="high",
            severity="high",
            replacement="dummy-host",
            auto_maskable=True,
            reason="hostname key detected",
        ),
    ]


@pytest.fixture
def sample_target_files() -> list[TargetFileEntry]:
    """Step 1 用の対象ファイル一覧を返す。

    Args:
        なし。
    Returns:
        list[TargetFileEntry]: CSV 出力検証向けの対象ファイル一覧。
    Raises:
        なし。
    Note:
        Step 1 の列仕様と UTF-8 出力検証で再利用する。
    """

    return [
        TargetFileEntry(
            path="config/database.php",
            file_type=".php",
            size=1024,
            scan_reason="config配下",
            risk_level="high",
        ),
        TargetFileEntry(
            path=".env",
            file_type=".env",
            size=256,
            scan_reason="優先対象ファイル",
            risk_level="high",
        ),
    ]


@pytest.fixture
def sample_skipped_files() -> list[dict[str, str]]:
    """Tree Export 用のスキップファイル一覧を返す。

    Args:
        なし。
    Returns:
        list[dict[str, str]]: スキップ理由付きファイル一覧。
    Raises:
        なし。
    Note:
        AC-04 の reason 表示検証で使用する。
    """

    return [
        {"path": "vendor/autoload.php", "reason": "excluded path"},
        {"path": "storage/logs/app.log", "reason": "excluded path"},
        {"path": "config/legacy_sjis.php", "reason": "encoding error"},
    ]


@pytest.fixture
def php_email_fixture() -> str:
    """PHP メールアドレス検出テスト用のサンプルテキストを返す。

    Args:
        なし。
    Returns:
        str: email / from_address キーを含む PHP 配列テキスト。
    Raises:
        なし。
    Note:
        TC-D-01 / TC-M-01 で使用する。
    """

    return textwrap.dedent("""\
        'email' => 'admin@myapp.jp',
        'from_address' => 'noreply@myapp.jp',
    """)


@pytest.fixture
def env_email_fixture() -> str:
    """ENV メールアドレス検出テスト用のサンプルテキストを返す。

    Args:
        なし。
    Returns:
        str: MAIL_FROM_ADDRESS / MAIL_USERNAME を含む ENV テキスト。
    Raises:
        なし。
    Note:
        TC-D-02 / TC-M-02 で使用する。
    """

    return textwrap.dedent("""\
        MAIL_FROM_ADDRESS=hello@myapp.jp
        MAIL_USERNAME=apikey@sendgrid.net
    """)


@pytest.fixture
def yaml_email_fixture() -> str:
    """YAML メールアドレス検出テスト用のサンプルテキストを返す。

    Args:
        なし。
    Returns:
        str: from / reply_to キーを含む YAML テキスト。
    Raises:
        なし。
    Note:
        TC-D-03 / TC-M-03 で使用する。
    """

    return textwrap.dedent("""\
        mailer:
          from: no-reply@myapp.jp
          reply_to: support@myapp.jp
    """)


@pytest.fixture
def php_email_pattern_fixture() -> str:
    """値パターンマッチ検出テスト用のサンプルテキストを返す。

    Args:
        なし。
    Returns:
        str: EMAIL_KEY_NAMES に含まれないキーでメールアドレス値を持つ PHP テキスト。
    Raises:
        なし。
    Note:
        TC-D-04 で使用する。contact は EMAIL_KEY_NAMES に含まれない。
    """

    return "'contact' => 'info@myapp.jp',"


@pytest.fixture
def php_smtp_email_fixture() -> str:
    """SMTP username メールアドレス検出テスト用のサンプルテキストを返す。

    Args:
        なし。
    Returns:
        str: username がメールアドレス形式の SMTP 設定 PHP テキスト。
    Raises:
        なし。
    Note:
        TC-D-07 / TC-M-06 で使用する。
    """

    return textwrap.dedent("""\
        'smtp' => [
            'username' => 'user@sendgrid.net',
            'password' => 'secret',
        ],
    """)
