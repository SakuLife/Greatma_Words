"""
Publish the latest private video to public.
Run at 18:00 JST to publish videos generated at 10:00 JST.
"""
import asyncio
from datetime import datetime, timedelta

from app.config import settings
from app.services.discord_notifier import DiscordNotifier
from app.services.youtube_uploader import YouTubeUploader
from app.utils.logger import logger


async def main():
    """Find and publish the latest private video."""
    logger.info("=" * 60)
    logger.info("最新のプライベート動画を公開します")
    logger.info("=" * 60)

    try:
        # Initialize services
        uploader = YouTubeUploader()
        await uploader.authenticate()

        discord = None
        if settings.discord_webhook_url:
            discord = DiscordNotifier()

        # Get list of private videos from today
        logger.info("プライベート動画を検索中...")

        # Search for videos uploaded today
        today = datetime.now()
        search_response = (
            uploader.youtube.search()
            .list(
                part="id,snippet",
                forMine=True,
                type="video",
                order="date",
                maxResults=50,
                publishedAfter=(today - timedelta(days=1)).isoformat() + "Z",
            )
            .execute()
        )

        if not search_response.get("items"):
            logger.warning("プライベート動画が見つかりませんでした")
            return

        # Find the latest private video
        latest_private_video = None
        for item in search_response["items"]:
            video_id = item["id"]["videoId"]

            # Get video details to check privacy status
            video_response = (
                uploader.youtube.videos()
                .list(part="status,snippet", id=video_id)
                .execute()
            )

            if video_response.get("items"):
                video = video_response["items"][0]
                privacy_status = video["status"]["privacyStatus"]

                if privacy_status == "private":
                    latest_private_video = video
                    break

        if not latest_private_video:
            logger.warning("本日アップロードされたプライベート動画が見つかりませんでした")
            return

        video_id = latest_private_video["id"]
        title = latest_private_video["snippet"]["title"]

        logger.info(f"プライベート動画を発見: {title}")
        logger.info(f"Video ID: {video_id}")

        # Update to public
        logger.info("公開状態に変更中...")

        uploader.youtube.videos().update(
            part="status",
            body={
                "id": video_id,
                "status": {
                    "privacyStatus": "public",
                },
            },
        ).execute()

        logger.info("✅ 動画を公開しました！")

        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        logger.info(f"YouTube URL: {youtube_url}")

        # Send Discord notification
        if discord:
            try:
                await discord.send_message(
                    f"""
📢 **動画を公開しました！**

**タイトル**: {title}
**URL**: {youtube_url}
**公開時刻**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

自動公開システムにより、プライベート状態から公開状態に変更されました。
"""
                )
            except Exception as e:
                logger.warning(f"Discord notification failed: {e}")

        logger.info("=" * 60)
        logger.info("完了！")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"公開処理に失敗: {e}")
        import traceback

        traceback.print_exc()

        if discord:
            try:
                await discord.notify_error(
                    str(e), context="動画の自動公開処理でエラーが発生しました"
                )
            except Exception:
                pass

        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n中断されました")
    except Exception as e:
        logger.error(f"実行エラー: {e}")
        print(f"\nエラー: {e}")
        exit(1)
