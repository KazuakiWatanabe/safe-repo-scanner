# フェーズ2: 実装指示 — v1.2 Email Masking

---

## ⚠️ 作業開始前に必ず読むこと

```
AGENTS.md CLAUDE.md を必ず参照し、コーディング規約・ブランチ運用・
コミットメッセージ規則・禁止事項を確認してから作業を開始すること。
AGENTS.md の内容はこのタスクの全指示より優先される。
```

---

## ⚠️ このファイルを渡す前に確認すること

```bash
pytest tests/test_detector_email.py tests/test_masker_email.py -v
```

> **全テストが RED（FAIL / ERROR）になっていることを確認してからこのファイルを渡すこと。**  
> RED を確認していない場合はフェーズ1（`task_test_v1.2.md`）に戻ること。

---

## 0. タスク固有設定

```yaml
target_branch: "feature/P1-v1.2-email-masking"

target_files:
  - "src/detectors.py"
  - "src/masker.py"
  - "masking_rules.yaml"

target_functions:
  - "detectors.EmailDetector.detect(line, line_no, file_path, rules)"
  - "masker.Masker.mask_email(line, result)"

test_scope:
  include: "フェーズ1で作成済みのテストをすべて GREEN にすること"
  exclude: "新しいテストの追加・既存テストの変更"

source_spec: "task_v1_2.md"

task_constraints:
  refactor_policy: >
    src/detectors.py / src/masker.py / masking_rules.yaml のみ変更可。
    tests/ は変更禁止。src/models.py の変更は category Literal への
    'email' 追加のみ許可。
```

---

## 1. このフェーズでやること・やらないこと

| やること | やらないこと |
|---|---|
| `src/detectors.py` にメールアドレス検出ロジックを追加する | テストコードを変更する |
| `src/masker.py` に `email` カテゴリの置換処理を追加する | テストを削除・スキップして PASS させる |
| `masking_rules.yaml` に必要なキーを追加する | `src/reporter.py` / `src/scanner.py` 等を変更する |
| `src/models.py` の `category` Literal に `"email"` を追加する | `models.py` の他フィールドを変更する |
| pytest を実行して **GREEN（PASS）を確認する** | — |
| エビデンスを `test/evidence/` に保存する | — |

---

## 2. 実装仕様

### 2-1. `masking_rules.yaml` への追記

```yaml
suspicious_keys:
  # --- 追加分 ---
  - "email"
  - "mail"
  - "from_address"
  - "reply_to"
  - "reply_to_address"
  - "sender"
  - "sender_address"
  - "MAIL_FROM_ADDRESS"
  - "MAIL_USERNAME"

replacement_map:
  # --- 追加分 ---
  email: "dummy@example.com"

# --- 新規セクション ---
email_placeholder_domains:
  - "example.com"
  - "example.jp"
  - "example.org"
  - "localhost"
  - "test.com"
```

---

### 2-2. `src/detectors.py` — EmailDetector の追加

```python
EMAIL_PATTERN = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
)

EMAIL_KEY_NAMES = {
    "email", "mail", "from", "from_address",
    "to", "to_address", "reply_to", "reply_to_address",
    "sender", "sender_address",
    "MAIL_FROM_ADDRESS", "MAIL_USERNAME",
}
```

#### 検出ロジックの要件

1. **コメント行の除外**  
   行を正規化した先頭が `//`, `#`, `*` で始まる場合は検出しない。  
   `/* ... */` ブロックコメントも除外する。

2. **キー名一致（`rule_type: "key_match"`）**  
   `EMAIL_KEY_NAMES` に含まれるキー名を持つ値がメールアドレス形式であれば検出する。

3. **値パターン一致（`rule_type: "pattern_match"`）**  
   キー名に関わらず値部分が `EMAIL_PATTERN` に一致すれば検出する。  
   ただし `rule_type: "key_match"` と重複する行は `key_match` を優先し、`pattern_match` の結果は除外する。

