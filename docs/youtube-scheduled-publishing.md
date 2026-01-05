# YouTube 予約投稿ガイド

このドキュメントでは、YouTube の予約投稿機能の使い方とトラブルシューティングを説明します。

## YouTube API 予約投稿の仕組み

### 基本的な流れ

1. 動画を `privacyStatus: "private"` でアップロード
2. `publishAt` パラメータに公開日時（UTC）を指定
3. 指定時刻になると、YouTube が自動的に動画を公開

### API リクエストの例

```json
{
  "snippet": {
    "title": "動画のタイトル",
    "description": "動画の説明",
    "categoryId": "22"
  },
  "status": {
    "privacyStatus": "private",
    "publishAt": "2026-01-05T09:00:00.000Z",
    "selfDeclaredMadeForKids": false
  }
}
```

## 重要な制約

### 1. プライバシー設定

- **必須**: `privacyStatus` は `"private"` でなければなりません
- `"public"` や `"unlisted"` では予約投稿できません
- 指定時刻になると、YouTube が自動的に公開（`public`）に変更します

### 2. 日時のフォーマット

- **必須フォーマット**: ISO 8601 / RFC 3339
- **例**: `2026-01-05T09:00:00.000Z`
- **タイムゾーン**: 必ずUTC（`Z` 接尾辞）
- **ミリ秒**: `.000` を含める必要があります

### 3. 時刻の制約

- **最低**: 現在時刻から **15分以上** 先
- **最大**: 現在時刻から **6ヶ月以内**
- **過去の時刻**: エラーになります

### 4. アカウントの制限

YouTube Data API v3 の予約投稿機能は、以下のアカウントで利用可能です：

- **確認済みアカウント**: YouTube でアカウント確認が完了していること
- **コミュニティガイドライン違反がないこと**
- 一部の国・地域では利用できない可能性があります

## 実装例

### Python での実装

```python
from datetime import datetime, timezone, timedelta

# JST 18:00 を UTC に変換
JST = timezone(timedelta(hours=9))
now_jst = datetime.now(JST)
target_time = now_jst.replace(hour=18, minute=0, second=0, microsecond=0)

if now_jst >= target_time:
    target_time += timedelta(days=1)

# UTC に変換
target_time_utc = target_time.astimezone(timezone.utc)

# YouTube API フォーマット
publish_at_iso = target_time_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")

print(f"Publish at: {publish_at_iso}")
# 出力例: Publish at: 2026-01-05T09:00:00.000Z
```

## トラブルシューティング

### エラー: "The request metadata specifies an invalid scheduled publishing time."

#### 原因1: 時刻が過去または近すぎる

**解決方法**:
- 現在時刻から最低15分以上先に設定してください
- スクリプトの実行タイミングを確認してください

#### 原因2: 日時のフォーマットが間違っている

**解決方法**:
- 正しいフォーマット: `2026-01-05T09:00:00.000Z`
- ミリ秒（`.000`）を含めてください
- タイムゾーンは必ず `Z`（UTC）にしてください

#### 原因3: プライバシー設定が間違っている

**解決方法**:
- `privacyStatus` を `"private"` に設定してください
- `"public"` や `"unlisted"` では予約投稿できません

#### 原因4: アカウントが予約投稿をサポートしていない

**解決方法**:
1. YouTube Studio にログイン
2. 手動で動画をアップロードして予約投稿を試す
3. 予約投稿機能が利用可能か確認

**確認方法**:
- YouTube Studio → アップロード → 公開設定 → スケジュール設定
- この機能が表示されない場合、APIでも利用できません

### エラー: "Forbidden"

#### 原因: OAuth スコープが不足している

**解決方法**:

1. `.env` ファイルで以下のスコープを確認:
   ```env
   YOUTUBE_OAUTH_SCOPES=https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube
   ```

2. 既存のトークンを削除:
   ```bash
   rm token.json
   ```

3. 再認証:
   ```bash
   python generate_youtube_token.py
   ```

### エラー: "quotaExceeded"

#### 原因: YouTube Data API のクォータ制限

**解決方法**:
- 1日のクォータ: 10,000ユニット
- 動画アップロード: 1,600ユニット/回
- 翌日（太平洋標準時0時）までお待ちください

## YouTube Studio での予約投稿との違い

### YouTube Studio

- UI で簡単に設定可能
- 公開時にコミュニティ投稿も自動作成可能
- サムネイルのA/Bテストが可能

### YouTube Data API

- プログラムで自動化可能
- 大量の動画を一括スケジュール可能
- CI/CD パイプラインに統合可能

## ベストプラクティス

### 1. 時刻の設定

```python
# ❌ 悪い例: ハードコード
publish_at = "2026-01-05T09:00:00.000Z"

# ✅ 良い例: 動的に計算
from datetime import datetime, timezone, timedelta

def calculate_next_publish_time(target_hour=18):
    JST = timezone(timedelta(hours=9))
    now_jst = datetime.now(JST)
    target_time = now_jst.replace(hour=target_hour, minute=0, second=0, microsecond=0)

    if now_jst >= target_time:
        target_time += timedelta(days=1)

    return target_time.astimezone(timezone.utc)
```

### 2. エラーハンドリング

```python
try:
    video_id = await youtube.upload_video(video_path, metadata)
except RuntimeError as e:
    if "invalid scheduled publishing time" in str(e):
        # 予約投稿を無効にして再試行
        metadata.publish_at = None
        metadata.privacy_status = "private"
        video_id = await youtube.upload_video(video_path, metadata)
    else:
        raise
```

### 3. ログ記録

```python
logger.info(f"Scheduled publish time: {publish_at_iso}")
logger.info(f"Time until publish: {time_diff / 3600:.1f} hours")
```

## テスト方法

### 1. ローカルテスト

```bash
# トークンを生成
python generate_youtube_token.py

# テスト実行
python test_scheduled_publish.py
```

### 2. 動作確認

1. 動画がアップロードされることを確認
2. YouTube Studio で動画を確認:
   - 公開設定が「非公開」になっていること
   - スケジュール設定が正しいこと
3. 指定時刻に自動公開されることを確認

## 関連ドキュメント

- [YouTube Data API v3 - Videos: insert](https://developers.google.com/youtube/v3/docs/videos/insert)
- [YouTube Data API v3 - Video Resource](https://developers.google.com/youtube/v3/docs/videos#resource)
- [RFC 3339 - Date and Time on the Internet](https://www.rfc-editor.org/rfc/rfc3339)

---

**最終更新**: 2026-01-04
