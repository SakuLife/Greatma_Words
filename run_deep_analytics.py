"""
包括的チャンネル分析 & コンテンツ戦略生成エントリポイント

使い方:
    python run_deep_analytics.py              # 全分析+戦略生成（デフォルト）
    python run_deep_analytics.py analysis     # チャンネル分析のみ
    python run_deep_analytics.py competitor   # 競合調査のみ
    python run_deep_analytics.py strategy     # 戦略生成（分析+競合+LLM統合）
    python run_deep_analytics.py all          # 全て実行
"""

import asyncio
import sys
from datetime import datetime

from app.config import settings
from app.services.channel_deep_analyzer import ChannelDeepAnalyzer
from app.services.competitor_researcher import CompetitorResearcher
from app.services.content_strategy_engine import ContentStrategyEngine
from app.services.discord_notifier import DiscordNotifier
from app.services.sheets_manager import SheetsManager
from app.utils.logger import logger


async def run_deep_analysis(days: int = 90) -> dict:
    """
    包括的チャンネル分析を実行

    Args:
        days: 分析対象日数

    Returns:
        分析結果のサマリー
    """
    logger.info("=" * 60)
    logger.info(f"包括的チャンネル分析（過去{days}日間）")
    logger.info("=" * 60)

    analyzer = ChannelDeepAnalyzer()
    analysis = await analyzer.run_full_analysis(days=days)

    # LLM用レポートをログ出力
    report = analyzer.format_for_llm(analysis)
    logger.info("分析レポート:")
    for line in report.split("\n"):
        logger.info(f"  {line}")

    # Sheetsに保存
    try:
        sheets = SheetsManager()
        await sheets.authenticate()
        await sheets.write_deep_analysis({
            "analysis_date": analysis.analysis_date,
            "analysis_period_days": analysis.analysis_period_days,
            "subscriber_count": analysis.subscriber_count,
            "total_views": analysis.total_views,
            "total_videos": analysis.total_videos,
            "top_traffic_source": analysis.top_traffic_source,
            "traffic_sources": [
                {"source_type": ts.source_type, "percentage": ts.percentage}
                for ts in analysis.traffic_sources[:5]
            ],
            "top_age_group": analysis.demographics.top_age_group if analysis.demographics else "",
            "gender_ratio": str(analysis.demographics.gender_ratio if analysis.demographics else ""),
            "primary_device": analysis.primary_device,
            "devices": [
                {"device_type": d.device_type, "percentage": d.percentage}
                for d in analysis.devices[:5]
            ],
            "top_subscriber_videos": [
                {"title": v.title, "subscribers_gained": v.subscribers_gained}
                for v in analysis.top_subscriber_videos[:3]
            ],
            "recommended_publish_time": (
                analysis.upload_time_analysis.publish_at_description
                if analysis.upload_time_analysis else ""
            ),
            "upload_time_confidence": (
                f"{analysis.upload_time_analysis.confidence:.0%}"
                if analysis.upload_time_analysis else ""
            ),
        })

        if analysis.upload_time_analysis:
            uta = analysis.upload_time_analysis
            await sheets.write_upload_time_analysis(
                [
                    {
                        "day_name": dp.day_name,
                        "total_uploads": dp.total_uploads,
                        "avg_initial_views_48h": dp.avg_initial_views_48h,
                    }
                    for dp in uta.day_performances
                ],
                uta.publish_at_description,
                uta.confidence,
            )
    except Exception as e:
        logger.error(f"Sheets保存に失敗: {e}")

    return {
        "channel": analysis.channel_title,
        "subscribers": analysis.subscriber_count,
        "total_views": analysis.total_views,
        "traffic_top": analysis.top_traffic_source,
        "primary_device": analysis.primary_device,
        "top_sub_videos": len(analysis.top_subscriber_videos),
        "publish_recommendation": (
            analysis.upload_time_analysis.publish_at_description
            if analysis.upload_time_analysis else "データ不足"
        ),
    }


