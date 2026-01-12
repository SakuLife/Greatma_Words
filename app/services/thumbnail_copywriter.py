"""
サムネイル用キャッチコピー生成サービス

台本や人物情報から、YouTubeサムネイルに最適な
クリックを誘発するキャッチコピーを生成する
"""

import google.generativeai as genai

from app.config import settings
from app.utils.logger import logger


class ThumbnailCopywriter:
    """YouTubeサムネイル用のキャッチコピーを生成"""

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
        if not self.model:
            logger.warning("Gemini not available, using fallback copy")
            return self._fallback_copy(person_name, topic)

        prompt = self._build_prompt(person_name, topic, script_summary, quote)

        try:
            response = self.model.generate_content(prompt)
            result = self._parse_response(response.text)
            logger.info(f"サムネイルコピー生成: {result['main_copy']}")
            return result
        except Exception as e:
            logger.error(f"キャッチコピー生成エラー: {e}")
            return self._fallback_copy(person_name, topic)

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
1. メインコピー: 8文字以内の強烈なインパクトワード
   - 例: 「知らないと損」「今すぐ真似しろ」「衝撃の真実」「成功者の習慣」
   - 視聴者の感情を刺激する言葉
   - 疑問形や命令形も効果的

2. サブコピー: 15文字以内の補足
   - メインを補強する具体的な内容
   - 数字を入れると効果的（例: 「3つの法則」「90%が知らない」）

3. キーワード: サムネイルに入れる可能性のあるワード2-3個

【出力形式】必ずこの形式で出力:
MAIN: [メインコピー]
SUB: [サブコピー]
KEYWORDS: [キーワード1], [キーワード2], [キーワード3]

【注意】
- 日本語で出力
- 誇張しすぎない（信頼性を損なわない程度）
- {person_name}の名前はコピーに含めない（別途表示するため）
"""
        return prompt

    def _parse_response(self, response_text: str) -> dict:
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

        # バリデーション
        if not result["main_copy"]:
            result["main_copy"] = "必見"
        if not result["sub_copy"]:
            result["sub_copy"] = ""

        return result

    def _fallback_copy(self, person_name: str, topic: str) -> dict:
        """フォールバック用のデフォルトコピー"""
        # トピックから簡易的にコピーを生成
        fallback_copies = [
            {"main": "知らないと損", "sub": "成功者の思考法"},
            {"main": "衝撃の真実", "sub": "誰も教えない秘密"},
            {"main": "今すぐ真似しろ", "sub": "億万長者の習慣"},
            {"main": "9割が知らない", "sub": "お金持ちの法則"},
        ]

        import random
        selected = random.choice(fallback_copies)

        return {
            "main_copy": selected["main"],
            "sub_copy": selected["sub"],
            "keywords": [topic[:10] if len(topic) > 10 else topic],
        }
