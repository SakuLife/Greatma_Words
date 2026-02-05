"""
Person information fetcher using AI.
Dynamically fetches person titles, quotes, and background information.
"""

import json

import google.generativeai as genai
import requests

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
    "short_bio": "2-3文の簡潔な人物紹介",
    "appearance": "英語で外見描写（AI画像生成プロンプト用）"
}}

**重要:**
- JSON形式のみで回答してください。説明文は不要です。
- appearanceは必ず英語で記述してください。以下の情報を含めてください：
  - 年齢（例: elderly man in his 70s, middle-aged man in his 50s）
  - 髪型・髪色（例: white hair, bald, short gray hair）
  - 髭の有無（例: white beard, mustache, clean-shaven）
  - 眼鏡の有無（例: round glasses, thick glasses）
  - 服装（例: traditional Japanese clothing, dark suit, black turtleneck）
  - 時代を反映した特徴（例: Meiji-era Japanese businessman, Renaissance-era Italian）
  - 表情・雰囲気（例: wise expression, dignified appearance）
- 実在の人物の写真や肖像画に基づいた正確な外見描写をしてください
- 50-100語程度で具体的に記述してください
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
            "appearance": "distinguished person, professional appearance, confident expression",
        }

    async def get_person_image_urls(self, person_name: str, max_images: int = 2) -> list[str]:
        """
        Wikipedia/Wikimedia Commonsから人物の画像URLを取得する。

        Args:
            person_name: 人物名
            max_images: 取得する画像の最大数

        Returns:
            画像URLのリスト
        """
        image_urls = []

        # 日本語Wikipediaと英語Wikipediaの両方を試す
        wiki_configs = [
            {"lang": "ja", "name": person_name},
            {"lang": "en", "name": self._get_english_name(person_name)},
        ]

        for config in wiki_configs:
            if len(image_urls) >= max_images:
                break

            urls = self._fetch_wikipedia_images(config["name"], config["lang"])
            for url in urls:
                if url not in image_urls:
                    image_urls.append(url)
                    if len(image_urls) >= max_images:
                        break

        if image_urls:
            logger.info(f"[OK] {person_name}の参照画像を{len(image_urls)}枚取得しました")
        else:
            logger.warning(f"[WARN] {person_name}の参照画像が見つかりませんでした")

        return image_urls

    def _fetch_wikipedia_images(self, person_name: str, lang: str = "ja") -> list[str]:
        """
        Wikipedia APIから人物の画像URLを取得する。

        Args:
            person_name: 人物名
            lang: 言語コード（ja, en）

        Returns:
            画像URLのリスト
        """
        image_urls = []

        # Wikipedia APIはUser-Agentを要求
        headers = {
            "User-Agent": "GreatmanWordsBot/1.0 (https://github.com/greatman-words; contact@example.com)"
        }

        try:
            # Step 1: ページ情報を取得（メイン画像）
            api_url = f"https://{lang}.wikipedia.org/w/api.php"

            # ページのメイン画像を取得
            params = {
                "action": "query",
                "titles": person_name,
                "prop": "pageimages|images",
                "pithumbsize": 800,  # サムネイルサイズ
                "format": "json",
            }

            response = requests.get(api_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            pages = data.get("query", {}).get("pages", {})
            for page_id, page_data in pages.items():
                if page_id == "-1":
                    continue  # ページが見つからない

                # メインサムネイル画像
                thumbnail = page_data.get("thumbnail", {}).get("source")
                if thumbnail:
                    # サムネイルURLを高解像度版に変換
                    high_res_url = self._get_high_res_url(thumbnail)
                    if high_res_url:
                        image_urls.append(high_res_url)
                        logger.debug(f"Wikipedia画像取得: {high_res_url}")

                # ページ内の画像リストから追加取得
                images = page_data.get("images", [])
                for img in images[:5]:  # 最初の5つだけチェック
                    img_title = img.get("title", "")
                    # 人物写真っぽいファイル名をフィルタリング
                    if self._is_person_image(img_title):
                        img_url = self._get_image_url(img_title, lang)
                        if img_url and img_url not in image_urls:
                            image_urls.append(img_url)

        except Exception as e:
            logger.debug(f"Wikipedia画像取得エラー ({lang}): {e}")

        return image_urls

    def _get_high_res_url(self, thumbnail_url: str) -> str | None:
        """サムネイルURLを高解像度版に変換する。"""
        try:
            # Wikipediaのサムネイル形式: /thumb/.../XXXpx-filename.ext
            # 高解像度版: /commons/ or /wikipedia/ から直接取得
            if "/thumb/" in thumbnail_url:
                # サムネイルサイズを大きくする
                import re
                high_res = re.sub(r"/\d+px-", "/800px-", thumbnail_url)
                return high_res
            return thumbnail_url
        except Exception:
            return thumbnail_url

    def _is_person_image(self, filename: str) -> bool:
        """ファイル名から人物画像かどうかを判定する。"""
        filename_lower = filename.lower()
        # 除外するパターン
        exclude_patterns = [
            "icon", "logo", "flag", "map", "chart", "graph",
            "signature", "autograph", "seal", "coat_of_arms",
            ".svg", "commons-logo", "wiki"
        ]
        for pattern in exclude_patterns:
            if pattern in filename_lower:
                return False
        # 含めるパターン
        include_patterns = [".jpg", ".jpeg", ".png", "portrait", "photo"]
        for pattern in include_patterns:
            if pattern in filename_lower:
                return True
        return False

    def _get_image_url(self, image_title: str, lang: str = "ja") -> str | None:
        """画像タイトルから実際のURLを取得する。"""
        headers = {
            "User-Agent": "GreatmanWordsBot/1.0 (https://github.com/greatman-words; contact@example.com)"
        }
        try:
            api_url = f"https://{lang}.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "titles": image_title,
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 800,
                "format": "json",
            }
            response = requests.get(api_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            pages = data.get("query", {}).get("pages", {})
            for page_data in pages.values():
                imageinfo = page_data.get("imageinfo", [])
                if imageinfo:
                    return imageinfo[0].get("thumburl") or imageinfo[0].get("url")
        except Exception as e:
            logger.debug(f"画像URL取得エラー: {e}")
        return None

    def _get_english_name(self, japanese_name: str) -> str:
        """日本語名から英語名を推測する（簡易版）。"""
        # よくある人物の英語名マッピング
        name_mapping = {
            "ウォーレン・バフェット": "Warren Buffett",
            "スティーブ・ジョブズ": "Steve Jobs",
            "イーロン・マスク": "Elon Musk",
            "ビル・ゲイツ": "Bill Gates",
            "ジェフ・ベゾス": "Jeff Bezos",
            "孫正義": "Masayoshi Son",
            "松下幸之助": "Konosuke Matsushita",
            "本田宗一郎": "Soichiro Honda",
            "稲盛和夫": "Kazuo Inamori",
            "渋沢栄一": "Eiichi Shibusawa",
            "アルベルト・アインシュタイン": "Albert Einstein",
            "レオナルド・ダ・ヴィンチ": "Leonardo da Vinci",
            "ナポレオン・ボナパルト": "Napoleon Bonaparte",
            "マハトマ・ガンジー": "Mahatma Gandhi",
            "ネルソン・マンデラ": "Nelson Mandela",
            "ピーター・ドラッカー": "Peter Drucker",
            "マイケル・ポーター": "Michael Porter",
        }
        return name_mapping.get(japanese_name, japanese_name)

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
