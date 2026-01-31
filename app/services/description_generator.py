"""
Video description generator for YouTube uploads.
Builds a short hook, summary, and TOC aligned to the actual video duration.
"""

from __future__ import annotations

import math
import re

import google.generativeai as genai

from app.config import settings
from app.models.schemas import VideoScript
from app.utils.logger import logger


class DescriptionGenerator:
    """Generates YouTube video descriptions from script content."""

    def __init__(self):
        """Initialize description generator with AI client."""
        self.gemini_enabled = False
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.gemini_enabled = True

    def generate_description(
        self,
        script: VideoScript,
        person_name: str,
        topic: str,
        video_duration_seconds: float,
        subtitles: list[dict] | None = None,
        dynamic_hashtags: list[str] | None = None,
    ) -> str:
        logger.info("Generating video description")

        opening_hook = self._generate_opening_hook(person_name, topic, script)
        summary = self._generate_summary(person_name, topic, script, video_duration_seconds)
        chapters = self._generate_chapters(script, video_duration_seconds, subtitles)
        narration_info = "■ナレーション\nVOICEVOX：青山龍星"
        hashtags = self._generate_hashtags(person_name, topic, dynamic_hashtags)

        description = (
            f"{opening_hook}\n\n"
            f"{summary}\n\n"
            f"【目次】\n{chapters}\n\n"
            f"{narration_info}\n\n"
            f"【ハッシュタグ】\n{hashtags}"
        )

        logger.debug("Description generated")
        return description

    def _generate_opening_hook(
        self, person_name: str, topic: str, script: VideoScript
    ) -> str:
        """
        AIで動画説明文用の冒頭フックを生成する。
        台本をそのまま使わず、YouTube説明文に適した短いキャッチコピーを生成。
        """
        if not self.gemini_enabled:
            # フォールバック: シンプルなテンプレート
            return f"なぜ{person_name}は成功できたのか？その秘密に迫ります。"

        try:
            # 台本の要点を抽出
            key_points = []
            for section in script.sections[:3]:  # 最初の3セクションから
                if section.title:
                    key_points.append(section.title)

            prompt = f"""YouTube動画の説明文の冒頭に使う、短くてキャッチーなフック文を1つだけ生成してください。

【動画情報】
- 人物: {person_name}
- テーマ: {topic}
- 主な内容: {', '.join(key_points) if key_points else 'この人物の哲学と教訓'}

【条件】
- 2-3文で、合計50-80文字程度
- 視聴者の興味を引く問いかけや気づきを含める
- 台本調ではなく、説明文として自然な文体
- 「この動画では」のような説明的な書き出しは避ける
- 絵文字は使わない

フック文のみを出力してください。"""

            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(prompt)
            hook = response.text.strip()

            # 改行があれば最初の段落だけ使用
            if "\n" in hook:
                hook = hook.split("\n")[0].strip()

            logger.info(f"✅ AIで冒頭フックを生成: {hook[:50]}...")
            return hook

        except Exception as e:
            logger.warning(f"⚠️ AI冒頭フック生成に失敗、フォールバック使用: {e}")
            return f"なぜ{person_name}は成功できたのか？その秘密に迫ります。"

    def _generate_summary(
        self,
        person_name: str,
        topic: str,
        script: VideoScript,
        video_duration_seconds: float,
    ) -> str:
        minutes = max(1, int(math.ceil(video_duration_seconds / 60)))
        return (
            f"{person_name}の「{topic}」をわかりやすく解説します。\n"
            f"{person_name}の哲学や行動から、現代に応用できる実践的な示唆をまとめた約{minutes}分の動画です。"
        )

    def _generate_chapters(
        self,
        script: VideoScript,
        video_duration_seconds: float,
        subtitles: list[dict] | None = None,
    ) -> str:
        """Generate chapter timestamps using actual subtitle timings."""
        if not script.sections:
            return "00:00 導入"

        # subtitles から実際のセクション開始時刻を計算
        if subtitles:
            chapters: list[str] = []
            subtitle_index = 0

            for idx, section in enumerate(script.sections, start=1):
                # このセクションの最初の字幕を探す
                section_start_time = 0.0
                if subtitle_index < len(subtitles):
                    section_start_time = subtitles[subtitle_index].get("start_time", 0.0)

                minutes = int(section_start_time // 60)
                seconds = int(section_start_time % 60)
                title = section.title or f"第{idx}章"
                chapters.append(f"{minutes:02d}:{seconds:02d} {title}")

                # このセクションの字幕数分インデックスを進める
                if section.subtitles:
                    subtitle_index += len(section.subtitles)

            logger.info(f"✅ 実際の字幕タイミングを使用してチャプターを生成しました")
            return "\n".join(chapters)

        # フォールバック: 推定時間で計算（従来の方法）
        logger.warning("⚠️ 字幕データがないため、推定時間でチャプターを生成します")
        total_estimated = sum(section.duration_seconds for section in script.sections)
        scale = (
            max(video_duration_seconds, 1.0) / total_estimated
            if total_estimated > 0
            else max(video_duration_seconds, 1.0) / len(script.sections)
        )

        chapters: list[str] = []
        current_time = 0.0
        for idx, section in enumerate(script.sections, start=1):
            minutes = int(current_time // 60)
            seconds = int(current_time % 60)
            title = section.title or f"第{idx}章"
            chapters.append(f"{minutes:02d}:{seconds:02d} {title}")
            current_time += section.duration_seconds * scale

        return "\n".join(chapters)

    def _generate_hashtags(
        self,
        person_name: str,
        topic: str,
        dynamic_hashtags: list[str] | None = None,
    ) -> str:
        """
        ハッシュタグを生成。動的ハッシュタグが提供されていればそちらを優先使用。

        Args:
            person_name: 人物名
            topic: テーマ
            dynamic_hashtags: 戦略エンジンが生成した動的ハッシュタグ
        """
        if dynamic_hashtags:
            return " ".join(dynamic_hashtags)

        tags = [
            f"#{person_name}",
            f"#{topic}",
            "#偉人の言葉",
            "#教養",
            "#ビジネス",
            "#自己啓発",
            "#人生哲学",
        ]
        return " ".join(tags)

    def extract_catchphrase(self, script: VideoScript) -> str:
        """
        Extract a short catchphrase from the first section for thumbnails.
        """
        if not script.sections:
            return "未来を変えるヒント"

        narration = script.sections[0].narration
        sentences = [s.strip() for s in re.split(r"(?<=。)", narration) if s.strip()]
        for sentence in sentences:
            if 10 <= len(sentence) <= 30:
                return sentence
        return sentences[0] if sentences else narration[:20]
