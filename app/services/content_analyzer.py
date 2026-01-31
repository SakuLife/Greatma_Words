"""
Content analyzer for data-driven video generation.
Analyzes YouTube performance data to inform content creation decisions.
"""

import re
from collections import Counter
from typing import Any

from app.services.youtube_analytics import (
    ChannelStats,
    RetentionData,
    SubscriberGrowth,
    VideoStats,
    YouTubeAnalytics,
)
from app.utils.logger import logger


class ContentAnalyzer:
    """Analyzes content performance to guide video generation."""

    def __init__(self):
        """Initialize content analyzer."""
        self.youtube_analytics = YouTubeAnalytics()

    async def analyze_channel_performance(
        self, max_videos: int = 50
    ) -> dict[str, Any]:
        """
        Analyze channel performance to identify successful patterns.

        Args:
            max_videos: Maximum number of videos to analyze

        Returns:
            Analysis results dictionary
        """
        logger.info("Starting channel performance analysis...")

        # Get channel stats
        channel_stats = await self.youtube_analytics.get_channel_stats()

        # Limit videos to analyze
        videos_to_analyze = channel_stats.videos[:max_videos]

        # Calculate performance metrics
        analysis = {
            "channel_info": {
                "channel_name": channel_stats.channel_title,
                "total_videos": channel_stats.video_count,
                "total_subscribers": channel_stats.subscriber_count,
                "total_views": channel_stats.total_view_count,
            },
            "performance_metrics": self._calculate_performance_metrics(videos_to_analyze),
            "topic_analysis": self._analyze_topics(videos_to_analyze),
            "engagement_analysis": self._analyze_engagement(videos_to_analyze),
            "recommendations": self._generate_recommendations(videos_to_analyze),
        }

        logger.info("Channel performance analysis complete")
        return analysis

    def _calculate_performance_metrics(
        self, videos: list[VideoStats]
    ) -> dict[str, Any]:
        """Calculate overall performance metrics."""
        if not videos:
            return {}

        total_views = sum(v.view_count for v in videos)
        total_likes = sum(v.like_count for v in videos)
        total_comments = sum(v.comment_count for v in videos)

        avg_views = total_views / len(videos)
        avg_likes = total_likes / len(videos)
        avg_comments = total_comments / len(videos)
        avg_engagement = sum(v.engagement_rate for v in videos) / len(videos)

        # Find top performers
        top_by_views = sorted(videos, key=lambda v: v.view_count, reverse=True)[:5]
        top_by_engagement = sorted(
            videos, key=lambda v: v.engagement_rate, reverse=True
        )[:5]

        return {
            "total_videos_analyzed": len(videos),
            "average_views": avg_views,
            "average_likes": avg_likes,
            "average_comments": avg_comments,
            "average_engagement_rate": avg_engagement,
            "top_videos_by_views": [
                {
                    "title": v.title,
                    "views": v.view_count,
                    "likes": v.like_count,
                    "engagement": v.engagement_rate,
                }
                for v in top_by_views
            ],
            "top_videos_by_engagement": [
                {
                    "title": v.title,
                    "views": v.view_count,
                    "engagement": v.engagement_rate,
                }
                for v in top_by_engagement
            ],
        }

    def _analyze_topics(self, videos: list[VideoStats]) -> dict[str, Any]:
        """Analyze what topics/themes are performing well."""
        # Extract keywords from titles
        all_words = []
        for video in videos:
            # タイトルから単語を抽出（簡易的）
            words = re.findall(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+", video.title)
            all_words.extend(words)

        # Count word frequency
        word_counts = Counter(all_words)
        common_words = word_counts.most_common(20)

        # 人物名を抽出（タイトルに含まれる）
        person_patterns = []
        for video in videos:
            # タイトルの最初の部分が人物名の可能性が高い
            parts = video.title.split("・")
            if parts:
                person_patterns.append(parts[0].strip())

        person_counts = Counter(person_patterns)
        common_persons = person_counts.most_common(10)

        # トピック別のパフォーマンス
        topic_performance = {}
        for person, count in common_persons:
            person_videos = [v for v in videos if person in v.title]
            if person_videos:
                avg_views = sum(v.view_count for v in person_videos) / len(person_videos)
                avg_engagement = (
                    sum(v.engagement_rate for v in person_videos) / len(person_videos)
                )
                topic_performance[person] = {
                    "video_count": count,
                    "avg_views": avg_views,
                    "avg_engagement": avg_engagement,
                }

        return {
            "common_keywords": [
                {"word": word, "count": count} for word, count in common_words
            ],
            "common_persons": [
                {"person": person, "count": count} for person, count in common_persons
            ],
            "topic_performance": topic_performance,
        }

    def _analyze_engagement(self, videos: list[VideoStats]) -> dict[str, Any]:
        """Analyze engagement patterns."""
        if not videos:
            return {}

        # Engagement rate distribution
        high_engagement = [v for v in videos if v.engagement_rate > 3.0]  # 3%以上
        medium_engagement = [
            v for v in videos if 1.0 <= v.engagement_rate <= 3.0
        ]  # 1-3%
        low_engagement = [v for v in videos if v.engagement_rate < 1.0]  # 1%未満

        # タグ分析
        all_tags = []
        for video in videos:
            all_tags.extend(video.tags)

        tag_counts = Counter(all_tags)
        common_tags = tag_counts.most_common(15)

        return {
            "engagement_distribution": {
                "high": len(high_engagement),
                "medium": len(medium_engagement),
                "low": len(low_engagement),
            },
            "high_engagement_videos": [
                {"title": v.title, "engagement": v.engagement_rate}
                for v in high_engagement[:5]
            ],
            "common_tags": [{"tag": tag, "count": count} for tag, count in common_tags],
        }

    def _generate_recommendations(self, videos: list[VideoStats]) -> dict[str, Any]:
        """Generate content recommendations based on analysis."""
        if not videos:
            return {}

        # パフォーマンスの高い動画の特徴を抽出
        top_videos = sorted(videos, key=lambda v: v.view_count, reverse=True)[:10]

        # 共通するキーワードを抽出
        top_words = []
        for video in top_videos:
            words = re.findall(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+", video.title)
            top_words.extend(words)

        top_word_counts = Counter(top_words)
        recommended_keywords = [word for word, count in top_word_counts.most_common(10)]

        # 平均以上のパフォーマンスを出している人物を抽出
        avg_views = sum(v.view_count for v in videos) / len(videos)
        person_performance = {}

        for video in videos:
            parts = video.title.split("・")
            if parts:
                person = parts[0].strip()
                if person not in person_performance:
                    person_performance[person] = {
                        "videos": [],
                        "total_views": 0,
                        "total_engagement": 0.0,
                    }
                person_performance[person]["videos"].append(video)
                person_performance[person]["total_views"] += video.view_count
                person_performance[person]["total_engagement"] += video.engagement_rate

        # 平均以上のパフォーマンスを出している人物
        recommended_persons = []
        for person, data in person_performance.items():
            avg_person_views = data["total_views"] / len(data["videos"])
            if avg_person_views >= avg_views:
                recommended_persons.append(
                    {
                        "person": person,
                        "video_count": len(data["videos"]),
                        "avg_views": avg_person_views,
                        "avg_engagement": data["total_engagement"]
                        / len(data["videos"]),
                    }
                )

        # 視聴回数でソート
        recommended_persons.sort(key=lambda x: x["avg_views"], reverse=True)

        return {
            "recommended_keywords": recommended_keywords,
            "recommended_persons": recommended_persons[:10],
            "optimal_video_length": self._estimate_optimal_length(top_videos),
            "suggested_themes": self._suggest_themes(top_videos),
        }

    def _estimate_optimal_length(self, videos: list[VideoStats]) -> str:
        """Estimate optimal video length based on top performers."""
        # ISO 8601形式のdurationを秒数に変換（簡易版）
        # 例: PT15M33S -> 15分33秒
        durations = []
        for video in videos:
            duration_str = video.duration
            minutes = 0
            seconds = 0

            # PT15M33S形式をパース
            if "M" in duration_str:
                minutes_part = duration_str.split("M")[0].replace("PT", "")
                if minutes_part:
                    minutes = int(minutes_part)

            if "S" in duration_str:
                seconds_part = duration_str.split("M")[-1].replace("S", "").replace("PT", "")
                if seconds_part and seconds_part.isdigit():
                    seconds = int(seconds_part)

            total_seconds = minutes * 60 + seconds
            if total_seconds > 0:
                durations.append(total_seconds)

        if not durations:
            return "15-20分（データ不足のため推奨値）"

        avg_duration = sum(durations) / len(durations)
        avg_minutes = int(avg_duration // 60)

        return f"{avg_minutes-2}-{avg_minutes+2}分"

    def _suggest_themes(self, videos: list[VideoStats]) -> list[str]:
        """Suggest themes based on high-performing videos."""
        themes = []

        # タイトルから一般的なテーマを抽出
        theme_keywords = [
            "経営", "哲学", "思考", "戦略", "成功", "リーダーシップ",
            "AI", "時代", "未来", "仕事", "人生", "ビジネス"
        ]

        theme_counts = {theme: 0 for theme in theme_keywords}

        for video in videos:
            for theme in theme_keywords:
                if theme in video.title or theme in video.description:
                    theme_counts[theme] += 1

        # カウントが多い順にソート
        sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)

        # 上位5つのテーマを返す
        themes = [theme for theme, count in sorted_themes[:5] if count > 0]

        return themes if themes else ["経営哲学", "AI時代の思考法", "成功の法則"]

    async def _get_advanced_analytics(self) -> dict:
        """
        Analytics API v2から高度な分析データを取得

        Returns:
            登録者推移・注目動画・維持率のデータ
        """
        result: dict = {
            "subscriber_growth": [],
            "trending_videos": [],
            "retention_insights": [],
        }

        try:
            # 登録者推移（7日間）
            growth = await self.youtube_analytics.get_subscriber_growth(days=7)
            result["subscriber_growth"] = growth
            logger.info(f"登録者推移取得: {len(growth)}日分")
        except Exception as e:
            logger.warning(f"登録者推移の取得に失敗（スキップ）: {e}")

        try:
            # 注目動画
            trending = await self.youtube_analytics.detect_trending_videos(days=7)
            result["trending_videos"] = trending
            logger.info(f"注目動画検出: {len(trending)}件")
        except Exception as e:
            logger.warning(f"注目動画の検出に失敗（スキップ）: {e}")

        # 注目動画の維持率
        for video in result["trending_videos"][:3]:
            try:
                ret = await self.youtube_analytics.get_audience_retention(
                    video["video_id"]
                )
                result["retention_insights"].append(
                    {
                        "video_id": video["video_id"],
                        "title": video.get("title", ""),
                        "average_retention": ret.average_retention,
                    }
                )
            except Exception as e:
                logger.warning(f"維持率取得失敗 ({video['video_id']}): {e}")

        return result

    async def get_content_suggestions_for_llm(self) -> str:
        """
        Get content suggestions formatted for LLM input.
        Analytics API v2の高度な分析データも含む。

        Returns:
            Formatted string with analysis and recommendations
        """
        analysis = await self.analyze_channel_performance()

        # Analytics API v2データを取得（失敗しても基本分析は続行）
        advanced = await self._get_advanced_analytics()

        # LLM用にフォーマット
        suggestions = f"""
# YouTube チャンネル分析結果

## チャンネル概要
- チャンネル名: {analysis['channel_info']['channel_name']}
- 総動画数: {analysis['channel_info']['total_videos']}
- 登録者数: {analysis['channel_info']['total_subscribers']:,}
- 総視聴回数: {analysis['channel_info']['total_views']:,}

## パフォーマンス指標
- 平均視聴回数: {analysis['performance_metrics']['average_views']:.0f}
- 平均いいね数: {analysis['performance_metrics']['average_likes']:.0f}
- 平均エンゲージメント率: {analysis['performance_metrics']['average_engagement_rate']:.2f}%

## トップパフォーマンス動画（視聴回数）
"""

        for i, video in enumerate(
            analysis['performance_metrics']['top_videos_by_views'][:5], 1
        ):
            suggestions += f"{i}. {video['title']} ({video['views']:,} views, {video['engagement']:.2f}% engagement)\n"

        # 登録者推移セクション
        if advanced["subscriber_growth"]:
            total_gained = sum(s.gained for s in advanced["subscriber_growth"])
            total_lost = sum(s.lost for s in advanced["subscriber_growth"])
            net = total_gained - total_lost
            suggestions += f"""
## チャンネル登録者推移（直近7日間）
- 新規登録: +{total_gained}人
- 解除: -{total_lost}人
- 純増減: {"+" if net >= 0 else ""}{net}人
"""

        # 注目動画セクション
        if advanced["trending_videos"]:
            suggestions += "\n## 今週伸びている動画（前週比）\n"
            for t in advanced["trending_videos"][:5]:
                growth_str = (
                    f"{t['growth_rate']:.1f}倍"
                    if t.get("growth_rate", 0) != float("inf")
                    else "新規"
                )
                suggestions += (
                    f"- {t.get('title', t['video_id'])}: "
                    f"成長率{growth_str} ({t['previous_views']}→{t['current_views']}再生)\n"
                )

        # 維持率インサイト
        if advanced["retention_insights"]:
            suggestions += "\n## 視聴維持率（注目動画）\n"
            for r in advanced["retention_insights"]:
                suggestions += (
                    f"- {r['title'][:30]}: 平均維持率{r['average_retention']:.1f}%\n"
                )

        suggestions += f"""
## 推奨キーワード
{', '.join(analysis['recommendations']['recommended_keywords'][:10])}

## 推奨する人物（過去のパフォーマンスが高い）
"""

        for person in analysis['recommendations']['recommended_persons'][:5]:
            suggestions += f"- {person['person']}: 平均{person['avg_views']:.0f}回視聴, {person['avg_engagement']:.2f}% エンゲージメント\n"

        suggestions += f"""
## 推奨動画長
{analysis['recommendations']['optimal_video_length']}

## 推奨テーマ
{', '.join(analysis['recommendations']['suggested_themes'])}

---

上記のデータに基づいて、次回の動画を計画してください。
伸びている動画のテーマや視聴維持率の高い動画の特徴を参考に、
視聴者が興味を持ち、高いエンゲージメントが期待できるテーマと人物を選んでください。
登録者推移も考慮し、チャンネルの成長に寄与するコンテンツを提案してください。
"""

        return suggestions
