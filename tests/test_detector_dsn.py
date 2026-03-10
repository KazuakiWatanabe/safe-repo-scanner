"""DSN 検出器のテスト。

概要:
    PHP 内の DSN 文字列から部分検出し、壊さずに部分置換できることを検証する。
入出力:
    サンプル PHP テキストを検出器と masker へ渡す。
制約:
    charset など非マスク対象は保持する。
Note:
    Phase 1 の必須ケース 3 を担保する。
"""

from src.detectors import detect_text
from src.masker import mask_text
from src.utils import load_masking_rules


def test_masks_php_dsn_partially() -> None:
    """DSN 内の host と dbname だけを置換する。"""

    rules = load_masking_rules()
    text = "'dsn' => 'mysql:host=gmodl-sensya;dbname=sensya;charset=utf8',\n"

    detections = detect_text("config/database.php", text, rules)
    categories = [detection.category for detection in detections]
    replacements = [detection.replacement for detection in detections]
    masked = mask_text(text, detections)

    assert categories == ["connection_host", "db_name"]
    assert replacements == ["dummy-host", "dummy_db"]
    assert masked == "'dsn' => 'mysql:host=dummy-host;dbname=dummy_db;charset=utf8',\n"
