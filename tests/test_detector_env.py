"""ENV 検出器のテスト。

概要:
    `.env` 形式のキー検出、preview、レポート安全性を検証する。
入出力:
    サンプル ENV テキストを検出器とレポータへ渡す。
制約:
    original_value をレポートへ含めない。
Note:
    Phase 1 の必須ケース 4 を担保する。
"""

from src.detectors import detect_text
from src.reporter import render_report
from src.utils import load_masking_rules


def test_detects_env_and_outputs_preview_only() -> None:
    """`.env` の機密キーが期待カテゴリと preview で出力される。"""

    rules = load_masking_rules()
    text = "DB_HOST=db.example.com\nDB_PASSWORD=p@ssw0rd\nAWS_SECRET_ACCESS_KEY=xxxxxxxx\n"

    detections = detect_text(".env", text, rules)
    by_key = {detection.key_name: detection for detection in detections}
    report = render_report(detections, "json")

    assert by_key["DB_HOST"].category == "connection_host"
    assert by_key["DB_HOST"].severity == "high"
    assert by_key["DB_PASSWORD"].category == "credential_password"
    assert by_key["DB_PASSWORD"].severity == "critical"
    assert by_key["AWS_SECRET_ACCESS_KEY"].category == "secret"
    assert by_key["AWS_SECRET_ACCESS_KEY"].severity == "critical"
    assert by_key["DB_PASSWORD"].original_value_preview == "p@s***"
    assert by_key["AWS_SECRET_ACCESS_KEY"].original_value_preview == "xxx***"
    assert "p@ssw0rd" not in report
    assert "xxxxxxxx" not in report
    assert '"プレビュー": "p@s***"' in report
    assert '"preview"' not in report


def test_render_report_uses_japanese_field_labels_for_csv_and_markdown() -> None:
    """mask_report 用の CSV / Markdown ヘッダーが日本語で出力されることを確認する。"""

    rules = load_masking_rules()
    text = "DB_HOST=db.example.com\nDB_PASSWORD=p@ssw0rd\nAWS_SECRET_ACCESS_KEY=xxxxxxxx\n"

    detections = detect_text(".env", text, rules)
    csv_report = render_report(detections, "csv")
    markdown_report = render_report(detections, "md")

    assert csv_report.splitlines()[0] == (
        "カテゴリ,キー名,プレビュー,ファイルパス,行番号,開始列,終了列,ルール種別,信頼度,重要度,置換値,自動マスク可否,検出理由"
    )
    assert "| カテゴリ | キー名 | プレビュー | ファイルパス | 行番号 | ルール種別 | 信頼度 | 置換値 | 自動マスク可否 |" in markdown_report
