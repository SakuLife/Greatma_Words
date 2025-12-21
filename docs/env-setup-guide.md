# .env ファイル設定ガイド

動画生成を開始するために必要な環境変数の設定方法です。

## ステップ1: .envファイルの作成

プロジェクトルートに `.env` ファイルを作成してください。

```bash
# Windows
cd D:\AutoSystem\PythonSystem\greatman_words
copy .env.example .env

# Mac/Linux
cd /path/to/greatman_words
cp .env.example .env
```

## ステップ2: 必須設定

### 1. AI API キー（最低1つは必須）

#### Claude 3.5 Sonnet（推奨）
```env
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxx
```
取得方法: [https://console.anthropic.com/](https://console.anthropic.com/)

#### または OpenAI
```env
OPENAI_API_KEY=sk-xxxxxxxxxxxxx
```
取得方法: [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)

### 2. VOICEVOX設定（必須）

**VoiceVoxは自動で起動されます。** `D:\App\VOICEVOX\VOICEVOX.exe` を自動検出します。

手動設定（必要に応じて）：
```env
VOICEVOX_API_URL=http://localhost:50021
VOICEVOX_SPEAKER_ID=13  # 青山龍星（VOICEVOX 0.13.0以降）
```

## ステップ3: オプション設定

### 画像生成設定

#### KIEAI nanobanana APIを使用（推奨・安い）
```env
USE_KIEAI=true
KIEAI_API_KEY=your_kieai_api_key_here
KIEAI_API_URL=https://api.kie.ai/api/v1
KIEAI_MODEL=google/nano-banana
```
**メリット**: 文字なし画像生成が可能で、コストが安い。肩書と名前はプログラムで自動追加されます。

#### DALL-Eを使用
```env
USE_DALLE=true
OPENAI_API_KEY=your_openai_api_key_here
```

#### 画像生成をスキップ（既存画像を使用）
```env
SKIP_IMAGE_GENERATION=true
```

### サムネイル生成をスキップ（手動生成する場合）
```env
SKIP_THUMBNAIL_GENERATION=true
```

### サムネイル自動生成（必要な場合のみ）
```env
USE_THUMBNAIL_GENERATION=true
THUMBNAIL_PROVIDER=dalle  # または nanobanana
```

DALL-Eを使用する場合（OPENAI_API_KEYがあれば自動で使用可能）:
```env
USE_DALLE=true
```

ナノバナナプロを使用する場合:
```env
THUMBNAIL_PROVIDER=nanobanana
NANOBANANA_API_KEY=your_nanobanana_api_key_here
```

### 台本生成設定
```env
DEFAULT_LLM_MODEL=claude-3-5-sonnet-20241022
DEFAULT_TEMPERATURE=0.7
```

## ステップ4: オプション設定

### YouTubeアップロード（オプション）
```env
YOUTUBE_CLIENT_SECRETS_FILE=client_secrets.json
YOUTUBE_DEFAULT_PRIVACY=private
```

## 最小構成の例

### 台本生成済み・画像手動・サムネイル手動の場合（最もシンプル）

```env
# VoiceVox設定（自動起動されるが、明示的に設定も可能）
VOICEVOX_API_URL=http://localhost:50021
VOICEVOX_SPEAKER_ID=13  # 青山龍星

# 画像生成をスキップ
SKIP_IMAGE_GENERATION=true

# サムネイル生成をスキップ
SKIP_THUMBNAIL_GENERATION=true
```

**これだけです！AI APIキーは不要です。**

### 画像を自動生成する場合

```env
# 必須: AI API キー（いずれか1つ）
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxx
# または
OPENAI_API_KEY=sk-xxxxxxxxxxxxx

# VoiceVox設定
VOICEVOX_API_URL=http://localhost:50021
VOICEVOX_SPEAKER_ID=13  # 青山龍星

# KIEAI APIで画像生成
USE_KIEAI=true
KIEAI_API_KEY=your_kieai_api_key_here

# または DALL-Eで画像生成
# SKIP_IMAGE_GENERATION=false
# USE_DALLE=true
# OPENAI_API_KEY=your_openai_api_key_here

# サムネイル生成をスキップ（手動生成）
SKIP_THUMBNAIL_GENERATION=true
```

## 設定の確認

設定が正しいか確認するには：

```bash
python -m app.cli
```

メニューから「5. Check settings」を選択して、設定を確認できます。

## トラブルシューティング

### VOICEVOXに接続できない
- VOICEVOXが起動しているか確認
- `http://localhost:50021/version` にアクセスして確認

### APIキーエラー
- APIキーが正しく設定されているか確認
- APIキーにクレジットが残っているか確認

### サムネイルが生成されない
- `USE_THUMBNAIL_GENERATION=true` になっているか確認
- `THUMBNAIL_PROVIDER` が正しく設定されているか確認
- 使用するプロバイダーのAPIキーが設定されているか確認

