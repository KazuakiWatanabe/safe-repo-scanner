# safe-repo-scanner タスク定義 v1.2（全体仕様）

> **このファイルは参照用仕様書です。Codex または Claude code への作業指示は以下の順で渡してください。**
>
> ```
> フェーズ1: task-test-v1.2.md のみ渡す → pytest で RED を人間が目視確認
> フェーズ2: task-impl-v1.2.md を渡す  → pytest で GREEN を確認 → エビデンス保存
> ```

---

## バージョン情報

| 項目 | 内容 |
|---|---|
| バージョン | v1.2 |
| ベース | v1.1（task_v1_1.md 完了済み） |
| 対象ブランチ | `feature/P1-v1.2-email-masking` |

---

## 追加機能概要

| # | 機能名 | 概要 |
|---|---|---|
| F-03 | **Email Masking** | メールアドレスをマスキング対象に追加する |

---

## F-03: Email Masking 仕様

### 検出対象

#### キー系（キー名によるマッチ）

以下のキー名を持つ値がメールアドレス形式であれば検出対象とする。

| キー名 |
|---|
| `email` |
| `mail` |
| `from` |
| `from_address` |
| `to` |
| `to_address` |
| `reply_to` |
| `reply_to_address` |
| `sender` |
| `sender_address` |
| `MAIL_FROM_ADDRESS` |
| `MAIL_USERNAME` |

#### 値パターン系（キー名によらずパターンマッチ）

ファイル内の値部分がメールアドレスの形式（`RFC 5321` の簡易パターン）に合致する場合も検出対象とする。

```
正規表現例: [a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}
```

ただし、以下は除外する。

- `@example.com` / `@localhost` などのプレースホルダー的なドメイン（検出はするが `confidence: low` とする）
- PHP コメント行（`//`, `#`, `/* */`）に含まれるメールアドレス
- テンプレート文字列中のプレースホルダー（例: `{email}`, `{{ email }}`）

### 対応ファイル形式

v1.1 までの検出対象ファイル形式（`.php`, `.env`, `.yaml`, `.yml`, `.json`, `.ini`, `.conf`, `.xml`）をすべて引き継ぐ。追加はなし。

### 検出例

**PHP 配列**
```php
'email' => 'admin@example.com',
'from_address' => 'noreply@myapp.jp',
```

**SMTP 設定（PHP）**
```php
'smtp' => [
    'host'     => 'smtp.example.com',
    'username' => 'user@example.com',
    'password' => 'secret',
],
```
> `username` がメールアドレス形式の場合、`credential_user` ルールに加えて `email` ルールでも検出する。  
> カテゴリは `email` を優先する。

**.env**
```ini
MAIL_FROM_ADDRESS=hello@example.com
MAIL_USERNAME=apikey@sendgrid.example.com
```

**YAML**
```yaml
mailer:
  from: no-reply@myapp.jp
  reply_to: support@myapp.jp
```

### マスク対象と置換値

`masking_rules.yaml` の `replacement_map` に以下を追加する。

| 分類 | 置換値 |
|---|---|
| `email` | `dummy@example.com` |

### DetectionResult のフィールド値

| フィールド | 値 |
|---|---|
| `category` | `email` |
| `rule_type` | `key_match` または `pattern_match` |
| `confidence` | `high`（キー名一致 または 値パターン一致＋信頼性高） / `low`（プレースホルダードメイン） |
| `severity` | `high` |
| `replacement` | `dummy@example.com` |
| `auto_maskable` | `True` |

### preview 形式

既存ルールと同様に `先頭3文字 + "***"` とする。  
例: `adm***`（`admin@example.com` の場合）

---

## masking_rules.yaml への追記

```yaml
suspicious_keys:
  # ... 既存エントリ ...
  - "email"
  - "mail"
  - "from_address"
  - "reply_to"
  - "MAIL_FROM_ADDRESS"
  - "MAIL_USERNAME"

replacement_map:
  # ... 既存エントリ ...
  email: "dummy@example.com"

email_placeholder_domains:
  - "example.com"
  - "example.jp"
  - "example.org"
  - "localhost"
  - "test.com"
```

