# 統合セットアップガイド - YouTube・Google Drive・Google Sheets・Discord連携

このガイドでは、GreatMan Words Generatorの外部サービス連携をセットアップする手順を説明します。

## 概要

このプロジェクトは以下のサービスと連携可能です：

- **YouTube**: 動画の自動アップロード
- **Google Drive**: 動画ファイルのバックアップ
- **Google Sheets**: タスク管理と動画制作ログ
- **Discord**: 進捗通知とエラーアラート

## 事前準備

### 必要なもの

1. Googleアカウント（YouTube、Drive、Sheets用）
2. Google Cloud Platformプロジェクト
3. Discord Server（通知用）

---

## 1. Google Cloud Platform セットアップ

### 1.1 プロジェクト作成

1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. 新しいプロジェクトを作成
   - プロジェクト名: 例）`GreatMan Words Generator`
3. プロジェクトを選択

### 1.2 YouTube Data API 有効化

1. 左メニューから **APIとサービス > ライブラリ** を選択
2. 「YouTube Data API v3」を検索
3. **有効にする** をクリック

### 1.3 Google Drive API 有効化

1. 同様に「Google Drive API」を検索
2. **有効にする** をクリック

### 1.4 Google Sheets API 有効化

1. 「Google Sheets API」を検索
2. **有効にする** をクリック

### 1.5 OAuth 2.0 クライアント作成

1. **APIとサービス > 認証情報** を選択
2. **認証情報を作成 > OAuth クライアント ID** をクリック
3. 同意画面の構成（初回のみ）:
   - User Type: **外部**
   - アプリ名: `GreatMan Words Generator`
   - サポートメール: 自分のメールアドレス
   - スコープ: 追加不要（後で設定）
   - テストユーザー: 自分のGoogleアカウント
4. OAuth クライアント作成:
   - アプリケーションの種類: **デスクトップアプリ**
   - 名前: `GreatMan Words Desktop Client`
5. **作成** をクリック
6. JSONファイルをダウンロード
7. ダウンロードしたファイルを `client_secrets.json` にリネーム
8. プロジェクトルートに配置

```bash
D:\AutoSystem\PythonSystem\greatman_words\
├── client_secrets.json  ← ここに配置
├── .env
├── app/
└── ...
```

---

## 2. Google Drive セットアップ

### 2.1 アップロード先フォルダ作成

