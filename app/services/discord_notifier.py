"""
Discord webhook notification service.
Sends notifications to Discord channel about video generation progress.
"""

import json
from datetime import datetime
from typing import Any

import aiohttp

from app.config import settings
from app.utils.logger import logger


class DiscordNotifier:
    """Sends notifications to Discord via webhook."""

    def __init__(self, webhook_url: str | None = None):
        """
        Initialize Discord notifier.

        Args:
            webhook_url: Discord webhook URL (if not provided, uses settings)
        """
        self.webhook_url = webhook_url or settings.discord_webhook_url

    async def send_message(
        self,
        content: str,
        title: str | None = None,
        color: int | None = None,
        fields: list[dict[str, Any]] | None = None,
    ) -> bool:
        """
        Send a message to Discord.

        Args:
            content: Message content
            title: Embed title (optional)
            color: Embed color in decimal (optional)
            fields: List of embed fields (optional)

        Returns:
            True if successful, False otherwise
        """
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured, skipping notification")
            return False

        try:
            payload: dict[str, Any] = {}

            if title or color or fields:
                # Use embed for rich formatting
                embed: dict[str, Any] = {
                    "description": content,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                if title:
                    embed["title"] = title

                if color:
                    embed["color"] = color

                if fields:
                    embed["fields"] = fields

                payload["embeds"] = [embed]
            else:
                # Simple text message
                payload["content"] = content

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status == 204:
                        logger.debug(f"Discord notification sent: {title or content[:50]}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Discord webhook failed: {response.status} - {error_text}"
                        )
                        return False

        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False

    async def notify_video_started(
        self, person_name: str, theme: str, duration: int
    ) -> bool:
        """
        Notify that video generation has started.

        Args:
            person_name: Name of the person/figure
            theme: Video theme
            duration: Target video duration in minutes

        Returns:
            True if notification sent successfully
        """
        return await self.send_message(
            content=f"**{person_name}** の動画生成を開始しました\n"
            f"テーマ: {theme}\n"
            f"目標時間: {duration}分",
            title="🎬 動画生成開始",
            color=0x3498DB,  # Blue
        )

    async def notify_script_completed(
        self, person_name: str, word_count: int
    ) -> bool:
        """
        Notify that script generation is complete.

        Args:
            person_name: Name of the person/figure
            word_count: Number of characters in script

        Returns:
            True if notification sent successfully
        """
        return await self.send_message(
            content=f"**{person_name}** の台本生成が完了しました\n文字数: {word_count}文字",
            title="📝 台本生成完了",
            color=0x2ECC71,  # Green
        )

    async def notify_image_completed(self, person_name: str, count: int) -> bool:
        """
        Notify that image generation is complete.

        Args:
            person_name: Name of the person/figure
            count: Number of images generated

        Returns:
            True if notification sent successfully
        """
        return await self.send_message(
            content=f"**{person_name}** の画像生成が完了しました\n生成枚数: {count}枚",
            title="🎨 画像生成完了",
            color=0x9B59B6,  # Purple
        )

    async def notify_voice_completed(
        self, person_name: str, duration: float
    ) -> bool:
        """
        Notify that voice synthesis is complete.

        Args:
            person_name: Name of the person/figure
            duration: Audio duration in seconds

        Returns:
            True if notification sent successfully
        """
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        return await self.send_message(
            content=f"**{person_name}** の音声合成が完了しました\n"
            f"音声時間: {minutes}分{seconds}秒",
            title="🎤 音声合成完了",
            color=0xE67E22,  # Orange
        )

    async def notify_video_completed(
        self,
        person_name: str,
        theme: str,
        output_path: str,
        duration: float,
        youtube_url: str | None = None,
        drive_url: str | None = None,
    ) -> bool:
        """
        Notify that video creation is complete.

        Args:
            person_name: Name of the person/figure
            theme: Video theme
            output_path: Path to output video file
            duration: Video duration in seconds
            youtube_url: YouTube video URL (optional)
            drive_url: Google Drive file URL (optional)

        Returns:
            True if notification sent successfully
        """
        minutes = int(duration // 60)
        seconds = int(duration % 60)

        fields = [
            {"name": "人物", "value": person_name, "inline": True},
            {"name": "テーマ", "value": theme, "inline": True},
            {"name": "動画時間", "value": f"{minutes}分{seconds}秒", "inline": True},
        ]

        content_lines = ["✅ 動画生成が完了しました"]

        if youtube_url:
            content_lines.append(f"🎥 [YouTube で視聴]({youtube_url})")
            fields.append({"name": "YouTube", "value": youtube_url, "inline": False})

        if drive_url:
            content_lines.append(f"☁️ [Google Drive で確認]({drive_url})")
            fields.append({"name": "Google Drive", "value": drive_url, "inline": False})

        return await self.send_message(
            content="\n".join(content_lines),
            title="🎉 動画生成完了",
            color=0x2ECC71,  # Green
            fields=fields,
        )

    async def notify_error(
        self, error_message: str, context: str | None = None
    ) -> bool:
        """
        Notify about an error.

        Args:
            error_message: Error message
            context: Additional context (optional)

        Returns:
            True if notification sent successfully
        """
        content = f"❌ エラーが発生しました\n```\n{error_message}\n```"
        if context:
            content += f"\n\n**コンテキスト**: {context}"

        return await self.send_message(
            content=content,
            title="🚨 エラー通知",
            color=0xE74C3C,  # Red
        )

    async def notify_task_progress(
        self, task_name: str, progress: int, total: int, details: str | None = None
    ) -> bool:
        """
        Notify about task progress.

        Args:
            task_name: Name of the task
            progress: Current progress count
            total: Total count
            details: Additional details (optional)

        Returns:
            True if notification sent successfully
        """
        percentage = int((progress / total) * 100) if total > 0 else 0
        progress_bar = self._create_progress_bar(percentage)

        content = f"**{task_name}**\n{progress_bar} {percentage}% ({progress}/{total})"
        if details:
            content += f"\n{details}"

        return await self.send_message(
            content=content,
            title="⏳ 進捗状況",
            color=0xF39C12,  # Yellow
        )

    @staticmethod
    def _create_progress_bar(percentage: int, length: int = 10) -> str:
        """
        Create a visual progress bar.

        Args:
            percentage: Percentage complete (0-100)
            length: Length of progress bar

        Returns:
            Progress bar string
        """
        filled = int((percentage / 100) * length)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}]"

    async def notify_youtube_uploaded(
        self, video_id: str, title: str, privacy_status: str
    ) -> bool:
        """
        Notify that video was uploaded to YouTube.

        Args:
            video_id: YouTube video ID
            title: Video title
            privacy_status: Privacy status (public/private/unlisted)

        Returns:
            True if notification sent successfully
        """
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"

        privacy_emoji = {
            "public": "🌍",
            "private": "🔒",
            "unlisted": "🔗",
        }.get(privacy_status, "❓")

        return await self.send_message(
            content=f"{privacy_emoji} YouTubeへのアップロードが完了しました\n\n"
            f"**タイトル**: {title}\n"
            f"**公開設定**: {privacy_status}\n"
            f"**URL**: {youtube_url}",
            title="📺 YouTube アップロード完了",
            color=0xFF0000,  # YouTube Red
        )

    async def notify_drive_uploaded(
        self, file_name: str, drive_url: str, file_size_mb: float
    ) -> bool:
        """
        Notify that file was uploaded to Google Drive.

        Args:
            file_name: Name of the uploaded file
            drive_url: Google Drive file URL
            file_size_mb: File size in MB

        Returns:
            True if notification sent successfully
        """
        return await self.send_message(
            content=f"☁️ Google Driveへのアップロードが完了しました\n\n"
            f"**ファイル名**: {file_name}\n"
            f"**サイズ**: {file_size_mb:.1f} MB\n"
            f"**URL**: {drive_url}",
            title="💾 Google Drive アップロード完了",
            color=0x4285F4,  # Google Blue
        )