async def run_competitor_research() -> dict:
    """
    競合・ニッチ調査を実行

    Returns:
        調査結果のサマリー
    """
    logger.info("=" * 60)
    logger.info("競合・ニッチ調査")
    logger.info("=" * 60)

    researcher = CompetitorResearcher()
    result = await researcher.research_niche(max_queries=3)

    # レポートをログ出力
    report = researcher.format_for_llm(result)
    logger.info("競合調査レポート:")
    for line in report.split("\n"):
        logger.info(f"  {line}")

    # Sheetsに保存
    try:
        sheets = SheetsManager()
        await sheets.authenticate()
        await sheets.write_competitor_analysis({
            "analyzed_at": result.analyzed_at,
            "search_queries": result.search_queries,
            "videos": [
                {
                    "title": v.title,
                    "channel_title": v.channel_title,
                    "view_count": v.view_count,
                    "like_count": v.like_count,
                    "engagement_rate": v.engagement_rate,
                }
                for v in result.videos[:20]
            ],
            "gap_opportunities": result.gap_opportunities,
        })
    except Exception as e:
        logger.error(f"Sheets保存に失敗: {e}")

    return {
        "total_videos": result.total_videos_analyzed,
        "trending_persons": len(result.trending_persons),
        "gap_opportunities": len(result.gap_opportunities),
        "top_gaps": [g["person"] for g in result.gap_opportunities[:3]],
    }


async def run_full_strategy() -> dict:
    """
    全データ統合 → コンテンツ戦略生成

    Returns:
        戦略のサマリー
    """
    logger.info("=" * 60)
    logger.info("コンテンツ戦略生成（全データ統合）")
    logger.info("=" * 60)

    engine = ContentStrategyEngine()
    strategy = await engine.generate_weekly_strategy(analysis_days=90)

    # 戦略をログ出力
    suggestions = strategy.get("next_video_suggestions", [])
    logger.info(f"動画提案: {len(suggestions)}件")
    for i, s in enumerate(suggestions, 1):
        logger.info(f"  {i}. {s.get('person', '')} - {s.get('topic', '')}")
        logger.info(f"     フック: {s.get('hook_strategy', '')}, 構成: {s.get('structure', '')}")
        logger.info(f"     タイトル案: {s.get('title_suggestion', '')}")

    upload = strategy.get("upload_schedule", {})
    logger.info(f"推奨投稿: {upload.get('publish_at_jst', 'N/A')}")

    return {
        "suggestions_count": len(suggestions),
        "suggestions": [
            {"person": s.get("person"), "topic": s.get("topic")}
            for s in suggestions
        ],
        "upload_schedule": upload,
        "channel_health": strategy.get("channel_health", {}),
    }


async def run_all() -> dict:
    """全ての分析と戦略生成を実行"""
    # 戦略生成は内部で全分析を実行するので、これだけで十分
    strategy_result = await run_full_strategy()

    # Discord通知
    try:
        discord = DiscordNotifier()
        if discord.webhook_url:
            suggestions = strategy_result.get("suggestions", [])
            suggestion_text = "\n".join(
                f"  {i+1}. {s['person']} - {s['topic']}"
                for i, s in enumerate(suggestions[:3])
            )
            upload = strategy_result.get("upload_schedule", {})

            message = f"""📊 **週次チャンネル包括分析 & 戦略レポート**

**分析日**: {datetime.now().strftime('%Y-%m-%d')}

**動画提案**:
{suggestion_text}

**推奨投稿日時**: {upload.get('publish_at_jst', 'N/A')} ({upload.get('confidence', 'N/A')})

**チャンネル健全性**: {strategy_result.get('channel_health', {})}

詳細は Google Sheets を確認してください。"""
            await discord.send_message(message)
    except Exception as e:
        logger.warning(f"Discord通知失敗: {e}")

    return strategy_result


async def main():
    """メインエントリポイント"""
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    print(f"\n{'=' * 60}")
    print("GreatMan Words - 包括的チャンネル分析 & 戦略生成")
    print(f"モード: {mode}")
    print(f"{'=' * 60}\n")

    if mode == "analysis":
        result = await run_deep_analysis()
    elif mode == "competitor":
        result = await run_competitor_research()
    elif mode == "strategy":
        result = await run_full_strategy()
    else:
        result = await run_all()

    print(f"\n{'=' * 60}")
    print("完了:")
    for k, v in result.items():
        print(f"  {k}: {v}")
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
