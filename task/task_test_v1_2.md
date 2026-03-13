# フェーズ1: テスト作成タスク — v1.2 Email Masking

---

## ⚠️ 作業開始前に必ず読むこと

```
AGENTS.md CLAUDE.md を必ず参照し、コーディング規約・ブランチ運用・
コミットメッセージ規則・禁止事項を確認してから作業を開始すること。
AGENTS.md の内容はこのタスクの全指示より優先される。
```

---

## 0. タスク固有設定

```yaml
target_branch: "feature/P1-v1.2-email-masking"
base_branch: "main"

target_files:
  - "tests/test_detector_email.py"   # 新規作成
  - "tests/test_masker_email.py"     # 新規作成
  - "tests/conftest.py"              # fixture 追加

source_spec: "task_v1_2.md"

task_constraints:
  refactor_policy: "tests/ 配下のみ変更可。src/ は変更禁止"
  test_result: "このフェーズ完了時点で全テストが RED（FAIL/ERROR）であること"
```

---

## 1. このフェーズでやること・やらないこと

| やること | やらないこと |
|---|---|
| `tests/test_detector_email.py` を新規作成する | `src/` 配下の実装を変更する |
| `tests/test_masker_email.py` を新規作成する | テストを GREEN にするための実装を書く |
| `tests/conftest.py` にメール関連 fixture を追加する | 既存テストを変更・削除する |
| pytest を実行して **RED（FAIL/ERROR）を確認する** | スキップ（`@pytest.mark.skip`）で RED を回避する |

---

## 2. 作成するテストファイル

### 2-1. `tests/test_detector_email.py`

以下のテストケースをすべて実装すること。

#### TC-D-01: PHP キー名一致でメールアドレスを検出する

```python
def test_detect_email_php_key_match(php_email_fixture):
    """'email' キーのメールアドレスが category='email' で検出されること"""
```

- 入力: `"'email' => 'admin@myapp.jp',"`
- 期待: `DetectionResult.category == "email"`
- 期待: `DetectionResult.confidence == "high"`
- 期待: `DetectionResult.replacement == "dummy@example.com"`

---

#### TC-D-02: .env キー名一致でメールアドレスを検出する

```python
def test_detect_email_env_key_match(env_email_fixture):
    """MAIL_FROM_ADDRESS がメールアドレスとして検出されること"""
```

- 入力: `"MAIL_FROM_ADDRESS=hello@myapp.jp"`
- 期待: `category == "email"`, `severity == "high"`, `confidence == "high"`

---

#### TC-D-03: YAML キー名一致でメールアドレスを検出する

```python
def test_detect_email_yaml_key_match(yaml_email_fixture):
    """from / reply_to キーのメールアドレスが検出されること"""
```

- 入力:
  ```yaml
  from: no-reply@myapp.jp
  reply_to: support@myapp.jp
  ```
- 期待: 2件の `DetectionResult`、いずれも `category == "email"`

---

#### TC-D-04: 値パターンマッチでメールアドレスを検出する

```python
def test_detect_email_pattern_match(php_email_pattern_fixture):
    """キー名によらず、値がメールアドレス形式であれば検出されること"""
```

- 入力: `"'contact' => 'info@myapp.jp',"`（`contact` はキー名リストに含まれない）
- 期待: `category == "email"`, `rule_type == "pattern_match"`

---

#### TC-D-05: プレースホルダードメインは confidence: low になる

```python
def test_detect_email_placeholder_domain_low_confidence():
    """example.com ドメインは confidence='low' で検出されること"""
```

- 入力: `"'email' => 'admin@example.com',"`
- 期待: `confidence == "low"`（検出はされる、マスクもされる）

---

#### TC-D-06: PHP コメント行のメールアドレスは検出しない

```python
def test_detect_email_skip_comment_line():
    """PHP コメント行のメールアドレスは検出対象外であること"""
```

- 入力:
  ```php
  // contact: webmaster@myapp.jp
  'email' => 'admin@myapp.jp',
  ```
- 期待: 検出件数 == 1（コメント行は含まれない）

---

#### TC-D-07: SMTP username がメールアドレスの場合 category は email になる