> `email_placeholder_domains` に含まれるドメインはプレースホルダーとみなし `confidence: low` とする。  
> マスクは行うが、スキャン結果一覧では低信頼度として区別表示する。

---

## 変更対象ファイル

| ファイル | 変更種別 |
|---|---|
| `src/detectors.py` | メールアドレス検出ロジックを追加 |
| `src/masker.py` | `email` カテゴリの置換処理を追加 |
| `masking_rules.yaml` | `suspicious_keys` / `replacement_map` / `email_placeholder_domains` を追加 |
| `tests/test_detector_email.py` | 新規作成（フェーズ1） |
| `tests/test_masker_email.py` | 新規作成（フェーズ1） |
| `tests/conftest.py` | メール関連 fixture を追加（フェーズ1） |

> `src/reporter.py` / `src/scanner.py` / `src/models.py` など他のモジュールは変更しないこと。  
> `DetectionResult` の `category` フィールドは既存の `Literal` 型に `"email"` を追加するのみとする。

---

## 受け入れ条件（AC）

| ID | 条件 |
|---|---|
| AC-01 | PHP / .env / YAML のメールアドレスが検出され、`dummy@example.com` に置換される |
| AC-02 | キー名一致・値パターン一致の両方で検出できる |
| AC-03 | プレースホルダードメイン（`example.com` 等）は検出されるが `confidence: low` となる |
| AC-04 | PHP コメント行のメールアドレスは検出されない |
| AC-05 | `username` がメールアドレス形式の場合、カテゴリは `email` になる |
| AC-06 | `preview` が `先頭3文字 + "***"` 形式で出力される |
| AC-07 | `original_value` が出力ファイルに含まれない |
| AC-08 | `masking_rules.yaml` の `email_placeholder_domains` によって `confidence` が制御される |

---

## テストケース

### Case 5: PHP メールアドレス（キー名一致）

**入力**
```php
'email' => 'admin@myapp.jp',
'from_address' => 'noreply@myapp.jp',
```

**期待**
```php
'email' => 'dummy@example.com',
'from_address' => 'dummy@example.com',
```

---

### Case 6: .env メールアドレス

**入力**
```ini
MAIL_FROM_ADDRESS=hello@myapp.jp
MAIL_USERNAME=apikey@sendgrid.net
```

**期待**
```ini
MAIL_FROM_ADDRESS=dummy@example.com
MAIL_USERNAME=dummy@example.com
```

検出レポートに以下が含まれること。
- `MAIL_FROM_ADDRESS` → category: `email`, severity: `high`, confidence: `high`
- `MAIL_USERNAME` → category: `email`, severity: `high`, confidence: `high`

---

### Case 7: YAML メールアドレス

**入力**
```yaml
mailer:
  from: no-reply@myapp.jp
  reply_to: support@myapp.jp
```

**期待**
```yaml
mailer:
  from: dummy@example.com
  reply_to: dummy@example.com
```

---

### Case 8: プレースホルダードメイン（confidence: low）

**入力**
```php
'email' => 'admin@example.com',
```

**期待**
- 置換結果: `'email' => 'dummy@example.com'`
- 検出レポート: `confidence: low`

---

### Case 9: PHP コメント行（検出しない）

**入力**
```php
// contact: webmaster@myapp.jp
'email' => 'admin@myapp.jp',
```

**期待**
- コメント行のメールアドレスは検出しない
- `'email'` 行のみ置換される

---

### Case 10: SMTP username がメールアドレス形式

**入力**
```php
'smtp' => [
    'username' => 'user@sendgrid.net',
    'password' => 'secret',
],
```

**期待**
```php
'smtp' => [
    'username' => 'dummy@example.com',
    'password' => '********',
],
```

- `username` の検出結果: `category: email`（`credential_user` より優先）
