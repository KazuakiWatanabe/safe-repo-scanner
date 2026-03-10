"""PHP 検出器のテスト。

概要:
    PHP 配列形式の基本キーと SMTP 配列の部分マスク挙動を検証する。
入出力:
    サンプル PHP テキストを検出器へ渡し、DetectionResult とマスク結果を確認する。
制約:
    生値をレポートへ出さず、置換値のみを期待する。
Note:
    Phase 1 の必須ケース 1 と 2 を担保する。
"""

from src.detectors import detect_text
from src.masker import mask_text
from src.utils import load_masking_rules


def test_detects_basic_php_credentials() -> None:
    """PHP の username / password を検出して置換できることを確認する。"""

    rules = load_masking_rules()
    text = "'username' => 'A',\n'password' => 'B',\n"

    detections = detect_text("config/database.php", text, rules)
    by_key = {detection.key_name: detection for detection in detections}

    assert by_key["username"].category == "credential_user"
    assert by_key["username"].replacement == "dummy_user"
    assert by_key["password"].category == "credential_password"
    assert by_key["password"].replacement == "********"
    assert mask_text(text, detections) == "'username' => 'dummy_user',\n'password' => '********',\n"


def test_masks_only_sensitive_php_smtp_fields() -> None:
    """SMTP 配列では host / username / password のみをマスクする。"""

    rules = load_masking_rules()
    text = (
        "'smtp' => [\n"
        "    'host' => 'AAA',\n"
        "    'port' => 587,\n"
        "    'username' => 'AAAAAAAAAAAAA',\n"
        "    'password' => 'AAAAA',\n"
        "    'timeout' => 300,\n"
        "    'starttls' => true,\n"
        "],\n"
    )

    detections = detect_text("config/mail.php", text, rules)
    detected_keys = [detection.key_name for detection in detections]

    assert detected_keys == ["host", "username", "password"]
    masked = mask_text(text, detections)
    assert "'host' => 'dummy-host'" in masked
    assert "'port' => 587" in masked
    assert "'username' => 'dummy_user'" in masked
    assert "'password' => '********'" in masked
    assert "'timeout' => 300" in masked
    assert "'starttls' => true" in masked


def test_does_not_detect_php_variable_reference_as_secret() -> None:
    """PHP の変数参照は生値ではないためマスク対象にしない。"""

    rules = load_masking_rules()
    text = "'vendor_token' => $vendors_token,\n"

    detections = detect_text("config/vendors.php", text, rules)

    assert detections == []
    assert mask_text(text, detections) == text


def test_does_not_detect_php_array_assignment_as_secret() -> None:
    """PHP の array 開始行は password を含んでもマスク対象にしない。"""

    rules = load_masking_rules()
    text = "\"omise_password\" => array(\n    'public_key' => 'pk_test_xxx',\n),\n"

    detections = detect_text("config/payment.php", text, rules)

    assert detections == []
    assert mask_text(text, detections) == text


def test_does_not_detect_php_password_help_text_as_secret() -> None:
    """password を含む説明文キーは機密値ではないためマスク対象にしない。"""

    rules = load_masking_rules()
    text = "'extract_password' => 'パスワードは半角英数字混在で8～20文字の範囲で入力してください。',\n"

    detections = detect_text("config/messages.php", text, rules)

    assert detections == []
    assert mask_text(text, detections) == text
