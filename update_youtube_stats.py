"""
Update YouTube statistics in Google Sheets.
Fetches view count, like count, and comment count for all uploaded videos.
"""

import asyncio
import re
from datetime import datetime

from app.services.sheets_manager import SheetsManager
from app.services.youtube_analytics import YouTubeAnalytics
from app.utils.logger import logger


def extract_video_id(url: str) -> str | None:
    """Extract video ID from YouTube URL."""
    if not url:
        return None

    # Match patterns like:
    # - https://www.youtube.com/watch?v=VIDEO_ID
    # - https://youtu.be/VIDEO_ID
    patterns = [
        r"watch\?v=([a-zA-Z0-9_-]+)",
        r"youtu\.be/([a-zA-Z0-9_-]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


async def update_youtube_stats():
    """Update YouTube statistics for all videos in Sheets."""
    logger.info("=" * 60)
    logger.info("YouTube Statistics Update")
    logger.info("=" * 60)

    # Initialize services
    sheets = SheetsManager()
    youtube = YouTubeAnalytics()

    try:
        # Authenticate
        logger.info("Step 1: Authenticating...")
        await sheets.authenticate()
        await youtube.authenticate(token_file="token.json")
        logger.info("✅ Authentication successful")

        # Read all video logs
        logger.info("\nStep 2: Reading video logs from Sheets...")
        range_name = "動画制作ログ!A:K"
        result = (
            sheets.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=sheets.spreadsheet_id,
                range=range_name,
            )
            .execute()
        )

        values = result.get("values", [])

        if len(values) <= 1:
            logger.warning("No video data found in Sheets")
            return

        logger.info(f"Found {len(values) - 1} videos")

        # Header row
        header = values[0]
        youtube_url_idx = header.index("YouTube URL") if "YouTube URL" in header else 6
        view_count_idx = header.index("視聴回数") if "視聴回数" in header else 7
        like_count_idx = header.index("いいね数") if "いいね数" in header else 8
        comment_count_idx = header.index("コメント数") if "コメント数" in header else 9

        # Collect video IDs to fetch
        video_ids_to_fetch = []
        video_row_map = {}  # video_id -> row_index

        for row_idx, row in enumerate(values[1:], start=2):  # Start at row 2 (skip header)
            if len(row) > youtube_url_idx:
                youtube_url = row[youtube_url_idx]
                video_id = extract_video_id(youtube_url)

                if video_id:
                    video_ids_to_fetch.append(video_id)
                    video_row_map[video_id] = row_idx
                    logger.debug(f"Found video: {video_id} at row {row_idx}")

        if not video_ids_to_fetch:
            logger.warning("No YouTube URLs found in Sheets")
            return

        logger.info(f"Found {len(video_ids_to_fetch)} videos with YouTube URLs")

        # Fetch statistics from YouTube API
        logger.info("\nStep 3: Fetching statistics from YouTube...")
        video_stats = await youtube.get_video_stats(video_ids_to_fetch)

        logger.info(f"✅ Retrieved stats for {len(video_stats)} videos")

        # Update Sheets
        logger.info("\nStep 4: Updating Google Sheets...")
        update_count = 0

        for stats in video_stats:
            row_idx = video_row_map.get(stats.video_id)
            if not row_idx:
                continue

            # Update the row with statistics
            # Columns: H (view_count), I (like_count), J (comment_count)
            range_to_update = f"動画制作ログ!H{row_idx}:J{row_idx}"
            values_to_update = [
                [
                    str(stats.view_count),
                    str(stats.like_count),
                    str(stats.comment_count),
                ]
            ]

            try:
                sheets.service.spreadsheets().values().update(
                    spreadsheetId=sheets.spreadsheet_id,
                    range=range_to_update,
                    valueInputOption="RAW",
                    body={"values": values_to_update},
                ).execute()

                logger.info(
                    f"  ✅ {stats.title[:50]}: "
                    f"Views={stats.view_count:,}, Likes={stats.like_count:,}, Comments={stats.comment_count}"
                )
                update_count += 1

            except Exception as e:
                logger.error(f"Failed to update row {row_idx}: {e}")

        logger.info(f"\n{'='*60}")
        logger.info(f"✅ Update complete! Updated {update_count}/{len(video_stats)} videos")
        logger.info(f"{'='*60}")

        # Show summary
        logger.info("\nSummary:")
        total_views = sum(s.view_count for s in video_stats)
        total_likes = sum(s.like_count for s in video_stats)
        total_comments = sum(s.comment_count for s in video_stats)
        avg_engagement = (
            sum(s.engagement_rate for s in video_stats) / len(video_stats)
            if video_stats
            else 0
        )

        logger.info(f"  Total views: {total_views:,}")
        logger.info(f"  Total likes: {total_likes:,}")
        logger.info(f"  Total comments: {total_comments}")
        logger.info(f"  Average engagement rate: {avg_engagement:.2f}%")

        return {
            "success": True,
            "videos_updated": update_count,
            "total_views": total_views,
            "total_likes": total_likes,
            "total_comments": total_comments,
        }

    except Exception as e:
        logger.error(f"Failed to update YouTube stats: {e}")
        import traceback

        traceback.print_exc()
        return {"success": False, "error": str(e)}


async def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("YouTube Statistics Updater")
    print("=" * 60)
    print("\nThis script will:")
    print("1. Read all videos from Google Sheets")
    print("2. Fetch current YouTube statistics (views, likes, comments)")
    print("3. Update the statistics in Google Sheets")
    print("\n" + "=" * 60)

    confirm = input("\nContinue? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    result = await update_youtube_stats()

    if result and result.get("success"):
        print("\n✅ SUCCESS!")
        print(f"  Videos updated: {result['videos_updated']}")
        print(f"  Total views: {result['total_views']:,}")
        print(f"  Total likes: {result['total_likes']:,}")
        print(f"  Total comments: {result['total_comments']}")
    else:
        print("\n❌ FAILED")
        if result:
            print(f"  Error: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"\nError: {e}")
