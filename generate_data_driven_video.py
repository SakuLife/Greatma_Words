"""
Data-driven video generation script.
Analyzes YouTube performance and generates optimized video content.
"""

import asyncio
import time
from pathlib import Path

from app.config import settings
from app.main import orchestrator
from app.models.schemas import GenerationConfig
from app.services.data_driven_workflow import DataDrivenWorkflow
from app.services.discord_notifier import DiscordNotifier
from app.services.drive_manager import DriveManager
from app.services.sheets_manager import SheetsManager
from app.utils.logger import logger
from pydub import AudioSegment


async def generate_data_driven_video(
    auto_suggest: bool = True,
    person_name: str | None = None,
    topic: str | None = None,
    duration_minutes: int = 15,
    upload_to_youtube: bool = True,
    upload_to_drive: bool = True,
    log_to_sheets: bool = True,
    send_discord_notifications: bool = True,
    youtube_privacy: str = "private",
):
    """
    Generate video using data-driven approach.

    Args:
        auto_suggest: Let AI suggest person and topic based on analytics
        person_name: Person name (if None and auto_suggest=True, AI will suggest)
        topic: Video topic (if None and auto_suggest=True, AI will suggest)
        duration_minutes: Target duration in minutes
        upload_to_youtube: Whether to upload to YouTube
        upload_to_drive: Whether to upload to Google Drive
        log_to_sheets: Whether to log to Google Sheets
        send_discord_notifications: Whether to send Discord notifications
        youtube_privacy: YouTube privacy status (public/private/unlisted)

    Returns:
        Dictionary with all results
    """
    start_time = time.time()

    # Initialize integrations
    discord = DiscordNotifier() if send_discord_notifications else None
    drive = DriveManager() if upload_to_drive else None
    sheets = SheetsManager() if log_to_sheets else None
    workflow = DataDrivenWorkflow()

    logger.info("=" * 60)
    logger.info("データドリブン動画生成開始")
    logger.info("=" * 60)

    if discord:
        await discord.notify_task_progress(
            "データ分析", 1, 8, "YouTubeチャンネルを分析中..."
        )

    try:
        # Step 1: Get data-driven suggestion and generate script
        logger.info("Step 1: データ分析と台本生成")
        logger.info("=" * 60)

        if auto_suggest and (not person_name or not topic):
            logger.info("AIによる人物・テーマ提案を実行中...")
            suggestion, script = await workflow.generate_data_driven_script(
                person_name=person_name,
                topic=topic,
                duration_minutes=duration_minutes,
            )

            person_name = suggestion["person_name"]
            topic = suggestion["suggested_theme"]

            logger.info(f"✅ AI提案完了:")
            logger.info(f"   人物: {person_name}")
            logger.info(f"   肩書: {suggestion['person_title']}")
            logger.info(f"   テーマ: {topic}")
            logger.info(f"   名言: {suggestion['famous_quote']}")
            logger.info(f"   理由: {suggestion['suggestion_reason']}")
            logger.info(f"   期待エンゲージメント: {suggestion['expected_engagement']}")

            if discord:
                await discord.notify_task_progress(
                    "台本生成",
                    2,
                    8,
                    f"AIが提案: {person_name} - {topic}",
                )
        else:
            logger.info(f"ユーザー指定: {person_name} - {topic}")
            suggestion, script = await workflow.generate_data_driven_script(
                person_name=person_name,
                topic=topic,
                duration_minutes=duration_minutes,
            )

            if discord:
                await discord.notify_task_progress(
                    "台本生成", 2, 8, f"{person_name} - {topic}"
                )

        logger.info(f"台本生成完了: {len(script.sections)}セクション")

        # Step 2: Generate complete video using existing orchestrator
        logger.info("=" * 60)
        logger.info("Step 2: 動画生成開始")
        logger.info("=" * 60)

        if discord:
            await discord.notify_task_progress(
                "動画生成", 3, 8, "画像・音声・動画を生成中..."
            )

        config = GenerationConfig(
            topic=topic,
            person_name=person_name,
            target_duration_minutes=duration_minutes,
            upload_to_youtube=upload_to_youtube,
            youtube_privacy=youtube_privacy,
        )

        # Generate video with the pre-generated script
        # (orchestratorは内部でscriptを生成するので、一旦通常フローで実行)
        project, video_path = await orchestrator.generate_complete_video(config)

        logger.info(f"動画生成成功: {video_path}")

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
                try:
                    await discord.notify_youtube_uploaded(
                        project.youtube_video_id, f"{person_name} - {topic}", youtube_privacy
                    )
                except Exception as e:
                    logger.warning(f"Discord notification failed (YouTube): {e}")

        # Step 3: Upload to Google Drive
        drive_url = None
        if upload_to_drive and drive:
            try:
                logger.info("=" * 60)
                logger.info("Step 3: Google Driveアップロード")
                logger.info("=" * 60)

                if discord:
                    try:
                        await discord.notify_task_progress(
                            "バックアップ", 7, 8, "Google Driveにアップロード中..."
                        )
                    except Exception as e:
                        logger.warning(f"Discord notification failed (Drive start): {e}")

                file_info = await drive.upload_file(
                    video_path,
                    file_name=f"{person_name}_{topic}.mp4",
                )
                drive_url = file_info["url"]
                file_size_mb = file_info["size"] / (1024 * 1024)

                logger.info(f"Driveアップロード完了: {drive_url}")

                if discord:
                    try:
                        await discord.notify_drive_uploaded(
                            file_info["name"], drive_url, file_size_mb
                        )
                    except Exception as e:
                        logger.warning(f"Discord notification failed (Drive complete): {e}")
            except Exception as e:
                logger.error(f"Google Drive upload failed: {e}")
                # Continue even if Drive upload fails

        # Step 4: Log to Google Sheets
        if log_to_sheets and sheets:
            try:
                logger.info("=" * 60)
                logger.info("Step 4: Google Sheetsログ記録")
                logger.info("=" * 60)

                if discord:
                    try:
                        await discord.notify_task_progress(
                            "記録", 8, 8, "Google Sheetsに記録中..."
                        )
                    except Exception as e:
                        logger.warning(f"Discord notification failed (Sheets start): {e}")

                generation_time = time.time() - start_time

                # Add suggestion data to sheets log
                notes = f"AI提案: {suggestion.get('suggestion_reason', 'N/A')}"
                if auto_suggest:
                    notes += f"\n期待エンゲージメント: {suggestion.get('expected_engagement', 'N/A')}"

                success = await sheets.log_video_production(
                    person_name=person_name,
                    theme=topic,
                    video_duration=video_duration,
                    generation_time=generation_time,
                    youtube_url=youtube_url,
                    drive_url=drive_url,
                    project_path=str(project.project_dir),
                )

                if success:
                    logger.info("Sheetsログ記録完了")
            except Exception as e:
                logger.error(f"Google Sheets logging failed: {e}")
                # Continue even if Sheets logging fails

        # Step 5: Send completion notification
        total_time = time.time() - start_time

        if discord:
            try:
                completion_message = f"""
📊 **データドリブン動画生成完了**

**人物**: {person_name}
**肩書**: {suggestion.get('person_title', 'N/A')}
**テーマ**: {topic}
**名言**: {suggestion.get('famous_quote', 'N/A')}

**AI分析結果**:
理由: {suggestion.get('suggestion_reason', 'N/A')}
期待エンゲージメント: {suggestion.get('expected_engagement', 'N/A')}

**動画情報**:
長さ: {video_duration:.1f}秒
生成時間: {total_time:.1f}秒
"""
                await discord.notify_video_completed(
                    person_name=person_name,
                    theme=topic,
                    output_path=str(video_path),
                    duration=video_duration,
                    youtube_url=youtube_url,
                    drive_url=drive_url,
                )
            except Exception as e:
                logger.warning(f"Discord notification failed (completion): {e}")

        logger.info("=" * 60)
        logger.info(f"✅ 完了! 合計時間: {total_time:.1f}秒")
        logger.info("=" * 60)

        return {
            "success": True,
            "suggestion": suggestion,
            "project_id": project.project_id,
            "project_dir": str(project.project_dir),
            "video_path": str(video_path),
            "thumbnail_path": str(project.thumbnail_path) if project.thumbnail_path else None,
            "youtube_url": youtube_url,
            "youtube_video_id": project.youtube_video_id,
            "drive_url": drive_url,
            "video_duration_seconds": video_duration,
            "generation_time_seconds": total_time,
        }

    except Exception as e:
        logger.error(f"データドリブン動画生成失敗: {e}")

        # Send error notification
        if discord:
            await discord.notify_error(str(e), context=f"{person_name} - {topic}")

        return {
            "success": False,
            "error": str(e),
        }


