"""
包括的チャンネル深層分析サービス。
YouTube Analytics API v2を使い、全動画・全期間のデータを収集・分析する。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.models.analytics_models import (
    ChannelDeepAnalysis,
    DayOfWeekPerformance,
    UploadTimeAnalysis,
)
from app.services.youtube_analytics import YouTubeAnalytics
from app.utils.logger import logger

# 曜日名マッピング（0=月曜〜6=日曜）
DAY_NAMES = ["月", "火", "水", "木", "金", "土", "日"]


class ChannelDeepAnalyzer:
    """全チャンネルデータの包括的分析を実行する"""

    def __init__(self):
        self.analytics = YouTubeAnalytics()

    async def run_full_analysis(self, days: int = 90) -> ChannelDeepAnalysis:
        """
        全データ収集を実行し、包括的分析結果を返す

        Args:
            days: 分析対象の日数（デフォルト90日）

        Returns:
            ChannelDeepAnalysis 統合分析結果
        """
        logger.info("=" * 60)
        logger.info(f"包括的チャンネル分析開始（過去{days}日間）")
        logger.info("=" * 60)

        await self.analytics.authenticate()

        end_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days + 2)).strftime("%Y-%m-%d")

        analysis = ChannelDeepAnalysis(
            analysis_date=datetime.now().strftime("%Y-%m-%d"),
            analysis_period_days=days,
        )

        # 基本チャンネル情報
        try:
            channel_stats = await self.analytics.get_channel_stats()
            analysis.channel_id = channel_stats.channel_id
            analysis.channel_title = channel_stats.channel_title
            analysis.subscriber_count = channel_stats.subscriber_count
            analysis.total_views = channel_stats.total_view_count
            analysis.total_videos = channel_stats.video_count
            logger.info(f"チャンネル: {analysis.channel_title}")
            logger.info(f"  登録者: {analysis.subscriber_count:,}")
            logger.info(f"  総再生: {analysis.total_views:,}")
        except Exception as e:
            logger.error(f"チャンネル基本情報の取得に失敗: {e}")

        # 1. トラフィックソース
        logger.info("-" * 40)
        logger.info("Step 1: トラフィックソース分析")
        try:
            analysis.traffic_sources = await self.analytics.get_traffic_sources(
                start_date, end_date
            )
        except Exception as e:
            logger.warning(f"トラフィックソース取得スキップ: {e}")

        # 2. デモグラフィック
        logger.info("-" * 40)
        logger.info("Step 2: デモグラフィック分析")
        try:
            analysis.demographics = await self.analytics.get_demographics(
                start_date, end_date
            )
        except Exception as e:
            logger.warning(f"デモグラフィック取得スキップ: {e}")

        # 3. デバイス別
        logger.info("-" * 40)
        logger.info("Step 3: デバイス別分析")
        try:
            analysis.devices = await self.analytics.get_device_breakdown(
                start_date, end_date
            )
        except Exception as e:
            logger.warning(f"デバイス別取得スキップ: {e}")

        # 4. 動画別登録者影響
        logger.info("-" * 40)
        logger.info("Step 4: 動画別登録者獲得分析")
        try:
            analysis.subscriber_impact = await self.analytics.get_video_subscriber_impact(
                start_date, end_date
            )
        except Exception as e:
            logger.warning(f"動画別登録者影響取得スキップ: {e}")

        # 5. アップロード時間分析
        logger.info("-" * 40)
        logger.info("Step 5: アップロード時間分析")
        try:
            analysis.upload_time_analysis = await self._analyze_upload_times(
                start_date, end_date
            )
        except Exception as e:
            logger.warning(f"アップロード時間分析スキップ: {e}")

        logger.info("=" * 60)
        logger.info("包括的チャンネル分析完了")
        logger.info("=" * 60)

        return analysis

    async def _analyze_upload_times(
        self, start_date: str, end_date: str
    ) -> UploadTimeAnalysis:
        """
        各動画のpublishedAtと初動48時間の再生数を相関分析し、最適な投稿時間を算出

        Args:
            start_date: 分析開始日
            end_date: 分析終了日

        Returns:
            UploadTimeAnalysis 分析結果
        """
        # 全動画のpublishedAtを取得
        channel_id = await self.analytics.get_my_channel_id()
        videos = await self.analytics.get_all_videos(channel_id, max_results=100)

        if not videos:
            logger.warning("動画が見つからないため、アップロード時間分析をスキップ")
            return UploadTimeAnalysis(
                best_day_of_week=2,
                best_day_name="水",
                best_hour_jst=17,
                confidence=0.0,
                recommended_publish_time="水曜日 17:00 JST（データ不足のため推奨値）",
            )

        # 曜日別・時間帯別のパフォーマンスを集計
        day_stats: dict[int, list[int]] = {i: [] for i in range(7)}  # 曜日→初動再生数リスト
        hour_stats: dict[int, list[int]] = {i: [] for i in range(24)}  # 時間→初動再生数リスト

        analyzed_count = 0
        for video in videos:
            published = video.published_at
            if not published:
                continue

            # UTCをJSTに変換 (+9時間)
            jst_hour = (published.hour + 9) % 24
            jst_weekday = published.weekday()
            if published.hour + 9 >= 24:
                jst_weekday = (jst_weekday + 1) % 7

            # 初動48時間の再生数を取得
            pub_date = published.strftime("%Y-%m-%d")
            end_48h = (published + timedelta(days=2)).strftime("%Y-%m-%d")

            try:
                daily_views = await self.analytics.get_daily_views_for_video(
                    video.video_id, pub_date, end_48h
                )
                initial_views = sum(d["views"] for d in daily_views)

                if initial_views > 0:
                    day_stats[jst_weekday].append(initial_views)
                    hour_stats[jst_hour].append(initial_views)
                    analyzed_count += 1
            except Exception as e:
                logger.debug(f"初動データ取得失敗 ({video.video_id}): {e}")
                continue

        logger.info(f"アップロード時間分析: {analyzed_count}件の動画を分析")

        # 曜日別パフォーマンス
        day_performances = []
        for day_idx in range(7):
            views_list = day_stats[day_idx]
            avg_views = sum(views_list) / len(views_list) if views_list else 0
            day_performances.append(
                DayOfWeekPerformance(
                    day_of_week=day_idx,
                    day_name=DAY_NAMES[day_idx],
                    avg_views=0,  # 全期間平均（ここでは初動のみ集計）
                    avg_watch_time_minutes=0,
                    total_uploads=len(views_list),
                    avg_initial_views_48h=avg_views,
                )
            )

        # ベスト曜日
        best_day = max(day_performances, key=lambda x: x.avg_initial_views_48h)

        # ベスト時間帯
        best_hour = 17  # デフォルト
        best_hour_avg = 0
        for hour, views_list in hour_stats.items():
            if views_list:
                avg = sum(views_list) / len(views_list)
                if avg > best_hour_avg:
                    best_hour_avg = avg
                    best_hour = hour

        # 信頼度（サンプル数ベース）
        confidence = min(1.0, analyzed_count / 30)  # 30本以上で信頼度1.0

        result = UploadTimeAnalysis(
            best_day_of_week=best_day.day_of_week,
            best_day_name=best_day.day_name,
            best_hour_jst=best_hour,
            confidence=round(confidence, 2),
            day_performances=day_performances,
            recommended_publish_time=f"{best_day.day_name}曜日 {best_hour}:00 JST",
        )

        logger.info(f"  最適曜日: {result.best_day_name}曜日")
        logger.info(f"  最適時間: {result.best_hour_jst}:00 JST")
        logger.info(f"  信頼度: {result.confidence:.0%}")

        return result

    def format_for_llm(self, analysis: ChannelDeepAnalysis) -> str:
        """
        分析結果をLLMプロンプト用にフォーマットする

        Args:
            analysis: 包括的分析結果

        Returns:
            LLM向けフォーマット済みテキスト
        """
        sections = []

        # ヘッダー
        sections.append("# チャンネル包括分析レポート")
        sections.append(f"分析日: {analysis.analysis_date}")
        sections.append(f"対象期間: 過去{analysis.analysis_period_days}日間")

        # 基本情報
        sections.append(f"\n## チャンネル基本情報")
        sections.append(f"- チャンネル名: {analysis.channel_title}")
        sections.append(f"- 登録者数: {analysis.subscriber_count:,}")
        sections.append(f"- 総再生回数: {analysis.total_views:,}")
        sections.append(f"- 総動画数: {analysis.total_videos}")

        # トラフィックソース
        if analysis.traffic_sources:
            sections.append(f"\n## トラフィックソース")
            for ts in analysis.traffic_sources[:7]:
                sections.append(f"- {ts.source_type}: {ts.views:,} views ({ts.percentage}%)")

        # デモグラフィック
        if analysis.demographics and analysis.demographics.details:
            sections.append(f"\n## 視聴者デモグラフィック")
            sections.append(f"- 主要年齢層: {analysis.demographics.top_age_group}")
            gender_ratio = analysis.demographics.gender_ratio
            for g, pct in gender_ratio.items():
                sections.append(f"- {g}: {pct:.1f}%")
            # 詳細
            sections.append("### 年齢×性別の詳細割合")
            for d in analysis.demographics.details[:10]:
                sections.append(f"- {d.age_group} / {d.gender}: {d.percentage:.1f}%")

        # デバイス
        if analysis.devices:
            sections.append(f"\n## デバイス別視聴")
            for dev in analysis.devices:
                sections.append(
                    f"- {dev.device_type}: {dev.views:,} views ({dev.percentage}%)"
                )

        # 登録者獲得動画
        if analysis.subscriber_impact:
            sections.append(f"\n## 登録者獲得に貢献した動画 TOP10")
            for v in analysis.top_subscriber_videos:
                sections.append(
                    f"- {v.title[:40]}: "
                    f"+{v.subscribers_gained}人 (再生{v.views:,}回, "
                    f"獲得率{v.subscriber_per_view:.3f})"
                )

        # アップロード時間分析
        if analysis.upload_time_analysis:
            uta = analysis.upload_time_analysis
            sections.append(f"\n## 投稿時間分析")
            sections.append(f"- 推奨投稿時間: {uta.publish_at_description}")
            sections.append(f"- 信頼度: {uta.confidence:.0%}")
            if uta.day_performances:
                sections.append("### 曜日別初動パフォーマンス")
                for dp in uta.day_performances:
                    if dp.total_uploads > 0:
                        sections.append(
                            f"- {dp.day_name}曜: "
                            f"平均初動{dp.avg_initial_views_48h:.0f}再生 "
                            f"(投稿{dp.total_uploads}本)"
                        )

        # 競合分析（Phase 2で追加される場合）
        if analysis.competitor_analysis:
            ca = analysis.competitor_analysis
            sections.append(f"\n## 競合・ニッチ分析")
            sections.append(f"- 調査動画数: {ca.total_videos_analyzed}件")
            if ca.trending_persons:
                sections.append("### 競合で人気の人物")
                for p in ca.trending_persons[:10]:
                    sections.append(
                        f"- {p['person']}: {p['count']}本, "
                        f"平均{p.get('avg_views', 0):,.0f}再生"
                    )
            if ca.gap_opportunities:
                sections.append("### ギャップ機会（競合にあり自チャンネルにない）")
                for g in ca.gap_opportunities[:5]:
                    sections.append(
                        f"- {g['person']}: {g.get('reason', '')} "
                        f"(推定需要: {g.get('estimated_demand', '中')})"
                    )

        sections.append(
            "\n---\n上記のデータに基づいて、次回の動画を計画してください。\n"
            "特に以下を考慮してください:\n"
            "- トラフィックソースの傾向（検索vs.おすすめ）に最適化したタイトル/テーマ\n"
            "- 視聴者の年齢層・性別に合ったトーン\n"
            "- デバイス比率に合った動画構成（モバイル向けはテンポ良く等）\n"
            "- 登録者獲得率の高い動画の特徴を再現\n"
            "- 最適な投稿時間に公開\n"
        )

        return "\n".join(sections)
