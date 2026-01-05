# 認証トークン再生成ガイド

GitHub Actions で `invalid_grant: Token has been expired or revoked` エラーが発生した場合、このガイドに従ってトークンを再生成してください。

## 問題の症状

GitHub Actions のワークフローが以下のエラーで失敗します：

```
google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {...})
```

これは、Google の認証トークンが期限切れになっているためです。

## 解決手順

### 前提条件

- `client_secrets.json` がプロジェクトルートに配置されていること
- Google Cloud Console で YouTube Data API、Google Sheets API が有効になっていること
- ローカル環境に Python 3.10+ がインストールされていること

詳細は [docs/integration-setup.md](docs/integration-setup.md) を参照してください。

---

## ステップ1: リポジトリをクローン（初回のみ）

```bash
git clone https://github.com/YOUR_USERNAME/Greatma_Words.git
cd Greatma_Words
```

## ステップ2: 環境をセットアップ（初回のみ）

```bash
# 仮想環境を作成
python -m venv .venv

# 仮想環境を有効化
# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate

# 依存関係をインストール
pip install -r requirements.txt
```

## ステップ3: client_secrets.json を配置（初回のみ）

Google Cloud Console から OAuth 2.0 クライアントの認証情報をダウンロードし、`client_secrets.json` として配置してください。

```
Greatma_Words/
├── client_secrets.json  ← ここに配置
├── .env
├── app/
└── ...
```

詳細は [docs/integration-setup.md](docs/integration-setup.md#15-oauth-20-クライアント作成) を参照。

---

## ステップ4: トークンを再生成

### YouTube トークンの再生成

```bash
python generate_youtube_token.py
```

1. ブラウザが自動で開きます
2. Google アカウントでログインします
3. YouTube へのアクセス権限を許可します
4. 「認証成功」と表示されたらブラウザを閉じます
5. ターミナルに表示される **Base64エンコード値をコピー** します

```
===============================================================
COPY THIS VALUE:
===============================================================
eyJ0eXAiOiJKV1QiLC...（長い文字列）
===============================================================
```

または、`youtube_token_b64.txt` からコピーできます。

### Google Sheets トークンの再生成

```bash
python generate_sheets_token.py
```

同様の手順で、**Base64エンコード値をコピー** します。

---

## ステップ5: GitHub Secrets を更新

### YouTube トークンを更新

1. リポジトリの Settings → Secrets and variables → Actions にアクセス:
   ```
   https://github.com/YOUR_USERNAME/YOUR_REPO/settings/secrets/actions
   ```

2. `YOUTUBE_TOKEN_JSON_B64` を選択（なければ「New repository secret」をクリック）

3. ステップ4でコピーした Base64 値を貼り付けます

4. 「Update secret」をクリック

### Google Sheets トークンを更新

同様に `GOOGLE_TOKEN_JSON_B64` を更新します。

---

## ステップ6: ワークフローを再実行

1. GitHub リポジトリの「Actions」タブを開きます

2. 失敗したワークフローを選択します

3. 「Re-run all jobs」をクリックします

4. ワークフローが成功することを確認します ✅

---

## トラブルシューティング

### client_secrets.json が見つからない

**エラー:**
```
❌ ERROR: client_secrets.json not found
```

**解決方法:**
1. Google Cloud Console にアクセス
2. OAuth 2.0 クライアント ID を作成（デスクトップアプリ）
3. JSON をダウンロードして `client_secrets.json` にリネーム
4. プロジェクトルートに配置

詳細: [docs/integration-setup.md](docs/integration-setup.md)

### ブラウザが開かない

**原因:**
ヘッドレス環境（サーバー等）で実行している場合、ブラウザを開けません。

**解決方法:**
ローカル PC で実行してください。

### トークンテストが失敗する

**警告メッセージ:**
```
⚠️  Warning: Token test failed: ...
```

**対処:**
トークンファイル自体は生成されているため、そのまま GitHub Secrets を更新してください。多くの場合、CI 環境では正常に動作します。

---

## 定期メンテナンス

### トークンの有効期限

Google の認証トークンには有効期限があります：

- **推奨更新頻度**: 3ヶ月ごと
- **リマインダー設定**: カレンダーに登録することを推奨

### 自動更新の検討

将来的には、トークンの自動更新機能を実装予定です。現在は手動更新が必要です。

---

## 関連ドキュメント

- [docs/integration-setup.md](docs/integration-setup.md) - 初回セットアップガイド
- [docs/github-actions-troubleshooting.md](docs/github-actions-troubleshooting.md) - その他のトラブルシューティング
- [README.md](README.md) - プロジェクト概要

---

## サポート

問題が解決しない場合は、以下の情報を添えて Issue を作成してください：

- エラーメッセージ全文
- 実行したコマンド
- 使用している OS
- Python バージョン

**Issue URL**: https://github.com/YOUR_USERNAME/YOUR_REPO/issues

---

**最終更新**: 2026-01-04
