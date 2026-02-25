# GitHub Actions トラブルシューティングガイド

このドキュメントでは、GitHub Actions ワークフローでよく発生する問題の解決方法を説明します。

## 目次

1. [Google認証トークンの期限切れ](#google認証トークンの期限切れ)
2. [YouTube アップロード失敗](#youtube-アップロード失敗)
3. [Google Sheets 更新失敗](#google-sheets-更新失敗)
4. [VOICEVOX 起動失敗](#voicevox-起動失敗)
5. [依存関係のインストール失敗](#依存関係のインストール失敗)

---

## Google認証トークンの期限切れ

### 症状

```
google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {...})
```

または

```
Failed to authenticate with Google Sheets: ('invalid_grant: Token has been expired or revoked.', {...})
```

### 原因

GitHub Secrets に保存されている Google 認証トークン（`GOOGLE_TOKEN_JSON_B64` または `YOUTUBE_TOKEN_JSON_B64`）が期限切れになっています。

### 解決方法

#### YouTube トークンの再生成

1. **ローカル環境でトークンを生成**

```bash
# リポジトリをクローン（まだの場合）
git clone https://github.com/YOUR_USERNAME/Greatma_Words.git
cd Greatma_Words

# 仮想環境を有効化
python -m venv .venv
# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate

# 依存関係をインストール
pip install -r requirements.txt

# client_secrets.json が配置されているか確認
# なければ Google Cloud Console からダウンロードして配置

# YouTube トークンを生成
python generate_youtube_token.py
```

2. **ブラウザで認証**
   - スクリプトがブラウザを開きます
   - Google アカウントでログイン
   - YouTube へのアクセス権限を許可
   - 「認証成功」と表示されたらブラウザを閉じる

3. **Base64 値をコピー**
   - ターミナルに表示される長い文字列（Base64エンコード値）をコピー
   - または `youtube_token_b64.txt` からコピー

4. **GitHub Secrets を更新**
   - https://github.com/YOUR_USERNAME/YOUR_REPO/settings/secrets/actions にアクセス
   - `YOUTUBE_TOKEN_JSON_B64` を選択（なければ「New repository secret」をクリック）
   - コピーした Base64 値を貼り付け
   - 「Update secret」または「Add secret」をクリック

5. **ワークフローを再実行**
   - Actions タブから失敗したワークフローを選択
   - 「Re-run all jobs」をクリック

#### Google Sheets トークンの再生成

同様の手順で Google Sheets トークンも再生成できます：

```bash
# Google Sheets トークンを生成
python generate_sheets_token.py
```

その後、GitHub Secrets の `GOOGLE_TOKEN_JSON_B64` を更新してください。

---

## YouTube アップロード失敗

### 症状

```
Failed to upload video to YouTube: quotaExceeded
```

または

```
YouTube API quota exceeded
```

### 原因

YouTube Data API の1日のクォータ制限（10,000ユニット）を超えています。

### 解決方法

1. **翌日まで待つ**
   - クォータは毎日午前0時（太平洋標準時）にリセットされます

2. **クォータを確認**
   - https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas
   - 現在の使用量を確認

3. **クォータ増加をリクエスト**（必要に応じて）
   - Google Cloud Console でクォータ増加をリクエストできます
   - ただし、審査に時間がかかる場合があります

4. **アップロード頻度を調整**
   - ワークフローの cron スケジュールを変更して、1日のアップロード回数を減らす

---

## Google Sheets 更新失敗

### 症状

```
Spreadsheet not found
```

または

```
The caller does not have permission
```

### 原因と解決方法

#### 原因1: スプレッドシートIDが間違っている

**解決方法:**
1. Google Sheets の URL を確認:
   ```
   https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID_HERE/edit
                                          ↑ この部分がスプレッドシートID
   ```

2. GitHub Secrets の `GOOGLE_SHEETS_ID` を更新:
   - https://github.com/YOUR_USERNAME/YOUR_REPO/settings/secrets/actions
   - `GOOGLE_SHEETS_ID` を正しいIDに更新

#### 原因2: スプレッドシートが削除された

**解決方法:**
1. Google Sheets で新しいスプレッドシートを作成
2. `docs/google-sheets-setup.md` に従ってシートを構成
3. 新しいスプレッドシートIDで GitHub Secrets を更新

#### 原因3: 認証トークンが期限切れ

**解決方法:**
- 上記「[Google認証トークンの期限切れ](#google認証トークンの期限切れ)」を参照

---

## VOICEVOX 起動失敗

### 症状

```
VOICEVOX API did not become ready within 60 seconds
```

### 原因

Docker で VOICEVOX の起動に時間がかかっています。

### 解決方法

#### 方法1: 待機時間を延長

`.github/workflows/auto-generate.yml` を編集:

```yaml
- name: Start VOICEVOX with Docker
  run: |
    docker compose up -d voicevox

    # Wait for API to be ready (max 120 seconds)  ← 60→120に変更
    echo "Waiting for VOICEVOX API to be ready..."
    for i in {1..60}; do  ← 30→60に変更
      sleep 2
      if curl -s http://localhost:50021/version > /dev/null 2>&1; then
        echo "VOICEVOX API is ready!"
        exit 0
      fi
      echo "Attempt $i/60 - Waiting for API..."
    done
    echo "VOICEVOX API did not become ready within 120 seconds"
    exit 1
```

#### 方法2: Docker ログを確認

ワークフローに以下を追加してログを確認:

```yaml
- name: Check VOICEVOX logs
  if: failure()
  run: |
    docker compose logs voicevox
```

---

## 依存関係のインストール失敗

### 症状

```
ERROR: Could not find a version that satisfies the requirement...
```

### 原因

`requirements.txt` に記載されているパッケージのバージョンが存在しないか、互換性がありません。

### 解決方法

1. **ローカルで依存関係を確認**

```bash
pip install -r requirements.txt
```

2. **バージョンを更新**

問題のあるパッケージのバージョンを緩和:

```txt
# Before
moviepy==1.0.3

# After (バージョン指定を緩和)
moviepy>=1.0.0,<2.0.0
```

3. **依存関係を再生成**

```bash
# 既存のパッケージを削除
pip freeze > temp.txt
pip uninstall -r temp.txt -y

# 新しくインストール
pip install -r requirements.txt

# requirements.txt を更新
pip freeze > requirements.txt
```

4. **変更をコミット**

```bash
git add requirements.txt
git commit -m "Update dependencies"
git push
```

---

## その他のよくある問題

### ワークフローが自動実行されない

#### 原因: Cron スケジュールの時刻が間違っている

**解決方法:**
- Cron は UTC 時刻で指定する必要があります
- 日本時間（JST）から UTC に変換: JST - 9時間

例:
- 日本時間 18:00 → UTC 09:00
- Cron: `0 9 * * *`

### Secrets が読み込まれない

#### 原因: Secrets 名が間違っている

**解決方法:**
1. ワークフローファイルで使用している Secrets 名を確認:
   ```yaml
   ${{ secrets.GOOGLE_SHEETS_ID }}
   ```

2. GitHub Secrets で同じ名前が設定されているか確認:
   - https://github.com/YOUR_USERNAME/YOUR_REPO/settings/secrets/actions

3. 大文字・小文字を含めて完全一致する必要があります

---

## 予防的なメンテナンス

### 定期的なトークン更新

Google の認証トークンは定期的に更新することを推奨します：

**推奨頻度:**
- YouTube トークン: 3ヶ月ごと
- Google Sheets トークン: 3ヶ月ごと

**更新手順:**
1. カレンダーにリマインダーを設定
2. 期限が近づいたら上記の手順でトークンを再生成
3. GitHub Secrets を更新

### ワークフローの監視

GitHub Actions の通知を有効化:
1. リポジトリの Settings → Notifications
2. 「Actions」の通知を有効化
3. ワークフロー失敗時にメールで通知を受け取る

### Discord 通知の活用

Discord Webhook を設定している場合、エラーも通知されます：
- 🚨 エラー通知が届いたらすぐに確認
- ログから原因を特定
- 必要に応じてトークンを更新

---

## サポート

### さらにヘルプが必要な場合

1. **ログを確認**
   - GitHub Actions の詳細ログを確認
   - エラーメッセージをコピー

2. **Issue を作成**
   - https://github.com/YOUR_USERNAME/YOUR_REPO/issues
   - エラーメッセージとログを添付

3. **関連ドキュメント**
   - [integration-setup.md](./integration-setup.md) - 初期セットアップ
   - [google-sheets-setup.md](./google-sheets-setup.md) - Sheets 設定
   - [README.md](../README.md) - プロジェクト概要

---

**最終更新**: 2026-01-04
