# GitHub Actions での自動生成メモ

このリポジトリを GitHub Actions（自前の Windows 自己ホストランナー）で自動実行するための設定手順です。

## 前提
- ランナー: Windows self-hosted で VOICEVOX がインストール済み。ラベル `self-hosted`, `Windows`, `voicevox` を付与してください。
- VOICEVOX 起動パス: 既定では `D:\App\VOICEVOX\VOICEVOX.exe`。異なる場合は `VOICEVOX_EXE_PATH` を Actions Secrets に登録。
- Python 3.11 以上を推奨。

## 必須 Secrets（Actions > Secrets and variables > Actions）
- `GEMINI_API_KEY`
- `KIEAI_API_KEY`（nanobanana）
- `NANOBANANA_API_KEY`
- `GOOGLE_DRIVE_FOLDER_ID`
- `GOOGLE_SHEETS_ID`
- `DISCORD_WEBHOOK_URL`
- `GOOGLE_CLIENT_SECRETS_JSON_B64` : `client_secrets.json` を base64 化した文字列
- （任意）`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- （任意）`VOICEVOX_EXE_PATH` : デフォルト以外の場所にある場合
- （任意）`YOUTUBE_TOKEN_JSON_B64` : 事前に取得した YouTube OAuth token.json を base64 化
- （任意）`GOOGLE_TOKEN_JSON_B64` : Drive/Sheets 用の token.json を base64 化

> 注: Hosted Runner では VOICEVOX がないため、必ず self-hosted Windows ランナーを使ってください。

## ワークフロー
- 追加済み: `.github/workflows/auto-generate.yml`
- 手動トリガー (`workflow_dispatch`) で `duration_minutes` を指定可能（デフォルト 15 分）。
- フロー: 依存インストール → secrets から `.env`/`client_secrets.json`/token を復元 → VOICEVOX 起動確認 → `python generate_data_driven_video.py auto <duration>` 実行 → 生成物を Artifact で回収。

## よくある躓きポイント
- YouTube/Drive/Sheets の OAuth は非対話で行うため、必ず token.json を base64 で渡してください。
- VOICEVOX ポート 50021 が開いていないと音声合成で失敗します。ランナー起動時に常駐させるか、Secrets にパスを入れて自動起動させてください。
- 生成物は `data/projects/...` に出力されます。Artifacts で mp4/images/metadata をアップロードしています。
