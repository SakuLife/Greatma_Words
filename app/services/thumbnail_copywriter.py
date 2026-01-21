"""
サムネイル用キャッチコピー生成サービス

台本や人物情報から、YouTubeサムネイルに最適な
クリックを誘発するキャッチコピーを生成する
"""

import random
import google.generativeai as genai

from app.config import settings
from app.utils.logger import logger


class ThumbnailCopywriter:
    """YouTubeサムネイル用のキャッチコピーを生成"""

    # トピックに応じたキャッチコピーパターン
    COPY_PATTERNS = {
        "思考": [
            {"main": "思考が変わる", "sub": "成功者だけが知る"},
            {"main": "考え方が9割", "sub": "結果を出す人の"},
            {"main": "頭の使い方", "sub": "天才たちの"},
        ],
        "成功": [
            {"main": "成功の法則", "sub": "誰も教えない"},
            {"main": "勝ち続ける人", "sub": "なぜ結果が出るのか"},
            {"main": "圧倒的な差", "sub": "ここで生まれる"},
        ],
        "お金": [
            {"main": "お金の真実", "sub": "富裕層だけが知る"},
            {"main": "資産を築く人", "sub": "共通点はこれ"},
            {"main": "投資の極意", "sub": "億万長者の"},
        ],
        "習慣": [
            {"main": "習慣が全て", "sub": "毎日やるべきこと"},
            {"main": "朝の過ごし方", "sub": "成功者に学ぶ"},
            {"main": "継続の秘訣", "sub": "なぜ続けられるのか"},
        ],
        "人生": [
            {"main": "人生が変わる", "sub": "今日から実践"},
            {"main": "後悔しない", "sub": "生き方の選択"},
            {"main": "運命を変える", "sub": "たった一つの"},
        ],
        "仕事": [
            {"main": "仕事の本質", "sub": "プロの流儀"},
            {"main": "結果を出す人", "sub": "何が違うのか"},
            {"main": "圧倒的成果", "sub": "この方法で"},
        ],
        "リーダー": [
            {"main": "リーダーの条件", "sub": "人がついてくる"},
            {"main": "決断力の差", "sub": "トップの思考法"},
            {"main": "組織を動かす", "sub": "たった一つの"},
        ],
        "default": [
            {"main": "知らないと損", "sub": "今すぐ学べ"},
            {"main": "これが答えだ", "sub": "迷いが消える"},
            {"main": "真実を話そう", "sub": "誰も言わない"},
            {"main": "ここで差がつく", "sub": "成功者の共通点"},
            {"main": "なぜ勝てるのか", "sub": "理由はシンプル"},
            {"main": "常識を疑え", "sub": "本当の正解"},
        ],
    }

    def __init__(self):
        """Initialize with Gemini API"""
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.model = genai.GenerativeModel("gemini-2.0-flash")
        else:
            self.model = None
            logger.warning("Gemini API key not configured")

    async def generate_thumbnail_copy(
        self,
        person_name: str,
        topic: str,
        script_summary: str | None = None,
        quote: str | None = None,
    ) -> dict:
        """
        サムネイル用のキャッチコピーを生成

        Args:
            person_name: 人物名
            topic: 動画のトピック
            script_summary: 台本の要約（オプション）
            quote: 名言（オプション）

        Returns:
            dict: {
                "main_copy": "メインキャッチコピー（大きく表示）",
                "sub_copy": "サブコピー（補足）",
                "keywords": ["キーワード1", "キーワード2"],
            }
        """
        # まずAI生成を試みる
        if self.model:
            prompt = self._build_prompt(person_name, topic, script_summary, quote)
            try:
                response = self.model.generate_content(prompt)
                result = self._parse_response(response.text, topic)
                logger.info(f"AIキャッチコピー生成: {result['main_copy']} / {result['sub_copy']}")
                return result
            except Exception as e:
                logger.warning(f"AI生成失敗、動的フォールバック使用: {e}")

        # フォールバック：トピックに基づいて動的生成
        return self._generate_dynamic_copy(person_name, topic, quote)

    def _build_prompt(
        self,
        person_name: str,
        topic: str,
        script_summary: str | None,
        quote: str | None,
    ) -> str:
        """キャッチコピー生成用プロンプトを構築"""
        context = f"""
人物: {person_name}
トピック: {topic}
"""
        if quote:
            context += f"名言: {quote}\n"
        if script_summary:
            context += f"台本概要: {script_summary[:500]}\n"

        prompt = f"""あなたはYouTubeサムネイルの専門家です。
以下の情報から、視聴者がクリックしたくなるサムネイル用キャッチコピーを生成してください。

{context}

【要件】
1. メインコピー: 6〜8文字の強烈なインパクトワード
   - トピックの核心を突く言葉
   - 視聴者の好奇心を刺激する
   - 「必見」「衝撃」などの使い古された言葉は避ける
   - 具体的で新鮮な表現を使う

2. サブコピー: 10〜15文字の補足
   - メインを補強する具体的な内容
   - 数字があると効果的（例: 「3つの法則」）
   - 人物の特徴や実績に関連づける

3. キーワード: サムネイルに入れる可能性のあるワード2-3個

【出力形式】必ずこの形式で出力:
MAIN: [メインコピー]
SUB: [サブコピー]
KEYWORDS: [キーワード1], [キーワード2], [キーワード3]

【禁止ワード】以下は使わない:
- 必見、衝撃、驚愕、ヤバい、まじ、神、最強

【注意】
- 日本語で出力
- {person_name}の名前はコピーに含めない（別途表示するため）
- トピック「{topic}」に直接関連する内容にする
"""
        return prompt

    def _parse_response(self, response_text: str, topic: str) -> dict:
        """AIレスポンスをパース"""
        result = {
            "main_copy": "",
            "sub_copy": "",
            "keywords": [],
        }

        lines = response_text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("MAIN:"):
                result["main_copy"] = line.replace("MAIN:", "").strip()
            elif line.startswith("SUB:"):
                result["sub_copy"] = line.replace("SUB:", "").strip()
            elif line.startswith("KEYWORDS:"):
                keywords_str = line.replace("KEYWORDS:", "").strip()
                result["keywords"] = [k.strip() for k in keywords_str.split(",")]

        # パース失敗時は動的生成にフォールバック
        if not result["main_copy"]:
            return self._generate_dynamic_copy("", topic, None)

        return result

    def _generate_dynamic_copy(
        self, person_name: str, topic: str, quote: str | None
    ) -> dict:
        """トピックに基づいて動的にキャッチコピーを生成"""

        # トピックからカテゴリを判定
        category = "default"
        topic_lower = topic.lower()

        for key in self.COPY_PATTERNS.keys():
            if key != "default" and key in topic_lower:
                category = key
                break

        # 追加のキーワードマッチング
        keyword_mapping = {
            "思考": ["考え", "マインド", "発想", "アイデア", "頭"],
            "成功": ["勝", "達成", "実現", "結果"],
            "お金": ["投資", "資産", "富", "財", "経済", "ビジネス"],
            "習慣": ["毎日", "継続", "ルーティン", "日課"],
            "人生": ["生き方", "人生", "運命", "選択"],
            "仕事": ["働", "キャリア", "プロ", "職"],
            "リーダー": ["経営", "組織", "マネジメント", "リーダー", "トップ"],
        }

        if category == "default":
            for cat, keywords in keyword_mapping.items():
                if any(kw in topic_lower for kw in keywords):
                    category = cat
                    break

        # パターンからランダム選択
        patterns = self.COPY_PATTERNS[category]
        selected = random.choice(patterns)

        # サブコピーをトピックでカスタマイズ
        sub_copy = selected["sub"]

        # トピックから短いキーワードを抽出してサブコピーに組み込む
        topic_short = topic[:8] if len(topic) > 8 else topic

        # 名言があればそれを活用
        if quote and len(quote) <= 15:
            sub_copy = quote

        return {
            "main_copy": selected["main"],
            "sub_copy": sub_copy,
            "keywords": [topic_short],
        }
