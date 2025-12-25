# サムネイル生成プロンプト（Cursorチャット用）

このプロンプトをCursorのチャットに貼り付けて、サムネイル生成用のプロンプトを作成してください。

---

## 使い方

1. 下記のテンプレートをコピー
2. `{{PERSON_NAME}}` と `{{TOPIC}}` を実際の値に置き換え
3. Cursorのチャットに貼り付けて送信
4. 生成されたプロンプトを画像生成AI（DALL-E、Midjourney、ナノバナナなど）に使用

---

# サムネイル生成プロンプトテンプレート

## 基本プロンプト

```
Professional YouTube thumbnail featuring {{PERSON_NAME}}.
Topic: {{TOPIC}}.
Style: professional, business-like, clean, modern, high quality, eye-catching,
portrait of {{PERSON_NAME}} prominently displayed,
clean background, suitable for educational content,
1280x720 aspect ratio, vibrant colors, professional photography style.
```

## スタイル別プロンプト

### プロフェッショナルスタイル
```
Professional YouTube thumbnail featuring {{PERSON_NAME}}.
Topic: {{TOPIC}}.
Style: professional, business-like, clean, modern, high quality,
portrait of {{PERSON_NAME}} on the left side,
bold text overlay on the right side with key message,
dark background with accent colors,
1280x720 aspect ratio, cinematic lighting,
suitable for educational business content.
```

### ドラマチックスタイル
```
Dramatic YouTube thumbnail featuring {{PERSON_NAME}}.
Topic: {{TOPIC}}.
Style: dramatic lighting, cinematic, impactful, high contrast,
portrait of {{PERSON_NAME}} with intense expression,
bold typography with shocking statement,
dark moody background,
1280x720 aspect ratio,
suitable for thought-provoking educational content.
```

### モダンスタイル
```
Modern YouTube thumbnail featuring {{PERSON_NAME}}.
Topic: {{TOPIC}}.
Style: modern, sleek, contemporary design, minimalist,
portrait of {{PERSON_NAME}} with clean composition,
geometric elements, bright colors,
1280x720 aspect ratio,
suitable for modern business education content.
```

## 使用例

### ピーター・ティール × 競争を避ける戦略
```
Professional YouTube thumbnail featuring Peter Thiel.
Topic: 競争を避ける戦略.
Style: professional, business-like, clean, modern, high quality, eye-catching,
portrait of Peter Thiel prominently displayed,
bold text "競争は負け犬がすること" in Japanese,
clean dark background, suitable for educational content,
1280x720 aspect ratio, vibrant colors, professional photography style.
```

### スティーブ・ジョブズ × シンプルさの力
```
Dramatic YouTube thumbnail featuring Steve Jobs.
Topic: シンプルさの力.
Style: dramatic lighting, cinematic, impactful,
portrait of Steve Jobs with intense expression,
bold typography "シンプルさの力" in Japanese,
dark moody background with Apple-inspired minimalism,
1280x720 aspect ratio,
suitable for thought-provoking educational content.
```

---

## 画像生成AI別の推奨設定

### DALL-E 3
- サイズ: 1024x1024（生成後、1280x720にリサイズ）
- 品質: hd
- スタイル: natural

### Midjourney
- アスペクト比: `--ar 16:9`
- スタイル: `--style raw` または `--style 4.0`
- 品質: `--quality 2`

### ナノバナナプロ
- サイズ: 1280x720
- スタイル: professional
- 品質: high

