"""
Video description generator for YouTube uploads.
Builds a short hook, summary, and TOC aligned to the actual video duration.
"""

from __future__ import annotations

import math
import re

from app.models.schemas import VideoScript
from app.utils.logger import logger


class DescriptionGenerator:
    """Generates YouTube video descriptions from script content."""

    def generate_description(
        self,
        script: VideoScript,
        person_name: str,
        topic: str,
        video_duration_seconds: float,
        subtitles: list[dict] | None = None,
    ) -> str:
        logger.info("Generating video description")

        opening_hook = self._extract_opening_hook(script)
        summary = self._generate_summary(person_name, topic, script, video_duration_seconds)
        chapters = self._generate_chapters(script, video_duration_seconds, subtitles)
        narration_info = "■ナレーション\nVOICEVOX：青山龍星"
        hashtags = self._generate_hashtags(person_name, topic)

        description = (
            f"{opening_hook}\n\n"
            f"{summary}\n\n"
            f"【目次】\n{chapters}\n\n"
            f"{narration_info}\n\n"
            f"【ハッシュタグ】\n{hashtags}"
        )

        logger.debug("Description generated")
        return description

    def _extract_opening_hook(self, script: VideoScript) -> str:
        """Grab the first 1-3 sentences from the opening section."""
        if not script.sections:
            return "この動画では、偉人の思想から現代に活かせるヒントを解説します。"

        narration = script.sections[0].narration
        sentences = [s.strip() for s in re.split(r"(?<=。)", narration) if s.strip()]
        hook = " ".join(sentences[:3]) if sentences else narration.strip()
        return hook

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

    def _generate_hashtags(self, person_name: str, topic: str) -> str:
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
