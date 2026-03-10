# safe-repo-scanner

レガシー PHP リポジトリの仕様調査前に、機密情報を安全にマスキングしたコピーを作るローカル専用ツールです。`.env` だけでなく PHP / YAML / config 配下のベタ書き設定も対象にし、元リポジトリは変更しません。

## 目的

- 仕様調査前に機密情報を検出する
- preview ベースで一覧レビューする
- ダミー値へ置換したコピーを出力する
- JSON / CSV / Markdown のレポートを残す

## 背景

設定ファイル単位の除外だけでは、PHP 配列や YAML に直書きされた接続情報・認証情報を防ぎ切れません。そのため、本ツールは事前マスキング方式を採用し、調査用コピーを安全に作成します。

## 対象ファイル

- `.env`
- `.env.*`
- `config/**/*.php`
- `config/**/*.yaml`
- `config/**/*.yml`
- `config/**/*.json`
- `fuel/app/config/**/*.php`
- `config/packages/**/*.yaml`
- `config/services.php`
- `config/database.php`
- `config/app.php`
- `config/app_local.php`

条件付きで `*.php` / `*.yaml` / `*.yml` / `*.ini` / `*.conf` / `*.json` / `*.xml` も対象候補にします。

## マスク対象

- `host`, `hostname`, `DB_HOST`
- `username`, `user`
- `password`, `pass`, `DB_PASSWORD`
- SMTP 設定内の `host`, `username`, `password`
- DSN 内の `host`, `user`, `password`, `dbname`
- API key / token / secret / private key

`port`, `timeout`, `starttls`, `charset`, `driver` はマスク対象外です。

## ローカル実行方法

### 前提条件

- Python 3.11 以上
- Windows 11 を主対象OSとして想定
- 外部通信なしでローカル実行すること

### セットアップ

PowerShell 例:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### UI 起動

```bash
streamlit run app.py
```

起動後はブラウザで以下の流れで操作します。

- 一覧から選択する場合は、検索ルートを指定して Git リポジトリを探索
- 対象リポジトリを選択
  一覧から選ぶか、`フォルダダイアログで選択` から Git リポジトリのフォルダを直接選択できます
- 証跡出力先は `出力先選択` ボタンからフォルダダイアログでも指定できます
- 対象ファイル候補を生成
- スキャン結果を確認
- `dry-run` または `apply` を実行

### CLI 実行

```bash
python -m src.scanner scan <repo_path>
python -m src.scanner report <repo_path> --format md
python -m src.scanner mask <repo_path> --output <masked_repo_path> --dry-run
python -m src.scanner mask <repo_path> --output <masked_repo_path> --apply
```

例:

```bash
python -m src.scanner scan C:\work\legacy-repo
python -m src.scanner mask C:\work\legacy-repo --output C:\work\legacy-repo-masked --dry-run
```

### テスト実行

```bash
pytest
```

個別実行例:

```bash
pytest tests/test_reporter_export.py tests/test_reporter_tree.py -v
```

## 使い方

### UI

```bash
streamlit run app.py
```

UI では以下を行えます。

- 検索ルートからローカル Git リポジトリを探索
- 対象リポジトリの選択
  一覧選択とフォルダ選択ダイアログの両方に対応
- 証跡出力先の選択
  テキスト入力とフォルダ選択ダイアログの両方に対応
- スキャン対象ファイル候補の確認と ON/OFF 選択
- スキャン結果一覧表示
- dry-run と apply 実行

### CLI

```bash
python -m src.scanner scan <repo_path>
python -m src.scanner report <repo_path> --format md
python -m src.scanner mask <repo_path> --output <masked_repo_path> --dry-run
python -m src.scanner mask <repo_path> --output <masked_repo_path> --apply
```

## UI のスクリーンショット想定

- Repository Search: 検索ルート入力、Git リポジトリ一覧、選択 UI
- Target Files: スキャン候補一覧、high risk フィルタ、ON/OFF 選択
- Scan Result: preview 付き検出結果一覧
- Dry-run / Apply: preview ベース差分、件数サマリー、出力先表示

## 制約事項

- 元リポジトリは変更しません
- `.git/` はコピーしません
- レポートと UI は preview のみ表示します
- 外部通信は行いません
- Phase 1 では show raw を実装しません

## 今後の拡張方針

- 検出精度の改善
- Shift-JIS / EUC-JP 対応強化
- allowlist / 除外ルール編集 UI
- 差分ビューア強化
