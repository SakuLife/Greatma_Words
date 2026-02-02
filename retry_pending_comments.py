"""
保留中の自動コメントをリトライするスクリプト。

予約投稿（private）動画はコメントが無効なため、動画公開後にこのスクリプトで
保留コメントを投稿する。

使い方:
    python retry_pending_comments.py
"""

import asyncio
import sys

from app.services.video_workflow import VideoWorkflow
from app.utils.logger import logger


async def main():
    """保留コメントのリトライを実行"""
    logger.info("保留コメントのリトライを開始します")

    workflow = VideoWorkflow(
        enable_youtube=True,
        enable_drive=False,
        enable_sheets=True,
        enable_discord=False,
    )

    result = await workflow.post_pending_comments()

    logger.info(f"リトライ結果: {result}")

    if result["success"] > 0:
        logger.info(f"{result['success']}件のコメント投稿に成功しました")
    if result["still_pending"] > 0:
        logger.info(f"{result['still_pending']}件がまだ保留中です（動画未公開）")
    if result["failed"] > 0:
        logger.warning(f"{result['failed']}件のコメント投稿に失敗しました")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCancelled")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