1. [Google Drive](https://drive.google.com/)にアクセス
2. 新しいフォルダを作成: 例）`GreatMan Words Videos`
3. フォルダを開いてURLを確認:
   ```
   https://drive.google.com/drive/folders/YOUR_DRIVE_FOLDER_ID
                                          ↑
                                    フォルダID（この部分をコピー）
   ```
4. フォルダIDを `.env` ファイルに記載:
   ```env
   GOOGLE_DRIVE_FOLDER_ID=YOUR_DRIVE_FOLDER_ID
   ```

---

## 3. Google Sheets セットアップ

### 3.1 スプレッドシート作成

1. [Google Sheets](https://sheets.google.com/)にアクセス
2. 新しいスプレッドシートを作成: `GreatMan Words - タスク管理`
3. URLからスプレッドシートIDを取得:
   ```
   https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit
                                          ↑
                                    スプレッドシートID（この部分をコピー）
   ```
4. スプレッドシートIDを `.env` に記載:
   ```env
   GOOGLE_SHEETS_ID=YOUR_SPREADSHEET_ID
   ```

### 3.2 シート構成

以下のシートを作成してください：

#### シート1: タスクマスター

| タスクID | カテゴリ | タスク内容 | 優先度 | ステータス | 担当者 | 期限 | 備考 |
|---------|---------|-----------|--------|----------|--------|------|------|

**CSVインポート方法**:
1. `docs/tasks-master.csv` をダウンロード
2. スプレッドシートで **ファイル > インポート**
3. CSVファイルを選択してインポート

#### シート2: 動画制作ログ

| 日付 | 人物名 | テーマ | 動画時間 | 生成時間 | プロジェクトパス | YouTube URL | 視聴回数 | いいね数 | コメント数 | Google Drive |
|------|--------|--------|---------|---------|--------------|-------------|---------|---------|----------|--------------|

**ヘッダー行を手動で作成してください**

#### シート3: コスト管理

| 日付 | サービス | 用途 | 使用量 | 単価 | 合計金額 | 備考 |
|------|---------|------|--------|------|---------|------|

**ヘッダー行を手動で作成してください**

---

## 4. Discord Webhook セットアップ

### 4.1 Webhook URL取得

1. Discordでサーバーを開く
2. 通知を送りたいチャンネルで **歯車アイコン（チャンネル設定）** をクリック
3. **連携サービス** を選択
4. **ウェブフック** をクリック
5. **新しいウェブフック** をクリック
6. 名前を設定: 例）`GreatMan Words Bot`
7. アイコンを設定（任意）
8. **ウェブフックURLをコピー** をクリック
9. URLを `.env` に記載:
   ```env
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/1234567890/abcdefg...
   ```

### 4.2 通知内容

Discordには以下の通知が送信されます：

- 🎬 動画生成開始
- 📝 台本生成完了
- 🎨 画像生成完了
- 🎤 音声合成完了
- 🎉 動画生成完了（YouTube URLとDrive URL付き）
- 📺 YouTube アップロード完了
- 💾 Google Drive アップロード完了
- 🚨 エラー通知
- ⏳ 進捗状況（タスクの進行状況）

---

## 5. 環境変数設定

`.env.example` を `.env` にコピーして編集:

```bash
cp .env.example .env  # Windows: copy .env.example .env
```

### 必須項目

```env
# Google API
GOOGLE_CLIENT_SECRETS_FILE=client_secrets.json
GOOGLE_DRIVE_FOLDER_ID=あなたのフォルダID
GOOGLE_SHEETS_ID=あなたのスプレッドシートID

# Discord
DISCORD_WEBHOOK_URL=あなたのWebhook URL

# AI API（いずれか1つ以上）
ANTHROPIC_API_KEY=your_anthropic_api_key
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key

# KIEAI（画像生成）
KIEAI_API_KEY=your_kieai_api_key
```

---

## 6. 初回認証

### 6.1 YouTube認証

初回実行時に自動的にブラウザが開き、OAuth認証が求められます。

```bash
python -m app.cli
# メニューから動画生成を選択
```

1. ブラウザが開く
2. Googleアカウントでログイン
3. 権限を許可
4. `token.json` が自動生成される

### 6.2 Google Drive認証

同様に初回アクセス時にブラウザが開きます。

- `drive_token.json` が自動生成される

### 6.3 Google Sheets認証

同様に初回アクセス時にブラウザが開きます。

- `sheets_token.json` が自動生成される

---

## 7. テスト実行

### 7.1 Discord通知テスト

```python
# test_discord.py
import asyncio
from app.services.discord_notifier import DiscordNotifier

async def test():
    notifier = DiscordNotifier()
    await notifier.send_message("テスト通知", title="接続確認", color=0x00FF00)

asyncio.run(test())
```

```bash
python test_discord.py
```

Discordチャンネルに通知が届けば成功です。

### 7.2 Google Drive テスト

```python
# test_drive.py
import asyncio
from pathlib import Path
from app.services.drive_manager import DriveManager

async def test():
    manager = DriveManager()
    await manager.authenticate()

    # テストファイル作成
    test_file = Path("test.txt")
    test_file.write_text("Hello from GreatMan Words!")

    # アップロード
    result = await manager.upload_file(test_file)
    print(f"Uploaded: {result['url']}")

    test_file.unlink()  # 削除

asyncio.run(test())
```

```bash
python test_drive.py
```

Google Driveにファイルがアップロードされれば成功です。

### 7.3 Google Sheets テスト

```python
# test_sheets.py
import asyncio
from app.services.sheets_manager import SheetsManager

async def test():
    manager = SheetsManager()
    await manager.authenticate()

    # テストログ記録
    await manager.log_video_production(
        person_name="テスト太郎",
        theme="接続確認",
        video_duration=60.0,
        generation_time=30.0,
    )
    print("ログ記録成功")

asyncio.run(test())
```

```bash
python test_sheets.py
```

Google Sheetsに行が追加されれば成功です。

---

## 8. 完全統合テスト

すべての連携を有効にして動画を生成:

```bash
python -m app.cli
# メニューから「2. Generate video automatically」を選択
```

以下が自動実行されます：

1. 台本生成 → Discord通知
2. 画像生成 → Discord通知
3. 音声合成 → Discord通知
4. 動画編集
5. サムネイル生成
6. YouTube アップロード → Discord通知
7. Google Drive アップロード → Discord通知
8. Google Sheets ログ記録
9. 完了通知 → Discord（YouTube URLとDrive URL付き）

---

## 9. トラブルシューティング

### 認証エラー

**エラー**: `Client secrets file not found`

**解決策**:
- `client_secrets.json` がプロジェクトルートにあるか確認
- ファイル名が正しいか確認

### スコープエラー

**エラー**: `insufficient permissions`

**解決策**:
1. `token.json`, `drive_token.json`, `sheets_token.json` を削除
2. 再度認証（自動でブラウザが開く）
3. すべての権限を許可

### Webhook エラー

**エラー**: `Discord webhook failed: 404`

**解決策**:
- Webhook URLが正しいか確認
- Webhookが削除されていないか確認（Discord設定で再確認）

### スプレッドシートが見つからない

**エラー**: `Spreadsheet not found`

**解決策**:
1. スプレッドシートIDが正しいか確認
2. スプレッドシートが自分のアカウントで作成されているか確認
3. スプレッドシートが削除されていないか確認

---

## 10. セキュリティ注意事項

### 機密情報の管理

以下のファイルは **絶対にGitにコミットしないでください**：

```
.env
client_secrets.json
token.json
drive_token.json
sheets_token.json
```

`.gitignore` に必ず追加:

```gitignore
.env
*.json  # トークンファイル
client_secrets.json
```

### Webhook URLの保護

Discord Webhook URLは機密情報です。公開リポジトリにコミットしないでください。

---

## 11. 統合の無効化

特定のサービスを無効にしたい場合：

```python
from app.services.video_workflow import VideoWorkflow

# YouTube無効、Driveのみ有効
workflow = VideoWorkflow(
    enable_youtube=False,
    enable_drive=True,
    enable_sheets=True,
    enable_discord=True,
)
```

または `.env` で設定:

```env
# 各サービスを無効化（環境変数を空にする）
DISCORD_WEBHOOK_URL=
GOOGLE_DRIVE_FOLDER_ID=
GOOGLE_SHEETS_ID=
```

---

## 関連ドキュメント

- [README.md](../README.md) - プロジェクト概要
- [google-sheets-setup.md](./google-sheets-setup.md) - Sheets詳細設定
- [task-management.md](./task-management.md) - タスク管理一覧

---

**セットアップ完了後、すべての連携が自動化されます！**
