"""メールアドレス検出器のテスト。

概要:
    PHP / .env / YAML のメールアドレス検出、値パターンマッチ、
    プレースホルダードメインの confidence 判定、コメント行除外を検証する。
入出力:
    fixture 経由のサンプルテキストを検出器へ渡し、DetectionResult を確認する。
制約:
    生値をレポートへ出さず、preview のみを期待する。
Note:
    v1.2 の TC-D-01〜TC-D-08 を担保する。
"""

from src.detectors import detect_text
from src.utils import load_masking_rules


def test_detect_email_php_key_match(php_email_fixture: str) -> None:
    """TC-D-01: 'email' キーのメールアドレスが category='email' で検出されること。"""

    rules = load_masking_rules()
    detections = detect_text("config/mail.php", php_email_fixture, rules)
    by_key = {d.key_name: d for d in detections}

    assert "email" in by_key
    assert "from_address" in by_key
    assert by_key["email"].category == "email"
    assert by_key["email"].confidence == "high"
    assert by_key["email"].replacement == "dummy@example.com"
    assert by_key["from_address"].category == "email"
    assert by_key["from_address"].confidence == "high"
    assert by_key["from_address"].replacement == "dummy@example.com"


def test_detect_email_env_key_match(env_email_fixture: str) -> None:
    """TC-D-02: MAIL_FROM_ADDRESS がメールアドレスとして検出されること。"""

    rules = load_masking_rules()
    detections = detect_text(".env", env_email_fixture, rules)
    by_key = {d.key_name: d for d in detections}

    assert "MAIL_FROM_ADDRESS" in by_key
    assert "MAIL_USERNAME" in by_key
    assert by_key["MAIL_FROM_ADDRESS"].category == "email"
    assert by_key["MAIL_FROM_ADDRESS"].severity == "high"
    assert by_key["MAIL_FROM_ADDRESS"].confidence == "high"
    assert by_key["MAIL_USERNAME"].category == "email"
    assert by_key["MAIL_USERNAME"].severity == "high"
    assert by_key["MAIL_USERNAME"].confidence == "high"


def test_detect_email_yaml_key_match(yaml_email_fixture: str) -> None:
    """TC-D-03: from / reply_to キーのメールアドレスが検出されること。"""

    rules = load_masking_rules()
    detections = detect_text("config/mailer.yaml", yaml_email_fixture, rules)
    by_key = {d.key_name: d for d in detections}

    assert "from" in by_key
    assert "reply_to" in by_key
    assert by_key["from"].category == "email"
    assert by_key["reply_to"].category == "email"
    assert len([d for d in detections if d.category == "email"]) == 2


def test_detect_email_pattern_match(php_email_pattern_fixture: str) -> None:
    """TC-D-04: キー名によらず、値がメールアドレス形式であれば検出されること。"""

    rules = load_masking_rules()
    detections = detect_text("config/contact.php", php_email_pattern_fixture, rules)

    assert len(detections) >= 1
    d = detections[0]
    assert d.category == "email"
    assert d.rule_type == "pattern_match"


def test_detect_email_placeholder_domain_low_confidence() -> None:
    """TC-D-05: example.com ドメインは confidence='low' で検出されること。"""

    rules = load_masking_rules()
    text = "'email' => 'admin@example.com',\n"
    detections = detect_text("config/mail.php", text, rules)

    assert len(detections) >= 1
    email_det = [d for d in detections if d.key_name == "email"][0]
    assert email_det.confidence == "low"
    assert email_det.category == "email"


def test_detect_email_skip_comment_line() -> None:
    """TC-D-06: PHP コメント行のメールアドレスは検出対象外であること。"""

    rules = load_masking_rules()
    text = "// contact: webmaster@myapp.jp\n'email' => 'admin@myapp.jp',\n"
    detections = detect_text("config/mail.php", text, rules)

    assert len(detections) == 1
    assert detections[0].key_name == "email"


def test_detect_email_smtp_username_category() -> None:
    """TC-D-07: username の値がメールアドレス形式のとき category='email' が優先されること。"""

    rules = load_masking_rules()
    text = "    'username' => 'user@sendgrid.net',\n"
    detections = detect_text("config/mail.php", text, rules)

    assert len(detections) == 1
    assert detections[0].category == "email"


def test_detect_email_preview_format() -> None:
    """TC-D-08: preview が '先頭3文字 + ***' 形式であること。"""

    rules = load_masking_rules()
    text = "'email' => 'admin@myapp.jp',\n"
    detections = detect_text("config/mail.php", text, rules)

    assert len(detections) >= 1
    d = [det for det in detections if det.key_name == "email"][0]
    assert d.original_value_preview == "adm***"