4. **カテゴリ優先ルール**  
   `username` など他のキー名ルールと競合する場合、値がメールアドレス形式であれば `category: "email"` を優先する。

5. **confidence の決定**
   - キー名一致 かつ プレースホルダードメイン以外 → `"high"`
   - 値パターン一致のみ かつ プレースホルダードメイン以外 → `"high"`
   - プレースホルダードメイン（`email_placeholder_domains` に含まれる）→ `"low"`

6. **preview の生成**  
   `先頭3文字 + "***"`（既存ルールと統一）  
   例: `admin@myapp.jp` → `"adm***"`

7. **severity**  
   常に `"high"` とする。

---

### 2-3. `src/masker.py` — email カテゴリの置換処理

```python
def mask_email(self, line: str, result: DetectionResult) -> str:
    """
    DetectionResult.category == 'email' の行を置換する。
    original_value の位置（column_start, column_end）を使って
    値部分のみを replacement で置き換える。
    行全体を壊さないこと。
    """
```

#### 置換の要件

- `result.replacement`（= `"dummy@example.com"`）で元のメールアドレス部分のみを置換する
- 行の引用符スタイル（シングル / ダブル）を維持する
- PHP / .env / YAML のいずれの書式でも正しく動作すること
- `confidence: "low"` であっても置換は実行すること

---

### 2-4. `src/models.py` — category Literal への追加

```python
# 変更前
category: str

# 変更後（Literal を使用している場合のみ）
category: Literal[
    "connection_host", "credential_user", "credential_password",
    "db_name", "api_key", "token", "secret",
    "ip_address", "private_key",
    "email",   # ← 追加
]
```

> `category` が単純な `str` 型の場合は変更不要。

---

## 3. 実装後の自己検証ステップ

```bash
# Step 1: テストが GREEN になることを確認
pytest tests/test_detector_email.py tests/test_masker_email.py -v

# Step 2: 核となるロジックを意図的に壊して RED になることを確認
# 例: EmailDetector でコメント行の除外を削除し
#     test_detect_email_skip_comment_line が FAIL することを確認する

# Step 3: 壊した実装を元に戻して GREEN に戻ることを確認
pytest tests/test_detector_email.py tests/test_masker_email.py -v

# Step 4: 既存テストがすべて通ることを確認（リグレッションなし）
pytest tests/ -v

# Step 5: カバレッジ確認
pytest tests/test_detector_email.py tests/test_masker_email.py \
  --cov=src/detectors --cov=src/masker --cov-report=term-missing

# Step 6: エビデンス保存
pytest tests/test_detector_email.py tests/test_masker_email.py -v \
  > test/evidence/test_email_masking_v1.2.txt
```

---

## 4. フェーズ2 終了条件

- [ ] `pytest tests/test_detector_email.py tests/test_masker_email.py -v` が全 GREEN である
- [ ] `pytest tests/ -v` で既存テストがすべて通る（リグレッションなし）
- [ ] `src/detectors.py` と `src/masker.py` のカバレッジが 85% 以上である
- [ ] 自己検証ステップ（Step 2）で RED になることを確認済みである
- [ ] テストコードを一切変更していない
- [ ] `src/reporter.py` / `src/scanner.py` / `src/repo_finder.py` 等を変更していない
- [ ] `test/evidence/test_email_masking_v1.2.txt` が保存されている

---

## 5. 禁止事項

| 禁止パターン | 理由 |
|---|---|
| テストを削除・スキップして PASS させる | 仕様を証明していない |
| テストコードの期待値を実装に合わせて書き換える | テストが仕様でなく実装を追いかける状態になる |
| `original_value` を出力ファイルに含める | AC-07 違反・機密漏洩リスク |
| `src/detectors.py` / `src/masker.py` 以外の `src/` を変更する（`models.py` の Literal 追加を除く） | フェーズ2のスコープ外 |
| コメント行のメールアドレスをマスクする | AC 違反・誤検知 |
