"""メールマスキングのテスト。

概要:
    メールアドレスを含む各ファイル形式に対してマスキング結果を検証する。
入出力:
    fixture 経由のサンプルテキストを検出・マスクし、置換結果を確認する。
制約:
    元リポジトリは変更せず、生値を出力しない。
Note:
    v1.2 の TC-M-01〜TC-M-07 を担保する。
"""

from src.detectors import detect_text
from src.masker import mask_text
from src.utils import load_masking_rules


def test_mask_email_php(php_email_fixture: str) -> None:
    """TC-M-01: PHP の email / from_address キーが dummy@example.com に置換されること。"""

    rules = load_masking_rules()
    detections = detect_text("config/mail.php", php_email_fixture, rules)
    masked = mask_text(php_email_fixture, detections)

    assert "'email' => 'dummy@example.com'" in masked
    assert "'from_address' => 'dummy@example.com'" in masked


def test_mask_email_env(env_email_fixture: str) -> None:
    """TC-M-02: MAIL_FROM_ADDRESS / MAIL_USERNAME が dummy@example.com に置換されること。"""

    rules = load_masking_rules()
    detections = detect_text(".env", env_email_fixture, rules)
    masked = mask_text(env_email_fixture, detections)

    assert "MAIL_FROM_ADDRESS=dummy@example.com" in masked
    assert "MAIL_USERNAME=dummy@example.com" in masked


def test_mask_email_yaml(yaml_email_fixture: str) -> None:
    """TC-M-03: from / reply_to が dummy@example.com に置換されること。"""

    rules = load_masking_rules()
    detections = detect_text("config/mailer.yaml", yaml_email_fixture, rules)
    masked = mask_text(yaml_email_fixture, detections)

    assert "from: dummy@example.com" in masked
    assert "reply_to: dummy@example.com" in masked


def test_mask_email_placeholder_domain_still_masked() -> None:
    """TC-M-04: confidence='low' であってもマスクは実行されること。"""

    rules = load_masking_rules()
    text = "'email' => 'admin@example.com',\n"
    detections = detect_text("config/mail.php", text, rules)
    masked = mask_text(text, detections)

    assert "'email' => 'dummy@example.com'" in masked


def test_mask_email_skip_comment_line() -> None:
    """TC-M-05: コメント行のメールアドレスはマスク対象外であること。"""

    rules = load_masking_rules()
    text = "// contact: webmaster@myapp.jp\n'email' => 'admin@myapp.jp',\n"
    detections = detect_text("config/mail.php", text, rules)
    masked = mask_text(text, detections)

    assert "// contact: webmaster@myapp.jp" in masked
    assert "'email' => 'dummy@example.com'" in masked


def test_mask_email_smtp_username(php_smtp_email_fixture: str) -> None:
    """TC-M-06: username の値が dummy@example.com に置換されること。"""

    rules = load_masking_rules()
    detections = detect_text("config/mail.php", php_smtp_email_fixture, rules)
    masked = mask_text(php_smtp_email_fixture, detections)

    assert "'username' => 'dummy@example.com'" in masked
    assert "'password' => '********'" in masked


def test_mask_email_no_original_value_in_report() -> None:
    """TC-M-07: DetectionResult に original_value が露出しないこと（preview のみ）。"""

    rules = load_masking_rules()
    text = "'email' => 'admin@myapp.jp',\n'from_address' => 'noreply@myapp.jp',\n"
    detections = detect_text("config/mail.php", text, rules)
    masked = mask_text(text, detections)

    assert "admin@myapp.jp" not in masked
    assert "noreply@myapp.jp" not in masked

    for d in detections:
        assert "***" in d.original_value_preview
        assert d.original_value != d.original_value_preview
