# GreatMan Words - AI Video Generator

完全自動化されたビジネス／教養系のYouTube動画を生成するツールです。偉人や哲学者の言葉を題材に、台本づくりから画像・音声・動画編集、サムネイルまでを一気通貫で行います。

## 主な機能
- 台本自動生成：Claude 3.5 Sonnet / GPT-4 を用いた高品質な台本作成（事実確認重視）
- AI画像生成：DALL-E 3 / nanobanana で人物イラスト・スライドを生成
- サムネイル生成：nanobanana または DALL-E で顔入りサムネイルを自動作成
- 音声合成：VOICEVOX による自然な日本語ナレーション
- 動画編集：MoviePy による自動動画生成
- **YouTube 自動アップロード**：Google API を使用（任意）
- **Google Drive 連携**：動画ファイルの自動バックアップ
- **Google Sheets 連携**：タスク管理と動画制作ログの自動記録
- **Discord 通知**：進捗状況とエラーの自動通知

## 生成される動画の特徴
- 15分前後の教養系コンテンツ
- ビジネスパーソン向けの深い洞察
- プロフェッショナルな画像スライド
- 高品質な音声ナレーション（例：青山龍星ボイス）

## セットアップ

### 必要要件
- Python 3.10+
- VOICEVOX（音声合成エンジン）
- FFmpeg（動画処理）

### インストール
```bash
git clone <repository_url>
cd greatman_words

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 環境変数の設定
`.env.example` を `.env` にコピーし、必要な値を設定してください。
```bash
cp .env.example .env  # Windows は copy .env.example .env
```

主な項目（例）:
```env
# Claude 推奨：事実確認に強い
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# OpenAI（高速だが事実確認はClaude推奨）
OPENAI_API_KEY=your_openai_api_key_here

# サムネイル生成
USE_THUMBNAIL_GENERATION=true
THUMBNAIL_PROVIDER=nanobanana  # nanobanana / dalle / stable-diffusion
NANOBANANA_API_KEY=your_nanobanana_api_key_here

# VOICEVOX
VOICEVOX_API_URL=http://localhost:50021
VOICEVOX_SPEAKER_ID=8

# YouTube API（任意）
YOUTUBE_CLIENT_SECRETS_FILE=client_secrets.json
```

### VOICEVOX の設定
1. [VOICEVOX](https://voicevox.hiroshiba.jp/) をダウンロード＆インストール
2. VOICEVOX を起動（デフォルト http://localhost:50021）

### 外部サービス連携（任意）

YouTube、Google Drive、Google Sheets、Discordとの連携が可能です。

**クイックセットアップ**:
```env
# Google API（YouTube、Drive、Sheets共通）
GOOGLE_CLIENT_SECRETS_FILE=client_secrets.json
GOOGLE_DRIVE_FOLDER_ID=あなたのDriveフォルダID
GOOGLE_SHEETS_ID=あなたのスプレッドシートID

# Discord通知
DISCORD_WEBHOOK_URL=あなたのWebhook URL
```

**詳細な設定手順**: `docs/integration-setup.md` を参照してください。

**連携テスト**:
```bash
python test_integrations.py
```

## 使い方

### CLI モードで起動
```bash
python -m app.cli
```

メニュー例:
```
1. Create script interactively
2. Generate video automatically
3. List projects
4. View project details
5. Check settings
6. Exit
```

### 推奨フロー（インタラクティブ台本作成）
1. メニューから `1. Create script interactively` を選択
2. 人物名とテーマを入力
3. AIがドラフトを生成
4. チャット形式で台本を調整（例: 「もっと具体的に」「導入部だけ変更して」）
5. 台本確定後、自動で以下を実行
   - 画像生成（約60秒） → Discord通知
   - 音声合成（約2–3分） → Discord通知
   - 動画編集（約1–2分）
   - サムネイル生成（約30秒）
   - YouTube アップロード（任意） → Discord通知
   - Google Drive バックアップ（任意） → Discord通知
   - Google Sheets ログ記録（任意）
   - 完了通知（YouTube URL・Drive URL付き）

### 完全自動モード
1. メニューから `2. Generate video automatically` を選択
2. 人物名・テーマ・動画時間を入力
3. スタートで一括生成

## プロジェクト管理

### タスク管理
Google Sheetsで全タスクを管理できます：
- [タスク管理スプレッドシート](https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit?gid=0#gid=0)
- [タスク管理ドキュメント](docs/task-management.md)

### Google Drive
生成された動画はGoogle Driveに自動バックアップ：
- [動画フォルダ](https://drive.google.com/drive/folders/YOUR_DRIVE_FOLDER_ID)

### Discord通知
進捗状況はDiscordで受け取れます：
- [Discord Webhook](https://discordapp.com/api/webhooks/REDACTED_WEBHOOK)

### GitHub
- [リポジトリ](https://github.com/SakuLife/Greatma_Words.git)

## GitHub Actions 自動化

このプロジェクトは GitHub Actions で完全自動化されています：

### ワークフロー
- **動画自動生成**: 毎朝10時（JST）に自動で動画を生成・アップロード
- **YouTube 統計更新**: 6時間ごとに視聴回数・いいね数を自動更新
- **予約投稿**: 生成した動画を毎日18時（JST）に自動公開

### トークン管理
認証トークンが期限切れになった場合：

```bash
# YouTube トークンを再生成
python generate_youtube_token.py

# Google Sheets トークンを再生成
python generate_sheets_token.py
```

詳細は [GitHub Actions トラブルシューティング](docs/github-actions-troubleshooting.md) を参照。

## ドキュメント
- [QUICKSTART.md](QUICKSTART.md) - クイックスタートガイド
- [docs/integration-setup.md](docs/integration-setup.md) - 外部サービス連携設定
- [docs/youtube-scheduled-publishing.md](docs/youtube-scheduled-publishing.md) - YouTube 予約投稿ガイド
- [docs/github-actions-troubleshooting.md](docs/github-actions-troubleshooting.md) - GitHub Actions トラブルシューティング
- [docs/task-management.md](docs/task-management.md) - タスク管理一覧
- [docs/google-sheets-setup.md](docs/google-sheets-setup.md) - Sheets詳細設定
- [docs/copyright-guidelines.md](docs/copyright-guidelines.md) - 著作権ガイドライン
- [docs/env-setup-guide.md](docs/env-setup-guide.md) - 環境セットアップ

## ライセンス・注意
- 著作権・肖像権の扱いに注意してください（`docs/copyright-guidelines.md` 参照）。
- 各APIキーは個人の責任で管理してください。
- `.env`、`client_secrets.json`、`*_token.json` は絶対にGitにコミットしないでください。