async def main():
    """Test data-driven video generation."""
    import sys

    print("\n" + "=" * 60)
    print("GreatMan Words - データドリブン動画生成")
    print("=" * 60)

    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "auto":
        # AI Auto-suggest mode (non-interactive)
        duration = int(sys.argv[2]) if len(sys.argv) > 2 else 15

        print("\n[AI自動提案モード - 自動実行]")
        print(f"動画の長さ: {duration}分")
        print("YouTubeチャンネルのデータを分析し、AIが最適な人物とテーマを提案します。")

        result = await generate_data_driven_video(
            auto_suggest=True,
            person_name=None,
            topic=None,
            duration_minutes=duration,
            upload_to_youtube=True,
            upload_to_drive=True,
            log_to_sheets=True,
            send_discord_notifications=True,
            youtube_privacy="private",
        )

    elif len(sys.argv) > 1 and sys.argv[1] == "manual":
        # Manual mode (from command line)
        person_name = sys.argv[2] if len(sys.argv) > 2 else "ピーター・ドラッカー"
        topic = sys.argv[3] if len(sys.argv) > 3 else "マネジメントの本質"
        duration = int(sys.argv[4]) if len(sys.argv) > 4 else 15

        print(f"\n[手動指定モード - 自動実行]")
        print(f"人物: {person_name}")
        print(f"テーマ: {topic}")
        print(f"動画の長さ: {duration}分")

        result = await generate_data_driven_video(
            auto_suggest=False,
            person_name=person_name,
            topic=topic,
            duration_minutes=duration,
            upload_to_youtube=True,
            upload_to_drive=True,
            log_to_sheets=True,
            send_discord_notifications=True,
            youtube_privacy="public",  # 公開設定
        )

    else:
        # Interactive mode
        print("\n[モード選択]")
        print("1. AI自動提案モード（YouTubeデータ分析→人物提案→動画生成）")
        print("2. 手動指定モード（人物・テーマを指定）")

        mode = input("\nモードを選択 (1/2): ").strip()

        if mode == "1":
            # AI Auto-suggest mode
            print("\n[AI自動提案モード]")
            print("YouTubeチャンネルのデータを分析し、AIが最適な人物とテーマを提案します。")

            duration = int(input("\n動画の長さ（分）[15]: ").strip() or "15")

            confirm = input("\n実行しますか？ (y/n): ").strip().lower()
            if confirm != "y":
                print("キャンセルしました。")
                return

            result = await generate_data_driven_video(
                auto_suggest=True,
                person_name=None,
                topic=None,
                duration_minutes=duration,
                upload_to_youtube=True,
                upload_to_drive=True,
                log_to_sheets=True,
                send_discord_notifications=True,
                youtube_privacy="private",
            )

        else:
            # Manual mode
            print("\n[手動指定モード]")
            person_name = input("人物名: ").strip()
            topic = input("テーマ: ").strip()
            duration = int(input("動画の長さ（分）[15]: ").strip() or "15")

            confirm = input(f"\n{person_name} - {topic} で生成しますか？ (y/n): ").strip().lower()
            if confirm != "y":
                print("キャンセルしました。")
                return

            result = await generate_data_driven_video(
                auto_suggest=False,
                person_name=person_name,
                topic=topic,
                duration_minutes=duration,
                upload_to_youtube=True,
                upload_to_drive=True,
                log_to_sheets=True,
                send_discord_notifications=True,
                youtube_privacy="private",
            )

    # Display results
    print("\n" + "=" * 60)
    if result["success"]:
        print("✅ データドリブン動画生成成功!")
        print("=" * 60)

        if "suggestion" in result:
            suggestion = result["suggestion"]
            print(f"\n【AI提案情報】")
            print(f"  人物: {suggestion.get('person_name', 'N/A')}")
            print(f"  肩書: {suggestion.get('person_title', 'N/A')}")
            print(f"  テーマ: {suggestion.get('suggested_theme', 'N/A')}")
            print(f"  名言: {suggestion.get('famous_quote', 'N/A')}")
            print(f"  理由: {suggestion.get('suggestion_reason', 'N/A')}")
            print(f"  期待エンゲージメント: {suggestion.get('expected_engagement', 'N/A')}")

        print(f"\n【生成結果】")
        print(f"  プロジェクトID: {result['project_id']}")
        print(f"  動画パス: {result['video_path']}")

        if result.get("youtube_url"):
            print(f"\n[YouTube] {result['youtube_url']}")
            print(f"          Video ID: {result['youtube_video_id']}")

        if result.get("drive_url"):
            print(f"\n[Google Drive] {result['drive_url']}")

        print(f"\n[Google Sheets] https://docs.google.com/spreadsheets/d/{settings.google_sheets_id}")
        print(f"\n[Discord] チャンネルで通知を確認してください")

        print(f"\n動画時間: {result['video_duration_seconds']:.1f}秒")
        print(f"生成時間: {result['generation_time_seconds']:.1f}秒")
    else:
        print("❌ 動画生成失敗")
        print("=" * 60)
        print(f"エラー: {result.get('error', 'Unknown error')}")

    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n中断されました")
    except Exception as e:
        logger.error(f"実行エラー: {e}")
        print(f"\nエラー: {e}")
