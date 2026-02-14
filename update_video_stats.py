"""
全動画の再生数・いいね数・コメント数をスプレッドシートに反映するスクリプト。

YouTube APIから統計情報を取得し、動画制作ログのHIJ列を更新する。
GitHub Actionsから定期実行を想定。

使い方:
    python update_video_stats.py
"""

import asyncio
import sys

from app.services.video_workflow import VideoWorkflow
from app.utils.logger import logger


async def main():
    """全動画の統計情報を一括更新"""
    logger.info("=" * 60)
    logger.info("動画統計の一括更新を開始します")
    logger.info("=" * 60)

    workflow = VideoWorkflow(
        enable_youtube=True,
        enable_drive=False,
        enable_sheets=True,
        enable_discord=False,
    )

    result = await workflow.update_all_video_stats()

    logger.info(f"更新結果: {result}")

    if result["updated"] > 0:
        logger.info(f"✅ {result['updated']}件の統計を更新しました")
    if result["skipped"] > 0:
        logger.info(f"⏭️ {result['skipped']}件をスキップ（動画が見つかりません）")
    if result["failed"] > 0:
        logger.error(f"❌ {result['failed']}件の統計取得に失敗しました")

    # 全件失敗の場合はエラー終了（CI で検知できるように）
    if result["updated"] == 0 and result["failed"] > 0:
        logger.error("統計更新が全件失敗しました。認証トークンを確認してください。")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCancelled")
    except Exception as e:
        logger.error(f"統計更新でエラーが発生: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
