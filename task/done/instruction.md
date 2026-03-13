# safe-repo-scanner 実装指示

## 目的

レガシーPHPプロジェクトの仕様調査前に、リポジトリ内の機密情報を安全にマスキングするローカルツールを Python で実装する。

このツールは、`.env` だけでなく PHP / YAML / config 配下のベタ書き設定も対象にし、機密情報を検出・一覧化・ダミー値へ置換したうえで、**元ソースは変更せず、コピー先にマスク済みリポジトリを出力する**。  
背景として、設定ファイル単位の除外だけでは PHP や YAML に直接書かれた値を防ぎきれないため、**事前マスキング方式を採用する**。  
対象フレームワークとして FuelPHP / Laravel / CakePHP / Symfony を想定する。

---

## 前提要件

- ローカル実行ツールであること
- Python 3.11 以上
- Windows 11 を主対象にする
- UI を持つこと
- UI 上で対象リポジトリを選択できること
- UI 上で対象ファイル一覧を確認・選択できること
- 元リポジトリは変更しないこと
- 出力先にマスク済みコピーを生成すること

---

## 実装方式

- UI: Streamlit
- コアロジック: 純粋な Python モジュールに分離
- 設定ファイル: YAML
- 対象ファイル一覧、検出結果一覧、差分確認を UI に出す

---

## 必須機能

1. ローカルの Git リポジトリ一覧表示
2. 対象リポジトリの選択
3. 対象ファイル候補一覧の生成
4. 対象ファイルの ON/OFF 選択
5. 機密情報候補のスキャン
6. スキャン結果一覧表示
7. dry-run
8. マスク実行
9. マスク済みリポジトリの出力
10. JSON / CSV / Markdown のレポート出力

---

## 想定ディレクトリ構成

以下の構成で作成すること。

```text
safe-repo-scanner/
  README.md
  requirements.txt
  app.py
  masking_rules.yaml
  src/
    __init__.py
    models.py
    repo_finder.py
    target_file_selector.py
    scanner.py
    detectors.py
    dsn_parser.py
    masker.py
    reporter.py
    utils.py
  tests/
    test_detector_php.py
    test_detector_env.py
    test_detector_dsn.py
    test_masker.py
```

---

## 起動方法

```bash
# UI 起動
streamlit run app.py

# CLI
python -m src.scanner scan <repo_path>
python -m src.scanner report <repo_path> --format md
python -m src.scanner mask <repo_path> --output <masked_repo_path> --dry-run
python -m src.scanner mask <repo_path> --output <masked_repo_path> --apply
```

---

## 対象ファイルの選定ルール

### 優先的に対象とするファイル

- `.env`
- `.env.*`
- `config/**/*.php`
- `config/**/*.yaml`
- `config/**/*.yml`
- `config/**/*.json`
- `fuel/app/config/**/*.php`
- `fuel/app/config/production/**/*.php`
- `config/packages/**/*.yaml`
- `config/services.php`
- `config/database.php`
- `config/app.php`
- `config/app_local.php`

### 条件付きで対象とするファイル

`*.php` / `*.yaml` / `*.yml` / `*.ini` / `*.conf` / `*.json` / `*.xml` のうち、以下のいずれかを満たす場合のみ対象候補にする。

- `config` 配下
- ファイル名またはパスに `db`, `database`, `mail`, `smtp`, `service`, `auth`, `oauth`, `secret` を含む
- ファイル先頭を軽量走査して suspicious key を含む

### 除外

- `.git/`
- `vendor/`
- `node_modules/`
- `storage/logs/`
- `tmp/`
- `cache/`
- バイナリ / 画像 / zip / pdf

---

## 機密情報の検出対象

### キー系

| 分類 | キー名 |
|---|---|
| 接続先 | `host`, `hostname`, `server`, `DB_HOST` |
| 認証 | `username`, `user`, `login`, `account`, `password`, `pass`, `passwd`, `pwd`, `DB_PASSWORD` |
| API / secret | `api_key`, `secret`, `secret_key`, `access_token`, `refresh_token`, `client_secret`, `private_key`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| DSN / DB系 | `dsn`, `dbname`, `database` |

### 値パターン系

- IPv4 / IPv6
- FQDN 風ホスト名
- JWT
- AWS Access Key
- Stripe Secret
- Bearer Token
- PEM Private Key
- DSN 文字列

---

## DSN 対応

以下の形式を解析対象にする。