```python
def test_detect_email_smtp_username_category():
    """username の値がメールアドレス形式のとき category='email' が優先されること"""
```

- 入力:
  ```php
  'username' => 'user@sendgrid.net',
  ```
- 期待: `category == "email"`（`credential_user` ではない）

---

#### TC-D-08: preview が正しい形式で出力される

```python
def test_detect_email_preview_format():
    """preview が '先頭3文字 + ***' 形式であること"""
```

- 入力値: `admin@myapp.jp`
- 期待: `preview == "adm***"`

---

### 2-2. `tests/test_masker_email.py`

#### TC-M-01: PHP メールアドレスのマスク（Case 5）

```python
def test_mask_email_php(php_email_fixture):
    """PHP の email / from_address キーが dummy@example.com に置換されること"""
```

---

#### TC-M-02: .env メールアドレスのマスク（Case 6）

```python
def test_mask_email_env(env_email_fixture):
    """MAIL_FROM_ADDRESS / MAIL_USERNAME が dummy@example.com に置換されること"""
```

---

#### TC-M-03: YAML メールアドレスのマスク（Case 7）

```python
def test_mask_email_yaml(yaml_email_fixture):
    """from / reply_to が dummy@example.com に置換されること"""
```

---

#### TC-M-04: プレースホルダードメインもマスクされる

```python
def test_mask_email_placeholder_domain_still_masked():
    """confidence='low' であってもマスクは実行されること"""
```

---

#### TC-M-05: PHP コメント行はマスクされない

```python
def test_mask_email_skip_comment_line():
    """コメント行のメールアドレスはマスク対象外であること"""
```

---

#### TC-M-06: SMTP username がメールアドレスの場合のマスク（Case 10）

```python
def test_mask_email_smtp_username(php_smtp_email_fixture):
    """username の値が dummy@example.com に置換されること"""
```

---

#### TC-M-07: original_value が出力に含まれないこと

```python
def test_mask_email_no_original_value_in_report():
    """DetectionResult に original_value が露出しないこと（preview のみ）"""
```

---

### 2-3. `tests/conftest.py` への fixture 追加

```python
@pytest.fixture
def php_email_fixture():
    return textwrap.dedent("""\
        'email' => 'admin@myapp.jp',
        'from_address' => 'noreply@myapp.jp',
    """)

@pytest.fixture
def env_email_fixture():
    return textwrap.dedent("""\
        MAIL_FROM_ADDRESS=hello@myapp.jp
        MAIL_USERNAME=apikey@sendgrid.net
    """)

@pytest.fixture
def yaml_email_fixture():
    return textwrap.dedent("""\
        mailer:
          from: no-reply@myapp.jp
          reply_to: support@myapp.jp
    """)

@pytest.fixture
def php_email_pattern_fixture():
    return "'contact' => 'info@myapp.jp',"

@pytest.fixture
def php_smtp_email_fixture():
    return textwrap.dedent("""\
        'smtp' => [
            'username' => 'user@sendgrid.net',
            'password' => 'secret',
        ],
    """)
```

---

## 3. フェーズ1 終了条件

- [ ] `tests/test_detector_email.py` が作成されている
- [ ] `tests/test_masker_email.py` が作成されている
- [ ] `tests/conftest.py` にメール関連 fixture が追加されている
- [ ] 以下のコマンドで全テストが **RED（FAIL/ERROR）** になることを人間が目視確認している
  ```bash
  pytest tests/test_detector_email.py tests/test_masker_email.py -v
  ```
- [ ] 既存のテスト（`test_detector_php.py` 等）が引き続き通ること（既存テストを壊さない）
  ```bash
  pytest tests/ -v
  ```
- [ ] `src/` 配下を一切変更していない

---

## 4. 禁止事項

| 禁止パターン | 理由 |
|---|---|
| `src/` 配下の実装を変更する | フェーズ1のスコープ外 |
| `@pytest.mark.skip` でテストをスキップする | RED を確認できない |
| テストの期待値を曖昧にして GREEN にしやすくする | 仕様を証明していない |
| 既存テストを変更・削除する | 既存仕様の保護 |
