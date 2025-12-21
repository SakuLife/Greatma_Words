# クイックスタート
最短で動画を生成するための手順です。

## 1. 環境準備
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## 2. 環境変数を設定
```bash
copy .env.example .env   # macOS/Linux は cp .env.example .env
```
`.env` を開き、以下をセット:
```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here  # Claude 推奨
OPENAI_API_KEY=sk-your-actual-api-key-here     # 併用可

# サムネイル生成（任意）
USE_THUMBNAIL_GENERATION=true
THUMBNAIL_PROVIDER=nanobanana  # または dalle
NANOBANANA_API_KEY=your_nanobanana_api_key_here
```
APIキー取得:
- Claude: https://console.anthropic.com/
- OpenAI: https://platform.openai.com/api-keys
- nanobanana: https://nanobanana.ai/

## 3. VOICEVOX を準備
1. https://voicevox.hiroshiba.jp/ からダウンロード＆インストール  
2. アプリを起動（自動で `http://localhost:50021` で待ち受け）
3. 動作確認（PowerShell 例）:
```bash
Invoke-WebRequest http://localhost:50021/version
```

## 4. 初回実行
```bash
python -m app.cli
```
メニューで `1` を選び、例のように入力:
```
Person name: Peter Thiel
Topic: 競争を避ける戦略
Duration: 15
Upload to YouTube: n
```

以上で最初の動画を生成できます。
