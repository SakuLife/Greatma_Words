"""
Integrated video production workflow.
Coordinates all services: script, images, voice, video, YouTube, Drive, Sheets, Discord.
"""

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.models.schemas import VideoMetadata
from app.services.discord_notifier import DiscordNotifier
from app.services.drive_manager import DriveManager
from app.services.image_generator import ImageGenerator
from app.services.script_generator import ScriptGenerator
from app.services.sheets_manager import SheetsManager
from app.services.thumbnail_generator import ThumbnailGenerator
from app.services.video_creator import VideoCreator
from app.services.voice_synthesizer import VoiceSynthesizer
from app.services.youtube_uploader import YouTubeUploader
from app.services.comment_generator import CommentGenerator
from app.utils.file_manager import FileManager
from app.utils.logger import logger


def calculate_next_publish_time(target_hour: int = 21) -> datetime:
    """
    Calculate next publish time at specified hour in JST (UTC+9).

    Args:
        target_hour: Target hour in JST (0-23). Default is 21 (9 PM JST).

    Returns:
        Next publish datetime in UTC (for YouTube API).

    Example:
        If current time is 2025-12-28 10:00 JST:
        - Returns 2025-12-28 21:00 JST = 2025-12-28 12:00 UTC (same day)

        If current time is 2025-12-28 19:00 JST:
        - Returns 2025-12-28 21:00 JST = 2025-12-28 12:00 UTC (same day)
    """
    # JST is UTC+9
    JST = timezone(timedelta(hours=9))

    # Get current time in JST
    now_jst = datetime.now(JST)

    # Calculate target time today
    target_time_today = now_jst.replace(
        hour=target_hour, minute=0, second=0, microsecond=0
    )

    # If target time has passed, schedule for tomorrow
    if now_jst >= target_time_today:
        target_time = target_time_today + timedelta(days=1)
    else:
        target_time = target_time_today

    # Convert to UTC for YouTube API (YouTube expects UTC)
    target_time_utc = target_time.astimezone(timezone.utc)

    logger.info(
        f"Scheduled publish time: {target_time.strftime('%Y-%m-%d %H:%M:%S %Z')} "
        f"= {target_time_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    )

    return target_time_utc


class VideoWorkflow:
    """Orchestrates the entire video production workflow with integrations."""

    def __init__(
        self,
        enable_youtube: bool = True,
        enable_drive: bool = True,
        enable_sheets: bool = True,
        enable_discord: bool = True,
    ):
        """
        Initialize video workflow.

        Args:
            enable_youtube: Enable YouTube upload
            enable_drive: Enable Google Drive upload
            enable_sheets: Enable Google Sheets logging
            enable_discord: Enable Discord notifications
        """
        self.enable_youtube = enable_youtube
        self.enable_drive = enable_drive
        self.enable_sheets = enable_sheets
        self.enable_discord = enable_discord

        # Initialize services
        self.file_manager = FileManager()
        self.script_generator = ScriptGenerator()
        self.image_generator = ImageGenerator()
        self.voice_synthesizer = VoiceSynthesizer()
        self.video_creator = VideoCreator()
        self.thumbnail_generator = ThumbnailGenerator()

        self.comment_generator = CommentGenerator()

        # Initialize optional services
        self.youtube_uploader = YouTubeUploader() if enable_youtube else None
        self.drive_manager = DriveManager() if enable_drive else None
        self.sheets_manager = SheetsManager() if enable_sheets else None
        self.discord_notifier = DiscordNotifier() if enable_discord else None

    async def create_video_complete(
        self,
        person_name: str,
        theme: str,
        target_duration: int = 15,
        upload_to_youtube: bool = True,
        upload_to_drive: bool = True,
        privacy_status: str = "private",
        hook_strategy: str = "",
        structure_pattern: str = "",
    ) -> dict[str, Any]:
        """
        Create a complete video from start to finish with all integrations.

        Args:
            person_name: Name of the person/figure
            theme: Video theme
            target_duration: Target video duration in minutes
            upload_to_youtube: Whether to upload to YouTube
            upload_to_drive: Whether to upload to Google Drive
            privacy_status: YouTube privacy status (public/private/unlisted)
            hook_strategy: 使用したフック戦略名（スプシ記録用）
            structure_pattern: 使用した構成パターン名（スプシ記録用）

        Returns:
            Dictionary with results including URLs and metadata
        """
        start_time = time.time()

        logger.info(f"Starting complete video workflow: {person_name} - {theme}")

        # Send start notification
        if self.discord_notifier:
            await self.discord_notifier.notify_video_started(
                person_name, theme, target_duration
            )

        try:
            # Step 1: Create project structure
            project = self.file_manager.create_project(theme, person_name)
            project_dir = project.project_dir

            # Step 2: Generate script
            logger.info("Step 1/6: Generating script...")
            if self.discord_notifier:
                await self.discord_notifier.notify_task_progress(
                    "動画生成", 1, 6, "台本生成中..."
                )

            script = await self.script_generator.generate_script(
                topic=theme,
                person_name=person_name,
                duration_minutes=target_duration,
            )

            # Save script to file
            import json

            script_file = project_dir / "script.json"
            with open(script_file, "w", encoding="utf-8") as f:
                json.dump(script.model_dump(), f, indent=2, ensure_ascii=False)

            # Calculate word count
            word_count = sum(len(section.narration) for section in script.sections)

            if self.discord_notifier:
                await self.discord_notifier.notify_script_completed(
                    person_name, word_count
                )

            # Step 3: Skip image generation for now (TODO: implement later)
            logger.info("Step 2/6: Skipping image generation...")
            if self.discord_notifier:
                await self.discord_notifier.notify_task_progress(
                    "動画生成", 2, 6, "画像生成をスキップ"
                )

            image_count = 0
            logger.info("Image generation skipped - will use default images")

            # Step 4: Generate voice
            logger.info("Step 3/6: Generating voice...")
            if self.discord_notifier:
                await self.discord_notifier.notify_task_progress(
                    "動画生成", 3, 6, "音声合成中..."
                )

            audio_file = await self.voice_synthesizer.synthesize_from_script(
                script_file, project_dir / "audio" / "narration.wav"
            )

            # Get audio duration
            from pydub import AudioSegment

            audio = AudioSegment.from_wav(str(audio_file))
            audio_duration = len(audio) / 1000.0  # Convert to seconds

            if self.discord_notifier:
                await self.discord_notifier.notify_voice_completed(
                    person_name, audio_duration
                )

            # Step 5: Create video
            logger.info("Step 4/6: Creating video...")
            if self.discord_notifier:
                await self.discord_notifier.notify_task_progress(
                    "動画生成", 4, 6, "動画編集中..."
                )

            video_file = await self.video_creator.create_video_from_script(
                script_file=script_file,
                audio_file=audio_file,
                output_file=project_dir / "output" / f"{person_name}_{theme}.mp4",
            )

            # Step 6: Generate thumbnail
            logger.info("Step 5/6: Generating thumbnail...")
            if self.discord_notifier:
                await self.discord_notifier.notify_task_progress(
                    "動画生成", 5, 6, "サムネイル生成中..."
                )

            if not settings.skip_thumbnail_generation:
                try:
                    thumbnail_file = await self.thumbnail_generator.generate_thumbnail(
                        person_name=person_name,
                        theme=theme,
                        output_path=project_dir / "output" / "thumbnail.jpg",
                    )
                except Exception as e:
                    logger.warning(
                        f"サムネイル生成失敗（スキップして続行）: {e}"
                    )
                    thumbnail_file = None
            else:
                logger.info("Skipping thumbnail generation")
                thumbnail_file = None

            # Step 7: Upload to YouTube (optional)
            logger.info("Step 6/6: Uploading...")
            youtube_url = None
            video_id = None
            auto_comment_status = ""
            auto_comment_text = ""

            if upload_to_youtube and self.youtube_uploader and self.enable_youtube:
                if self.discord_notifier:
                    await self.discord_notifier.notify_task_progress(
                        "動画生成", 6, 6, "YouTubeにアップロード中..."
                    )

                # Calculate scheduled publish time (next 21:00 JST)
                publish_time = calculate_next_publish_time(target_hour=21)

                metadata = VideoMetadata(
                    title=f"{person_name} - {theme}",
                    description=f"{person_name}の{theme}について解説した動画です。\n\n"
                    f"動画時間: {int(audio_duration // 60)}分{int(audio_duration % 60)}秒\n\n"
                    f"#教養 #{person_name} #ビジネス",
                    tags=[person_name, theme, "教養", "ビジネス", "偉人"],
                    category_id=settings.youtube_default_category,
                    privacy_status=privacy_status,
                    publish_at=publish_time,  # Schedule for next 21:00 JST
                )

                video_id = await self.youtube_uploader.upload_video(
                    video_file, metadata
                )
                youtube_url = f"https://www.youtube.com/watch?v={video_id}"

                # Set thumbnail if generated
                if thumbnail_file and thumbnail_file.exists():
                    await self.youtube_uploader.set_thumbnail(video_id, thumbnail_file)

                # 自動コメント投稿（台本のCTAに対するお手本コメント）
                if settings.youtube_auto_comment:
                    try:
                        import asyncio
                        await asyncio.sleep(10)
                        auto_comment_text = await self.comment_generator.generate_comment(
                            person_name=person_name,
                            topic=theme,
                            script_sections=script.sections if script else None,
                        )
                        comment_id, auto_comment_status = await self.youtube_uploader.post_comment(
                            video_id, auto_comment_text
                        )
                        if comment_id:
                            logger.info(f"Auto-comment posted: {comment_id}")
                        elif auto_comment_status == "コメント無効":
                            # 予約投稿（private）動画はコメント無効 → 保留にして公開後にリトライ
                            auto_comment_status = "保留"
                            logger.info(
                                "コメント保留: 動画公開後にリトライが必要です"
                            )
                    except Exception as e:
                        auto_comment_status = "失敗"
                        logger.warning(f"Auto-comment failed (non-critical): {e}", exc_info=True)

                if self.discord_notifier:
                    await self.discord_notifier.notify_youtube_uploaded(
                        video_id, metadata.title, privacy_status
                    )

            # Step 8: Upload to Google Drive (optional)
            drive_url = None
            if upload_to_drive and self.drive_manager and self.enable_drive:
                file_info = await self.drive_manager.upload_file(
                    video_file,
                    file_name=f"{person_name}_{theme}.mp4",
                )
                drive_url = file_info["url"]
                file_size_mb = file_info["size"] / (1024 * 1024)

                if self.discord_notifier:
                    await self.discord_notifier.notify_drive_uploaded(
                        file_info["name"], drive_url, file_size_mb
                    )

            # Step 9: Log to Google Sheets (optional)
            if self.sheets_manager and self.enable_sheets:
                generation_time = time.time() - start_time

                # 台本から冒頭テキストとアクションプランを抽出
                opening_text = ""
                action_plan = ""
                if script and script.sections:
                    # 冒頭テキスト: 最初のセクションのnarration先頭
                    opening_text = script.sections[0].narration[:200] if script.sections[0].narration else ""
                    # アクションプラン: 「応用」「アクション」「実践」を含むセクション
                    for section in script.sections:
                        if any(kw in section.title for kw in ["応用", "アクション", "実践"]):
                            action_plan = section.narration[:200] if section.narration else ""
                            break

                await self.sheets_manager.log_video_production(
                    person_name=person_name,
                    theme=theme,
                    video_duration=audio_duration,
                    generation_time=generation_time,
                    youtube_url=youtube_url,
                    drive_url=drive_url,
                    project_path=str(project_dir),
                    auto_comment_status=auto_comment_status if upload_to_youtube else "",
                    auto_comment_text=auto_comment_text if upload_to_youtube else "",
                    opening_text=opening_text,
                    action_plan=action_plan,
                    hook_strategy=hook_strategy,
                    structure_pattern=structure_pattern,
                )

            # Step 10: Send completion notification
            if self.discord_notifier:
                await self.discord_notifier.notify_video_completed(
                    person_name=person_name,
                    theme=theme,
                    output_path=str(video_file),
                    duration=audio_duration,
                    youtube_url=youtube_url,
                    drive_url=drive_url,
                )

            # Return results
            total_time = time.time() - start_time
            logger.info(
                f"Video workflow completed successfully in {total_time:.1f} seconds"
            )

            return {
                "success": True,
                "project_dir": str(project_dir),
                "video_file": str(video_file),
                "thumbnail_file": str(thumbnail_file) if thumbnail_file else None,
                "youtube_url": youtube_url,
                "youtube_video_id": video_id,
                "drive_url": drive_url,
                "duration_seconds": audio_duration,
                "generation_time_seconds": total_time,
            }

        except Exception as e:
            logger.error(f"Video workflow failed: {e}")

            # Send error notification
            if self.discord_notifier:
                await self.discord_notifier.notify_error(
                    str(e), context=f"{person_name} - {theme}"
                )

            return {
                "success": False,
                "error": str(e),
            }

    async def update_task_in_sheets(
        self, task_id: str, status: str, notes: str | None = None
    ) -> bool:
        """
        Update task status in Google Sheets.

        Args:
            task_id: Task ID (e.g., "YT-001")
            status: New status
            notes: Additional notes

        Returns:
            True if successful
        """
        if not self.sheets_manager or not self.enable_sheets:
            logger.warning("Google Sheets not enabled, skipping task update")
            return False

        from datetime import datetime

        completion_date = (
            datetime.now().strftime("%Y-%m-%d") if status == "完了" else None
        )

        return await self.sheets_manager.update_task_status(
            task_id=task_id,
            status=status,
            completion_date=completion_date,
            notes=notes,
        )

    async def post_pending_comments(self) -> dict[str, Any]:
        """
        保留中のコメントをリトライする。

        予約投稿（private）動画はコメントが無効なため、動画公開後にこのメソッドで
        保留コメントを投稿する。GitHub Actionsのスケジュール等から呼び出す。

        Returns:
            結果サマリー辞書
        """
        if not self.sheets_manager or not self.enable_sheets:
            logger.warning("Google Sheets not enabled, cannot retry pending comments")
            return {"success": 0, "failed": 0, "still_pending": 0}

        if not self.youtube_uploader or not self.enable_youtube:
            logger.warning("YouTube not enabled, cannot retry pending comments")
            return {"success": 0, "failed": 0, "still_pending": 0}

        # Sheetsから保留コメントを取得
        pending = await self.sheets_manager.get_pending_comments()
        if not pending:
            logger.info("保留コメントはありません")
            return {"success": 0, "failed": 0, "still_pending": 0}

        logger.info(f"保留コメント {len(pending)}件 のリトライを開始")

        success = 0
        failed = 0
        still_pending = 0

        for entry in pending:
            video_id = entry["video_id"]
            comment_text = entry["comment_text"]
            row_index = entry["row_index"]

            logger.info(f"リトライ: {video_id} ({entry.get('person_name', '')})")

            comment_id, status = await self.youtube_uploader.post_comment(
                video_id, comment_text
            )

            if comment_id:
                await self.sheets_manager.update_comment_status(row_index, "成功")
                success += 1
                logger.info(f"コメント投稿成功: {video_id}")
            elif status == "コメント無効":
                # まだ公開されていない → 保留のまま
                still_pending += 1
                logger.info(f"まだコメント無効（未公開）: {video_id}")
            else:
                await self.sheets_manager.update_comment_status(row_index, "失敗")
                failed += 1
                logger.warning(f"コメント投稿失敗: {video_id} ({status})")

        result = {
            "success": success,
            "failed": failed,
            "still_pending": still_pending,
        }
        logger.info(f"保留コメントリトライ完了: {result}")
        return result

    async def update_all_video_stats(self) -> dict[str, Any]:
        """
        全動画のHIJ列（再生数・いいね数・コメント数）を一括更新する。

        YouTube APIで各動画の統計を取得し、スプシに書き込む。
        GitHub Actionsのスケジュール等から定期実行を想定。

        Returns:
            結果サマリー辞書
        """
        if not self.sheets_manager or not self.enable_sheets:
            logger.warning("Google Sheets not enabled")
            return {"updated": 0, "failed": 0, "skipped": 0}

        if not self.youtube_uploader or not self.enable_youtube:
            logger.warning("YouTube not enabled")
            return {"updated": 0, "failed": 0, "skipped": 0}

        # YouTube認証
        if not self.youtube_uploader.youtube_service:
            logger.info("YouTube API認証を開始...")
            try:
                await self.youtube_uploader.authenticate()
                logger.info("✅ YouTube API認証成功")
            except Exception as e:
                logger.error(f"❌ YouTube API認証失敗: {e}")
                return {"updated": 0, "failed": 0, "skipped": 0, "error": str(e)}

        # Sheets認証
        if not self.sheets_manager.service:
            logger.info("Google Sheets API認証を開始...")
            try:
                await self.sheets_manager.authenticate()
                logger.info("✅ Google Sheets API認証成功")
            except Exception as e:
                logger.error(f"❌ Google Sheets API認証失敗: {e}")
                return {"updated": 0, "failed": 0, "skipped": 0, "error": str(e)}

        # 更新対象の動画リスト取得
        videos = await self.sheets_manager.get_videos_for_stats_update()
        if not videos:
            logger.info("統計更新対象の動画はありません")
            return {"updated": 0, "failed": 0, "skipped": 0}

        logger.info(f"統計更新開始: {len(videos)}件")

        updated = 0
        failed = 0
        skipped = 0

        for video in videos:
            video_id = video["video_id"]
            row_index = video["row_index"]

            try:
                info = await self.youtube_uploader.get_video_info(video_id)
                stats = info.get("statistics", {})

                view_count = int(stats.get("viewCount", 0))
                like_count = int(stats.get("likeCount", 0))
                comment_count = int(stats.get("commentCount", 0))

                await self.sheets_manager.update_video_stats(
                    row_index=row_index,
                    view_count=view_count,
                    like_count=like_count,
                    comment_count=comment_count,
                )
                updated += 1
                logger.info(
                    f"統計更新: {video.get('person_name', '')} "
                    f"(再生{view_count}, いいね{like_count}, コメント{comment_count})"
                )

            except Exception as e:
                error_str = str(e)
                if "Video not found" in error_str:
                    skipped += 1
                    logger.debug(f"動画が見つかりません（削除済み?）: {video_id}")
                else:
                    failed += 1
                    logger.warning(f"統計取得に失敗: {video_id} - {e}")

        result = {"updated": updated, "failed": failed, "skipped": skipped}
        logger.info(f"統計更新完了: {result}")
        return result

    async def get_production_stats(self) -> dict[str, Any]:
        """
        Get video production statistics from Google Sheets.

        Returns:
            Statistics dictionary
        """
        if not self.sheets_manager or not self.enable_sheets:
            logger.warning("Google Sheets not enabled")
            return {}

        return await self.sheets_manager.get_video_stats()