**PDO 形式**
```
mysql:host=gmodl-sensya;dbname=sensya;charset=utf8
pgsql:host=xxx;port=5432;dbname=yyy
```

**URL 形式**
```
mysql://user:pass@host:3306/dbname
smtp://user:pass@host:587
```

DSN 内の `host`, `user / username`, `password`, `dbname / database` を個別に置換すること。  
**DSN 全体を壊さず、一部だけ置換すること。**

---

## PHP / YAML / ENV の対応

以下のようなケースを拾えること。

**PHP 配列**
```php
'hostname' => 'gmodl-sensya',
'username' => 'A',
'password' => 'B',
```

**SMTP 設定**
```php
'smtp' => [
    'host' => 'AAA',
    'port' => 587,
    'username' => 'AAAAAAAAAAAAA',
    'password' => 'AAAAA',
    'timeout' => 300,
    'starttls' => true,
],
```

**.env**
```ini
DB_HOST=db.example.com
DB_PASSWORD=p@ssw0rd
AWS_SECRET_ACCESS_KEY=xxxxxxxx
```

**YAML**
```yaml
smtp:
  host: AAA
  username: BBB
  password: CCC
```

---

## マスク対象と置換値

| 分類 | 置換値 |
|---|---|
| `connection_host` | `dummy-host` |
| `credential_user` | `dummy_user` |
| `credential_password` | `********` |
| `db_name` | `dummy_db` |
| `api_key` | `dummy_key` |
| `token` | `dummy_token` |
| `secret` | `dummy_secret` |
| `ip_address` | `0.0.0.0` |
| `private_key` | `********` |

### マスク対象にすること

- `host`, `hostname`
- `username`, `user`
- `password`, `pass`
- SMTP 配列内の `host / username / password`
- DSN 内の `host / user / password / dbname`
- API key / token / secret 系
- クラウド認証情報

### マスク対象外にすること

- `port`
- `timeout`
- `starttls`
- `ssl`, `tls`
- `charset`
- `driver`

---

## 機能仕様

### 1. リポジトリ検索・選択画面

- UI 上部にテキスト入力欄を設け、検索ルートディレクトリを指定できること
- デフォルト値は `~/`（ホームディレクトリ）とする
- 指定ルート配下を再帰的に走査し、`.git` フォルダの有無で Git リポジトリと判定する
- 表示項目: `repository name` / `path` / `branch` / `last updated` / `selected`

### 2. 対象ファイル一覧画面

- スキャン対象ファイル候補を一覧表示する
- 表示項目: `selected` / `path` / `file_type` / `size` / `scan_reason` / `risk_level`
- 個別 ON/OFF を可能にする
- `high` risk のみ表示するフィルタを付ける

### 3. スキャン結果画面

- 機密候補を表形式で表示する
- 表示項目: `category` / `key_name` / `preview` / `file_path` / `line_no` / `rule_type` / `confidence` / `replacement` / `auto_maskable`

### 4. dry-run / 差分確認

- 変更前後の差分を確認できること
- apply 前に件数サマリーを出すこと

### 5. マスク実行

- 元リポジトリは変更しない
- `.git/` ディレクトリはコピー対象から除外すること（コミット履歴からの復元防止）
- 指定出力先にコピーしてから置換する
- レポートを保存する

---

## データモデル

```python
from dataclasses import dataclass
from typing import Literal, Optional

@dataclass
class RepoEntry:
    name: str
    path: str
    branch: str
    last_updated: str
    selected: bool = False

@dataclass
class TargetFileEntry:
    path: str
    file_type: str
    size: int
    scan_reason: str
    risk_level: Literal["high", "medium", "low"]
    selected: bool = True
    excluded_reason: Optional[str] = None

@dataclass
class DetectionResult:
    file_path: str
    line_no: int
    column_start: int
    column_end: int
    key_name: Optional[str]
    original_value: str
    original_value_preview: str   # 先頭3文字 + "***"（最大6文字）例: "p@s***"
    category: str
    rule_type: str
    confidence: Literal["high", "medium", "low"]
    severity: Literal["critical", "high", "medium", "low"]
    replacement: str
    auto_maskable: bool
    reason: str
```

---

## 設定ファイル（masking_rules.yaml）

`masking_rules.yaml` を作成し、以下の構造で外出しすること。

