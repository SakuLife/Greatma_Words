"""
Person information fetcher using AI.
Dynamically fetches person titles, quotes, and background information.
"""

import json

import google.generativeai as genai

from app.config import settings
from app.utils.logger import logger


class PersonInfoFetcher:
    """Fetches person information using AI."""

    def __init__(self):
        """Initialize person info fetcher."""
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.model = genai.GenerativeModel(settings.default_llm_model)
        else:
            self.model = None
            logger.warning("Gemini API key not configured")

    async def get_person_info(self, person_name: str) -> dict:
        """
        Get comprehensive information about a person.

        Args:
            person_name: Name of the person

        Returns:
            Dictionary with person information
        """
        if not self.model:
            logger.warning("AI model not available, using fallback")
            return self._get_fallback_info(person_name)

        prompt = f"""
以下の人物について、正確な情報を提供してください：

人物名: {person_name}

以下のJSON形式で回答してください：

{{
    "person_name": "{person_name}",
    "title": "肩書（最も有名な肩書を1つ、30文字以内）",
    "famous_quote": "代表的な名言（30文字以内）",
    "birth_year": "生年（西暦、不明な場合はnull）",
    "death_year": "没年（西暦、存命中または不明な場合はnull）",
    "field": "主な活動分野（例: ビジネス、政治、科学、哲学など）",
    "achievements": [
        "主な業績1",
        "主な業績2",
        "主な業績3"
    ],
    "keywords": [
        "関連キーワード1",
        "関連キーワード2",
        "関連キーワード3"
    ],
    "short_bio": "2-3文の簡潔な人物紹介"
}}

**重要:** JSON形式のみで回答してください。説明文は不要です。
"""

        try:
            logger.info(f"Fetching person info for: {person_name}")

            response = self.model.generate_content(prompt)
            response_text = response.text.strip()

            # JSONブロックを抽出（```json ... ``` で囲まれている場合）
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            # JSONをパース
            person_info = json.loads(response_text)

            logger.info(f"Person info retrieved: {person_info['title']}")
            return person_info

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Response text: {response_text}")
            return self._get_fallback_info(person_name)
        except Exception as e:
            logger.error(f"Failed to fetch person info: {e}")
            return self._get_fallback_info(person_name)

    def _get_fallback_info(self, person_name: str) -> dict:
        """Get fallback info when AI is not available."""
        # 既存のperson_titlesを参照
        from app.utils.person_titles import PERSON_TITLES, PERSON_QUOTES

        title = PERSON_TITLES.get(person_name, "偉人")
        quote = PERSON_QUOTES.get(person_name, "知識は力なり")

        return {
            "person_name": person_name,
            "title": title,
            "famous_quote": quote,
            "birth_year": None,
            "death_year": None,
            "field": "不明",
            "achievements": [],
            "keywords": [],
            "short_bio": f"{person_name}は歴史上の重要な人物です。",
        }

    async def suggest_next_person(
        self, analysis_context: str, exclude_persons: list[str] | None = None
    ) -> dict:
        """
        Suggest next person to feature based on channel analysis.

        Args:
            analysis_context: Channel analysis data
            exclude_persons: List of persons to exclude from suggestions

        Returns:
            Dictionary with suggested person and reasoning
        """
        if not self.model:
            logger.warning("AI model not available")
            return {
                "person_name": "ウォーレン・バフェット",
                "reason": "投資の神様として知られる人物",
            }

        exclude_list = exclude_persons or []
        exclude_text = (
            f"\n\n除外する人物: {', '.join(exclude_list)}"
            if exclude_list
            else ""
        )

        prompt = f"""
以下のYouTubeチャンネルの分析結果に基づいて、次に取り上げるべき人物を提案してください。

{analysis_context}
{exclude_text}

以下のJSON形式で回答してください：

{{
    "person_name": "提案する人物名（日本語）",
    "english_name": "英語名（該当する場合）",
    "title": "肩書（30文字以内）",
    "suggested_theme": "動画で扱うべきテーマ（30文字以内）",
    "reason": "この人物を選んだ理由（分析データに基づいて、100文字程度）",
    "expected_engagement": "予想されるエンゲージメント（高/中/低）",
    "keywords": ["関連キーワード1", "関連キーワード2", "関連キーワード3"]
}}

**条件:**
1. 過去の動画のパフォーマンスデータを考慮すること
2. 視聴者の興味に合致する人物を選ぶこと
3. 除外リストに含まれていない人物を選ぶこと
4. ビジネス・経営・自己啓発分野の著名人が望ましい

**重要:** JSON形式のみで回答してください。説明文は不要です。
"""

        try:
            logger.info("Requesting person suggestion from AI...")

            response = self.model.generate_content(prompt)
            response_text = response.text.strip()

            # JSONブロックを抽出
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            # JSONをパース
            suggestion = json.loads(response_text)

            logger.info(f"Person suggested: {suggestion['person_name']} - {suggestion['suggested_theme']}")
            return suggestion

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Response text: {response_text}")
            return {
                "person_name": "ピーター・ドラッカー",
                "english_name": "Peter Drucker",
                "title": "経営学の父",
                "suggested_theme": "マネジメントの本質",
                "reason": "経営学の権威として知られ、ビジネスパーソンに人気が高い",
                "expected_engagement": "高",
                "keywords": ["マネジメント", "経営戦略", "組織論"],
            }
        except Exception as e:
            logger.error(f"Failed to get person suggestion: {e}")
            return {
                "person_name": "ピーター・ドラッカー",
                "english_name": "Peter Drucker",
                "title": "経営学の父",
                "suggested_theme": "マネジメントの本質",
                "reason": "経営学の権威として知られ、ビジネスパーソンに人気が高い",
                "expected_engagement": "高",
                "keywords": ["マネジメント", "経営戦略", "組織論"],
            }
