"""
Complete video generation with full integration support.
Generates video using existing orchestrator, then logs to Sheets and sends Discord notifications.
"""

import asyncio
import time
from pathlib import Path

from app.config import settings
from app.main import orchestrator
from app.models.schemas import GenerationConfig
from app.services.discord_notifier import DiscordNotifier
from app.services.sheets_manager import SheetsManager
from app.utils.logger import logger
from pydub import AudioSegment


async def generate_video_with_integrations(
    person_name: str,
    topic: str,
    duration_minutes: int = 2,
    upload_to_youtube: bool = True,
    log_to_sheets: bool = True,
    send_discord_notifications: bool = True,
    youtube_privacy: str = "private",
):
    """
    Generate a complete video with all integrations.

    Args:
        person_name: Name of the person/figure
        topic: Video topic/theme
        duration_minutes: Target duration in minutes
        upload_to_youtube: Whether to upload to YouTube
        log_to_sheets: Whether to log to Google Sheets
        send_discord_notifications: Whether to send Discord notifications
        youtube_privacy: YouTube privacy status (public/private/unlisted)

    Returns:
        Dictionary with all results
    """
    start_time = time.time()

    # Initialize integrations
    discord = DiscordNotifier() if send_discord_notifications else None
    sheets = SheetsManager() if log_to_sheets else None

    logger.info(f"Starting complete video generation: {person_name} - {topic}")

    # Send start notification
    if discord:
        await discord.notify_video_started(person_name, topic, duration_minutes)

    try:
        # Step 1: Generate video using existing orchestrator
        logger.info("=" * 60)
        logger.info("GENERATING VIDEO")
        logger.info("=" * 60)

        config = GenerationConfig(
            topic=topic,
            person_name=person_name,
            target_duration_minutes=duration_minutes,
            upload_to_youtube=upload_to_youtube,
            youtube_privacy=youtube_privacy,
        )

        project, video_path = await orchestrator.generate_complete_video(config)

        logger.info(f"Video generated successfully: {video_path}")

        # Get video duration from audio file
        audio_path = project.audio_dir / "narration.wav"
        if audio_path.exists():
            audio = AudioSegment.from_wav(str(audio_path))
            video_duration = len(audio) / 1000.0  # Convert to seconds
        else:
            video_duration = 0.0

        # Get YouTube URL if uploaded
        youtube_url = None
        if project.youtube_video_id:
            youtube_url = f"https://www.youtube.com/watch?v={project.youtube_video_id}"
            logger.info(f"YouTube URL: {youtube_url}")

            if discord:
                await discord.notify_youtube_uploaded(
                    project.youtube_video_id,
                    f"{person_name} - {topic}",
                    youtube_privacy
                )

        # Step 2: Log to Google Sheets
        if log_to_sheets and sheets:
            logger.info("=" * 60)
            logger.info("LOGGING TO GOOGLE SHEETS")
            logger.info("=" * 60)

            generation_time = time.time() - start_time

            success = await sheets.log_video_production(
                person_name=person_name,
                theme=topic,
                video_duration=video_duration,
                generation_time=generation_time,
                youtube_url=youtube_url,
                project_path=str(project.project_dir),
            )

            if success:
                logger.info("Logged to Google Sheets successfully")
            else:
                logger.warning("Failed to log to Google Sheets")

        # Step 4: Send completion notification
        total_time = time.time() - start_time

        if discord:
            await discord.notify_video_completed(
                person_name=person_name,
                theme=topic,
                output_path=str(video_path),
                duration=video_duration,
                youtube_url=youtube_url,
            )

        logger.info("=" * 60)
        logger.info(f"COMPLETE! Total time: {total_time:.1f} seconds")
        logger.info("=" * 60)

        return {
            "success": True,
            "project_id": project.project_id,
            "project_dir": str(project.project_dir),
            "video_path": str(video_path),
            "thumbnail_path": str(project.thumbnail_path) if project.thumbnail_path else None,
            "youtube_url": youtube_url,
            "youtube_video_id": project.youtube_video_id,
            "video_duration_seconds": video_duration,
            "generation_time_seconds": total_time,
        }

    except Exception as e:
        logger.error(f"Video generation failed: {e}")

        # Send error notification
        if discord:
            await discord.notify_error(str(e), context=f"{person_name} - {topic}")

        return {
            "success": False,
            "error": str(e),
        }


async def main():
    """Test video generation with all integrations."""
    print("\n" + "=" * 60)
    print("GreatMan Words - Complete Video Generation")
    print("=" * 60)

    # Test parameters - short video for testing
    person_name = "リード・ヘイスティングス"
    topic = "自由と責任の経営哲学"
    duration = 5  # 5 minute video

    print(f"\n[INFO] Person: {person_name}")
    print(f"[INFO] Topic: {topic}")
    print(f"[INFO] Duration: {duration} minutes")
    print(f"\n[INFO] Integrations:")
    print(f"       - Discord notifications: ON")
    print(f"       - YouTube upload: ON (private)")
    print(f"       - Google Drive backup: ON")
    print(f"       - Google Sheets logging: ON")
    print("\n" + "=" * 60)

    # Confirm before proceeding
    confirm = input("\n[CONFIRM] Proceed with generation? (y/n): ").strip().lower()
    if confirm != "y":
        print("[CANCELLED] Generation cancelled by user.")
        return

    # Generate video
    result = await generate_video_with_integrations(
        person_name=person_name,
        topic=topic,
        duration_minutes=duration,
        upload_to_youtube=True,
        log_to_sheets=True,
        send_discord_notifications=True,
        youtube_privacy="private",
    )

    # Display results
    print("\n" + "=" * 60)
    if result["success"]:
        print("[SUCCESS] VIDEO GENERATION COMPLETED!")
        print("=" * 60)
        print(f"\nProject ID: {result['project_id']}")
        print(f"Video Path: {result['video_path']}")

        if result.get('thumbnail_path'):
            print(f"Thumbnail: {result['thumbnail_path']}")

        if result.get('youtube_url'):
            print(f"\n[YouTube] {result['youtube_url']}")
            print(f"          Video ID: {result['youtube_video_id']}")



        print(f"\n[Google Sheets] https://docs.google.com/spreadsheets/d/{settings.google_sheets_id}")

        print(f"\n[Discord] Check your Discord channel for notifications")

        print(f"\nVideo Duration: {result['video_duration_seconds']:.1f} seconds")
        print(f"Generation Time: {result['generation_time_seconds']:.1f} seconds")
    else:
        print("[ERROR] VIDEO GENERATION FAILED!")
        print("=" * 60)
        print(f"Error: {result.get('error', 'Unknown error')}")

    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[CANCELLED] Interrupted by user")
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        print(f"\n[ERROR] {e}")