```yaml
include_extensions:
  - ".php"
  - ".env"
  - ".yaml"
  - ".yml"
  - ".json"
  - ".ini"
  - ".conf"
  - ".xml"

exclude_paths:
  - ".git/"
  - "vendor/"
  - "node_modules/"
  - "storage/logs/"
  - "tmp/"
  - "cache/"

suspicious_keys:
  - "password"
  - "passwd"
  - "secret"
  - "api_key"
  - "access_token"
  - "private_key"
  - "hostname"
  - "DB_PASSWORD"
  - "AWS_SECRET_ACCESS_KEY"

replacement_map:
  connection_host: "dummy-host"
  credential_user: "dummy_user"
  credential_password: "********"
  db_name: "dummy_db"
  api_key: "dummy_key"
  token: "dummy_token"
  secret: "dummy_secret"
  ip_address: "0.0.0.0"
  private_key: "********"

non_maskable_keys:
  - "port"
  - "timeout"
  - "starttls"
  - "ssl"
  - "tls"
  - "charset"
  - "driver"

allowlist: []
```

---

## 文字エンコーディング対応

日本語レガシーPHPプロジェクトでは Shift-JIS や EUC-JP のファイルが含まれる可能性がある。  
読み取り失敗によるスキャンのスキップを防ぐため、以下の方針で処理すること。

- `chardet` ライブラリを使用してエンコーディングを自動検出する
- 内部処理はすべて UTF-8 に正規化してから実施する
- エンコーディング検出に失敗した場合はそのファイルをスキップし、スキップログに記録する

---

## 実装方針

- 正規表現 + 行コンテキスト判定を基本にする
- AST 解析は初版では不要
- まずは高再現率を優先し、誤検知は一覧レビューで吸収する
- `scan`, `report`, `mask` を分ける
- `mask` は `dry-run` と `apply` を分ける

---

## テストケース

最低限、以下のケースをすべて通すこと。

### Case 1: PHP 基本キー値

**入力**
```php
'username' => 'A',
'password' => 'B',
```

**期待**
```php
'username' => 'dummy_user',
'password' => '********',
```

---

### Case 2: PHP SMTP 配列（部分マスク）

**入力**
```php
'smtp' => [
    'host' => 'AAA',
    'port' => 587,
    'username' => 'AAAAAAAAAAAAA',
    'password' => 'AAAAA',
    'timeout' => 300,
    'starttls' => true,
],
```

**期待**
```php
'smtp' => [
    'host' => 'dummy-host',
    'port' => 587,
    'username' => 'dummy_user',
    'password' => '********',
    'timeout' => 300,
    'starttls' => true,
],
```

---

### Case 3: PHP DSN 文字列（部分置換）

**入力**
```php
'dsn' => 'mysql:host=gmodl-sensya;dbname=sensya;charset=utf8',
```

**期待**
```php
'dsn' => 'mysql:host=dummy-host;dbname=dummy_db;charset=utf8',
```

---

### Case 4: .env ファイル

**入力**
```ini
DB_HOST=db.example.com
DB_PASSWORD=p@ssw0rd
AWS_SECRET_ACCESS_KEY=xxxxxxxx
```

**期待**
```ini
DB_HOST=dummy-host
DB_PASSWORD=********
AWS_SECRET_ACCESS_KEY=dummy_secret
```

検出レポートに以下が含まれること。
- `DB_HOST` → category: `connection_host`, severity: `high`
- `DB_PASSWORD` → category: `credential_password`, severity: `critical`
- `AWS_SECRET_ACCESS_KEY` → category: `secret`, severity: `critical`
- 各行の `preview` が `先頭3文字 + ***` 形式で出力されること

---

## 注意事項

- 生値をログに残さないこと
- レポートには `preview` のみ出すこと（`preview = 先頭3文字 + "***"`、最大6文字）
- `show raw` のような危険機能は初版では実装しないこと
- バックアップまたはコピー先作成なしで `apply` しないこと
- 失敗時も元リポジトリを壊さないこと
- `.git/` はコピー対象から除外し、コミット履歴からの復元を防ぐこと

---

## README に書くこと

- 目的
- 背景
- 対象ファイル
- マスク対象
- 使い方（UI / CLI 両方）
- UI のスクリーンショット想定
- 制約事項（元リポジトリを変更しないこと）
- 今後の拡張方針

---

## 完了条件

- `streamlit run app.py` で UI が起動する
- UI でリポジトリ検索ルートを指定し、リポジトリ選択ができる
- 対象ファイル一覧が表示できる
- スキャン結果一覧が表示できる
- dry-run ができる
- マスク済みコピーを出力できる（`.git/` は除外されること）
- Case 1〜4 のテストケースがすべて通る
- README で実行方法が分かる
