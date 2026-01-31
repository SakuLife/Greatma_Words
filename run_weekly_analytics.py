"""
週次YouTubeアナリティクス分析 & サムネイルA/Bテスト実行スクリプト

使い方:
    python run_weekly_analytics.py analytics   # 分析のみ
    python run_weekly_analytics.py ab-test     # A/Bテストのみ
    python run_weekly_analytics.py all         # 両方（デフォルト）
"""

import asyncio
import sys
from datetime import datetime, timedelta

from app.config import settings
from app.services.discord_notifier import DiscordNotifier
from app.services.sheets_manager import SheetsManager
from app.services.thumbnail_ab_test_manager import ThumbnailABTestManager
from app.services.youtube_analytics import YouTubeAnalytics
from app.utils.logger import logger


async def run_analytics() -> dict:
    """
    週次アナリティクス分析を実行

    Returns:
        分析結果のサマリー
    """
    logger.info("=" * 60)
    logger.info("週次YouTube Analytics 分析開始")
    logger.info("=" * 60)

    analytics = YouTubeAnalytics()
    sheets = SheetsManager()

    await analytics.authenticate()
    await sheets.authenticate()

    report_date = datetime.now().strftime("%Y-%m-%d")
    summary: dict = {"report_date": report_date}

    # 1. 登録者推移
    logger.info("-" * 40)
    logger.info("Step 1: チャンネル登録者推移")
    try:
        subscriber_growth = await analytics.get_subscriber_growth(days=7)
        subscriber_data = [
            {
                "date": s.date,
                "gained": s.gained,
                "lost": s.lost,
                "net": s.net,
            }
            for s in subscriber_growth
        ]
        total_net = sum(s.net for s in subscriber_growth)
        summary["subscriber_net_change"] = total_net
        logger.info(f"  登録者純増: {total_net}")
    except Exception as e:
        logger.error(f"  登録者推移の取得に失敗: {e}")
        subscriber_data = []

    # 2. 注目動画の検出
    logger.info("-" * 40)
    logger.info("Step 2: 注目動画の検出")
    try:
        trending_videos = await analytics.detect_trending_videos(days=7)
        summary["trending_count"] = len(trending_videos)
        logger.info(f"  注目動画: {len(trending_videos)}件")
    except Exception as e:
        logger.error(f"  注目動画検出に失敗: {e}")
        trending_videos = []

    # 3. 視聴維持率（注目動画 + 直近動画の上位5件）
    logger.info("-" * 40)
    logger.info("Step 3: 視聴維持率分析")
    retention_data = []
    video_ids_to_check = [t["video_id"] for t in trending_videos[:5]]

    # 直近の動画も追加
    try:
        channel_id = await analytics.get_my_channel_id()
        recent_videos = await analytics.get_all_videos(channel_id, max_results=10)
        for v in recent_videos:
            if v.video_id not in video_ids_to_check:
                video_ids_to_check.append(v.video_id)
            if len(video_ids_to_check) >= 10:
                break
    except Exception as e:
        logger.warning(f"  直近動画の取得に失敗: {e}")

    for vid in video_ids_to_check:
        try:
            ret = await analytics.get_audience_retention(vid)
            retention_data.append(
                {
                    "video_id": vid,
                    "average_retention": ret.average_retention,
                }
            )
        except Exception as e:
            logger.warning(f"  維持率取得失敗 ({vid}): {e}")

    if retention_data:
        avg_retention = sum(r["average_retention"] for r in retention_data) / len(
            retention_data
        )
        summary["avg_retention"] = round(avg_retention, 1)
        logger.info(f"  平均維持率: {avg_retention:.1f}%")

    # 4. Google Sheetsに書き込み
    logger.info("-" * 40)
    logger.info("Step 4: Google Sheetsに記録")
    try:
        # 注目動画にタイトル情報を付加
        for r in retention_data:
            for t in trending_videos:
                if t.get("video_id") == r["video_id"]:
                    r["title"] = t.get("title", "")
                    break

        success = await sheets.write_weekly_analytics(
            subscriber_data=subscriber_data,
            trending_videos=trending_videos,
            retention_data=retention_data,
            report_date=report_date,
        )
        if success:
            logger.info("  Sheets記録完了")
        else:
            logger.error("  Sheets記録に失敗")
    except Exception as e:
        logger.error(f"  Sheets記録エラー: {e}")

    logger.info("=" * 60)
    logger.info(f"週次分析完了: {summary}")
    logger.info("=" * 60)

    return summary


async def run_ab_test() -> dict:
    """
    A/Bテストサイクルを実行

    Returns:
        実行結果のサマリー
    """
    if not settings.ab_test_enabled:
        logger.info("A/Bテストは無効です (AB_TEST_ENABLED=false)")
        return {"enabled": False}

    logger.info("=" * 60)
    logger.info("サムネイルA/Bテスト実行開始")
    logger.info("=" * 60)

    manager = ThumbnailABTestManager()
    result = await manager.run_weekly_cycle()

    logger.info("=" * 60)
    logger.info(f"A/Bテスト完了: {result}")
    logger.info("=" * 60)

    return result


async def run_all() -> dict:
    """分析とA/Bテストの両方を実行"""
    analytics_result = await run_analytics()
    ab_result = await run_ab_test()

    # Discord通知
    try:
        discord = DiscordNotifier()
        if discord.webhook_url:
            message = f"""📊 **週次YouTube Analytics レポート**

**レポート日**: {analytics_result.get('report_date', 'N/A')}
**登録者純増**: {analytics_result.get('subscriber_net_change', 'N/A')}人
**注目動画**: {analytics_result.get('trending_count', 0)}件
**平均維持率**: {analytics_result.get('avg_retention', 'N/A')}%

**A/Bテスト**: アクティブ{ab_result.get('active_tests', 0)}件 / 完了{ab_result.get('completed', 0)}件 / 切替{ab_result.get('rotated', 0)}件

詳細は Google Sheets を確認してください。"""
            await discord.send_message(message)
    except Exception as e:
        logger.warning(f"Discord通知失敗: {e}")

    return {"analytics": analytics_result, "ab_test": ab_result}


async def main():
    """メインエントリポイント"""
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    print(f"\n{'=' * 60}")
    print("GreatMan Words - 週次YouTube Analytics")
    print(f"モード: {mode}")
    print(f"{'=' * 60}\n")

    if mode == "analytics":
        result = await run_analytics()
    elif mode == "ab-test":
        result = await run_ab_test()
    else:
        result = await run_all()

    print(f"\n{'=' * 60}")
    print(f"完了: {result}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n中断されました")
    except Exception as e:
        logger.error(f"実行エラー: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
