"""
YouTube analytics service for fetching video statistics.
Uses YouTube Data API v3 and YouTube Analytics API v2.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config import settings
from app.models.analytics_models import (
    CompetitorVideo,
    DemographicData,
    DemographicSummary,
    DeviceData,
    TrafficSourceData,
    VideoSubscriberImpact,
)
from app.utils.logger import logger


@dataclass
class VideoStats:
    """Statistics for a single video."""

    video_id: str
    title: str
    description: str
    published_at: datetime
    view_count: int
    like_count: int
    comment_count: int
    duration: str
    tags: list[str]

    @property
    def engagement_rate(self) -> float:
        """Calculate engagement rate (likes per view)."""
        if self.view_count == 0:
            return 0.0
        return (self.like_count / self.view_count) * 100


@dataclass
class ChannelStats:
    """Overall channel statistics."""

    channel_id: str
    channel_title: str
    subscriber_count: int
    total_view_count: int
    video_count: int
    videos: list[VideoStats]

    @property
    def avg_views_per_video(self) -> float:
        """Calculate average views per video."""
        if self.video_count == 0:
            return 0.0
        return self.total_view_count / self.video_count

    @property
    def top_videos(self, limit: int = 10) -> list[VideoStats]:
        """Get top videos by view count."""
        return sorted(self.videos, key=lambda v: v.view_count, reverse=True)[:limit]


@dataclass
class SubscriberGrowth:
    """日別のチャンネル登録者変動"""

    date: str
    gained: int
    lost: int

    @property
    def net(self) -> int:
        """純増減"""
        return self.gained - self.lost


@dataclass
class RetentionData:
    """動画の視聴維持率データ"""

    video_id: str
    retention_points: list[dict] = field(default_factory=list)  # [{elapsed_ratio, watch_ratio}]

    @property
    def average_retention(self) -> float:
        """平均視聴維持率"""
        if not self.retention_points:
            return 0.0
        return sum(p["watch_ratio"] for p in self.retention_points) / len(
            self.retention_points
        )


@dataclass
class VideoCTR:
    """動画のCTR（クリック率）データ"""

    video_id: str
    impressions: int
    ctr: float  # パーセント
    date: str = ""  # 日別取得時に使用


class YouTubeAnalytics:
    """Fetches and analyzes YouTube channel statistics."""

    def __init__(self):
        """Initialize YouTube analytics service."""
        # Accept scopes as space-delimited string in settings and normalize to list
        if isinstance(settings.youtube_oauth_scopes, str):
            self.scopes = settings.youtube_oauth_scopes.split()
        else:
            self.scopes = list(settings.youtube_oauth_scopes)
        self.client_secrets_file = settings.youtube_client_secrets_file
        self.credentials = None
        self.youtube_service = None
        self.analytics_service = None

    async def authenticate(self, token_file: str = "token.json") -> None:
        """
        Authenticate with YouTube API using OAuth 2.0.

        Args:
            token_file: Path to store/load OAuth token

        Raises:
            RuntimeError: If authentication fails
        """
        logger.info("Authenticating with YouTube API for analytics")

        try:
            # Load credentials from token file if it exists
            if os.path.exists(token_file):
                self.credentials = Credentials.from_authorized_user_file(
                    token_file, self.scopes
                )

            # If credentials don't exist or are invalid, get new ones
            if not self.credentials or not self.credentials.valid:
                if (
                    self.credentials
                    and self.credentials.expired
                    and self.credentials.refresh_token
                ):
                    logger.info("Refreshing expired credentials")
                    self.credentials.refresh(Request())
                else:
                    if not os.path.exists(self.client_secrets_file):
                        raise FileNotFoundError(
                            f"Client secrets file not found: {self.client_secrets_file}"
                        )

                    logger.info("Starting OAuth flow")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.client_secrets_file, self.scopes
                    )
                    self.credentials = flow.run_local_server(port=0)

                # Save credentials for future use
                with open(token_file, "w") as token:
                    token.write(self.credentials.to_json())

            # Build YouTube Data API v3 service
            self.youtube_service = build("youtube", "v3", credentials=self.credentials)

            # Build YouTube Analytics API v2 service
            self._build_analytics_service()

            logger.info("YouTube API authentication successful")

        except Exception as e:
            logger.error(f"YouTube authentication failed: {e}")
            raise RuntimeError(f"Failed to authenticate with YouTube: {e}") from e

    async def get_my_channel_id(self) -> str:
        """
        Get the authenticated user's channel ID.

        Returns:
            Channel ID

        Raises:
            RuntimeError: If channel retrieval fails
        """
        if not self.youtube_service:
            await self.authenticate()

        try:
            request = self.youtube_service.channels().list(
                part="id,snippet",
                mine=True
            )
            response = request.execute()

            if not response.get("items"):
                raise RuntimeError("No channel found for authenticated user")

            channel_id = response["items"][0]["id"]
            channel_title = response["items"][0]["snippet"]["title"]

            logger.info(f"Found channel: {channel_title} (ID: {channel_id})")
            return channel_id

        except Exception as e:
            logger.error(f"Failed to get channel ID: {e}")
            raise RuntimeError(f"Failed to get channel ID: {e}") from e

    async def get_channel_stats(self, channel_id: str | None = None) -> ChannelStats:
        """
        Get overall channel statistics.

        Args:
            channel_id: Channel ID (uses authenticated user's channel if None)

        Returns:
            ChannelStats object

        Raises:
            RuntimeError: If stats retrieval fails
        """
        if not self.youtube_service:
            await self.authenticate()

        try:
            # Get channel ID if not provided
            if not channel_id:
                channel_id = await self.get_my_channel_id()

            # Get channel details
            request = self.youtube_service.channels().list(
                part="snippet,statistics",
                id=channel_id
            )
            response = request.execute()

            if not response.get("items"):
                raise RuntimeError(f"Channel not found: {channel_id}")

            channel_data = response["items"][0]
            snippet = channel_data["snippet"]
            stats = channel_data["statistics"]

            logger.info(f"Retrieved stats for channel: {snippet['title']}")
            logger.info(f"  Subscribers: {stats.get('subscriberCount', 'N/A')}")
            logger.info(f"  Total Views: {stats.get('viewCount', 0)}")
            logger.info(f"  Videos: {stats.get('videoCount', 0)}")

            # Get all videos from channel
            videos = await self.get_all_videos(channel_id)

            return ChannelStats(
                channel_id=channel_id,
                channel_title=snippet["title"],
                subscriber_count=int(stats.get("subscriberCount", 0)),
                total_view_count=int(stats.get("viewCount", 0)),
                video_count=int(stats.get("videoCount", 0)),
                videos=videos,
            )

        except Exception as e:
            logger.error(f"Failed to get channel stats: {e}")
            raise RuntimeError(f"Failed to get channel stats: {e}") from e

    async def get_all_videos(
        self, channel_id: str, max_results: int = 50
    ) -> list[VideoStats]:
        """
        Get all videos from a channel.

        Args:
            channel_id: Channel ID
            max_results: Maximum number of videos to retrieve

        Returns:
            List of VideoStats objects
        """
        if not self.youtube_service:
            await self.authenticate()

        try:
            videos = []
            next_page_token = None

            while len(videos) < max_results:
                # Search for videos in channel
                request = self.youtube_service.search().list(
                    part="id,snippet",
                    channelId=channel_id,
                    maxResults=min(50, max_results - len(videos)),
                    order="date",  # Most recent first
                    type="video",
                    pageToken=next_page_token
                )
                response = request.execute()

                video_ids = [item["id"]["videoId"] for item in response.get("items", [])]

                if not video_ids:
                    break

                # Get detailed stats for these videos
                video_stats = await self.get_video_stats(video_ids)
                videos.extend(video_stats)

                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break

            logger.info(f"Retrieved {len(videos)} videos from channel")
            return videos

        except Exception as e:
            logger.error(f"Failed to get videos: {e}")
            raise RuntimeError(f"Failed to get videos: {e}") from e

    async def get_video_stats(self, video_ids: list[str]) -> list[VideoStats]:
        """
        Get statistics for specific videos.

        Args:
            video_ids: List of video IDs

        Returns:
            List of VideoStats objects
        """
        if not self.youtube_service:
            await self.authenticate()

        try:
            # Get video details (up to 50 at a time)
            request = self.youtube_service.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(video_ids)
            )
            response = request.execute()

            video_stats = []
            for item in response.get("items", []):
                snippet = item["snippet"]
                stats = item["statistics"]
                content_details = item["contentDetails"]

                video_stat = VideoStats(
                    video_id=item["id"],
                    title=snippet["title"],
                    description=snippet["description"],
                    published_at=datetime.fromisoformat(
                        snippet["publishedAt"].replace("Z", "+00:00")
                    ),
                    view_count=int(stats.get("viewCount", 0)),
                    like_count=int(stats.get("likeCount", 0)),
                    comment_count=int(stats.get("commentCount", 0)),
                    duration=content_details["duration"],
                    tags=snippet.get("tags", []),
                )
                video_stats.append(video_stat)

            return video_stats

        except Exception as e:
            logger.error(f"Failed to get video stats: {e}")
            raise RuntimeError(f"Failed to get video stats: {e}") from e

    async def analyze_top_performers(
        self, channel_id: str | None = None, top_n: int = 10
    ) -> dict:
        """
        Analyze top performing videos to identify patterns.

        Args:
            channel_id: Channel ID (uses authenticated user's channel if None)
            top_n: Number of top videos to analyze

        Returns:
            Dictionary with analysis results
        """
        channel_stats = await self.get_channel_stats(channel_id)

        # Get top videos by views
        top_videos = sorted(
            channel_stats.videos, key=lambda v: v.view_count, reverse=True
        )[:top_n]

        # Analyze patterns
        total_views = sum(v.view_count for v in top_videos)
        avg_views = total_views / len(top_videos) if top_videos else 0
        avg_likes = sum(v.like_count for v in top_videos) / len(top_videos) if top_videos else 0
        avg_engagement = sum(v.engagement_rate for v in top_videos) / len(top_videos) if top_videos else 0

        # Extract common tags
        all_tags = []
        for video in top_videos:
            all_tags.extend(video.tags)

        tag_counts = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

        common_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        analysis = {
            "total_videos_analyzed": len(top_videos),
            "avg_views": avg_views,
            "avg_likes": avg_likes,
            "avg_engagement_rate": avg_engagement,
            "top_videos": [
                {
                    "title": v.title,
                    "views": v.view_count,
                    "likes": v.like_count,
                    "engagement_rate": v.engagement_rate,
                    "url": f"https://www.youtube.com/watch?v={v.video_id}",
                }
                for v in top_videos
            ],
            "common_tags": [{"tag": tag, "count": count} for tag, count in common_tags],
        }

        logger.info("=" * 60)
        logger.info(f"[YouTube分析結果] Top {top_n} videos")
        logger.info(f"  平均再生数: {avg_views:.0f}")
        logger.info(f"  平均高評価: {avg_likes:.0f}")
        logger.info(f"  平均エンゲージメント率: {avg_engagement:.2f}%")
        logger.info("-" * 40)
        logger.info("[動画パフォーマンス一覧]")
        for i, v in enumerate(top_videos, 1):
            logger.info(f"  {i}. {v.title[:40]}...")
            logger.info(f"     再生数: {v.view_count:,} / 高評価: {v.like_count:,} / エンゲージメント: {v.engagement_rate:.2f}%")
        logger.info("=" * 60)

        return analysis

    # ========================================
    # YouTube Analytics API v2 メソッド
    # ========================================

    def _build_analytics_service(self) -> None:
        """YouTube Analytics API v2サービスを構築"""
        try:
            self.analytics_service = build(
                "youtubeAnalytics", "v2", credentials=self.credentials
            )
            logger.info("YouTube Analytics API v2 サービス構築完了")
        except Exception as e:
            logger.warning(f"Analytics API v2の構築に失敗（Data API v3は利用可能）: {e}")
            self.analytics_service = None

    async def _ensure_analytics_service(self) -> None:
        """Analytics APIサービスが利用可能か確認し、なければ認証"""
        if not self.analytics_service:
            await self.authenticate()
        if not self.analytics_service:
            raise RuntimeError("YouTube Analytics API v2が利用できません")

    async def get_subscriber_growth(
        self, days: int = 7
    ) -> list[SubscriberGrowth]:
        """
        チャンネル登録者の日別増減を取得

        Args:
            days: 取得する日数（デフォルト7日）

        Returns:
            日別の登録者変動リスト
        """
        await self._ensure_analytics_service()

        end_date = datetime.now() - timedelta(days=2)  # データ遅延を考慮
        start_date = end_date - timedelta(days=days - 1)

        try:
            response = self.analytics_service.reports().query(
                ids="channel==MINE",
                startDate=start_date.strftime("%Y-%m-%d"),
                endDate=end_date.strftime("%Y-%m-%d"),
                metrics="subscribersGained,subscribersLost",
                dimensions="day",
                sort="day",
            ).execute()

            results = []
            for row in response.get("rows", []):
                results.append(
                    SubscriberGrowth(
                        date=row[0],
                        gained=int(row[1]),
                        lost=int(row[2]),
                    )
                )

            total_gained = sum(r.gained for r in results)
            total_lost = sum(r.lost for r in results)
            logger.info(
                f"登録者推移（{days}日間）: +{total_gained} / -{total_lost} = 純増{total_gained - total_lost}"
            )

            return results

        except Exception as e:
            logger.error(f"登録者推移の取得に失敗: {e}")
            raise RuntimeError(f"登録者推移の取得に失敗: {e}") from e

    async def get_audience_retention(self, video_id: str) -> RetentionData:
        """
        動画の視聴維持率を取得

        Args:
            video_id: YouTube動画ID

        Returns:
            視聴維持率データ
        """
        await self._ensure_analytics_service()

        try:
            response = self.analytics_service.reports().query(
                ids="channel==MINE",
                startDate="2020-01-01",
                endDate=datetime.now().strftime("%Y-%m-%d"),
                metrics="audienceWatchRatio",
                dimensions="elapsedVideoTimeRatio",
                filters=f"video=={video_id}",
                sort="elapsedVideoTimeRatio",
            ).execute()

            points = []
            for row in response.get("rows", []):
                points.append(
                    {
                        "elapsed_ratio": float(row[0]),
                        "watch_ratio": float(row[1]),
                    }
                )

            retention = RetentionData(video_id=video_id, retention_points=points)
            logger.info(
                f"視聴維持率取得: {video_id} - 平均{retention.average_retention:.1f}%"
            )

            return retention

        except Exception as e:
            logger.error(f"視聴維持率の取得に失敗 ({video_id}): {e}")
            raise RuntimeError(f"視聴維持率の取得に失敗: {e}") from e

    async def get_video_ctr(
        self, video_id: str, start_date: str, end_date: str
    ) -> list[VideoCTR]:
        """
        動画のインプレッション・CTRを日別に取得

        Args:
            video_id: YouTube動画ID
            start_date: 開始日 (YYYY-MM-DD)
            end_date: 終了日 (YYYY-MM-DD)

        Returns:
            日別のCTRデータリスト
        """
        await self._ensure_analytics_service()

        try:
            response = self.analytics_service.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="impressions,impressionClickThroughRate",
                dimensions="day",
                filters=f"video=={video_id}",
                sort="day",
            ).execute()

            results = []
            for row in response.get("rows", []):
                results.append(
                    VideoCTR(
                        video_id=video_id,
                        date=row[0],
                        impressions=int(row[1]),
                        ctr=float(row[2]),
                    )
                )

            if results:
                total_imp = sum(r.impressions for r in results)
                avg_ctr = sum(r.ctr for r in results) / len(results)
                logger.info(
                    f"CTR取得: {video_id} - {total_imp}インプレッション, 平均CTR {avg_ctr:.2f}%"
                )

            return results

        except Exception as e:
            logger.error(f"CTRの取得に失敗 ({video_id}): {e}")
            raise RuntimeError(f"CTRの取得に失敗: {e}") from e

    async def get_bulk_video_ctr(
        self, start_date: str, end_date: str
    ) -> list[VideoCTR]:
        """
        全動画のCTRをまとめて取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            end_date: 終了日 (YYYY-MM-DD)

        Returns:
            動画別のCTRデータリスト
        """
        await self._ensure_analytics_service()

        try:
            response = self.analytics_service.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="impressions,impressionClickThroughRate",
                dimensions="video",
                sort="-impressions",
            ).execute()

            results = []
            for row in response.get("rows", []):
                results.append(
                    VideoCTR(
                        video_id=row[0],
                        impressions=int(row[1]),
                        ctr=float(row[2]),
                    )
                )

            logger.info(f"全動画CTR取得: {len(results)}件")
            return results

        except Exception as e:
            logger.error(f"全動画CTRの取得に失敗: {e}")
            raise RuntimeError(f"全動画CTRの取得に失敗: {e}") from e

    async def detect_trending_videos(
        self, days: int = 7, growth_threshold: float = 1.5
    ) -> list[dict]:
        """
        伸びている動画を検出（前期間比で視聴回数増加率が閾値以上）

        Args:
            days: 比較期間（日数）
            growth_threshold: 成長率の閾値（1.5 = 前期間の1.5倍以上）

        Returns:
            伸びている動画のリスト [{video_id, title, current_views, previous_views, growth_rate}]
        """
        await self._ensure_analytics_service()

        end_date = datetime.now() - timedelta(days=2)
        mid_date = end_date - timedelta(days=days)
        start_date = mid_date - timedelta(days=days)

        try:
            # 今期間の視聴回数
            current_response = self.analytics_service.reports().query(
                ids="channel==MINE",
                startDate=mid_date.strftime("%Y-%m-%d"),
                endDate=end_date.strftime("%Y-%m-%d"),
                metrics="views",
                dimensions="video",
                sort="-views",
                maxResults=50,
            ).execute()

            current_views: dict[str, int] = {}
            for row in current_response.get("rows", []):
                current_views[row[0]] = int(row[1])

            # 前期間の視聴回数
            previous_response = self.analytics_service.reports().query(
                ids="channel==MINE",
                startDate=start_date.strftime("%Y-%m-%d"),
                endDate=mid_date.strftime("%Y-%m-%d"),
                metrics="views",
                dimensions="video",
                sort="-views",
                maxResults=50,
            ).execute()

            previous_views: dict[str, int] = {}
            for row in previous_response.get("rows", []):
                previous_views[row[0]] = int(row[1])

            # 成長率を計算
            trending = []
            for video_id, curr in current_views.items():
                prev = previous_views.get(video_id, 0)
                if prev > 0:
                    growth_rate = curr / prev
                elif curr > 0:
                    growth_rate = float("inf")
                else:
                    continue

                if growth_rate >= growth_threshold:
                    trending.append(
                        {
                            "video_id": video_id,
                            "current_views": curr,
                            "previous_views": prev,
                            "growth_rate": growth_rate,
                        }
                    )

            # タイトルを取得
            if trending and self.youtube_service:
                video_ids = [t["video_id"] for t in trending]
                stats = await self.get_video_stats(video_ids)
                title_map = {s.video_id: s.title for s in stats}
                for t in trending:
                    t["title"] = title_map.get(t["video_id"], "不明")

            trending.sort(key=lambda x: x["growth_rate"], reverse=True)

            logger.info(f"注目動画検出: {len(trending)}件（成長率{growth_threshold}倍以上）")
            for t in trending[:5]:
                logger.info(
                    f"  {t.get('title', t['video_id'])[:30]} - "
                    f"成長率{t['growth_rate']:.1f}倍 ({t['previous_views']}→{t['current_views']})"
                )

            return trending

        except Exception as e:
            logger.error(f"注目動画の検出に失敗: {e}")
            raise RuntimeError(f"注目動画の検出に失敗: {e}") from e

    # ========================================
    # 包括的チャンネル分析メソッド (Phase 1)
    # ========================================

    async def get_traffic_sources(
        self, start_date: str, end_date: str
    ) -> list[TrafficSourceData]:
        """
        トラフィックソース別の視聴データを取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            end_date: 終了日 (YYYY-MM-DD)

        Returns:
            トラフィックソース別データのリスト
        """
        await self._ensure_analytics_service()

        try:
            response = self.analytics_service.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="views,estimatedMinutesWatched",
                dimensions="insightTrafficSourceType",
                sort="-views",
            ).execute()

            total_views = sum(int(row[1]) for row in response.get("rows", []))
            results = []
            for row in response.get("rows", []):
                views = int(row[1])
                results.append(
                    TrafficSourceData(
                        source_type=row[0],
                        views=views,
                        watch_time_minutes=float(row[2]),
                        percentage=round(views / total_views * 100, 1) if total_views else 0,
                    )
                )

            logger.info(f"トラフィックソース取得: {len(results)}種類")
            for r in results[:5]:
                logger.info(f"  {r.source_type}: {r.views:,} views ({r.percentage}%)")

            return results

        except Exception as e:
            logger.error(f"トラフィックソースの取得に失敗: {e}")
            raise RuntimeError(f"トラフィックソースの取得に失敗: {e}") from e

    async def get_demographics(
        self, start_date: str, end_date: str
    ) -> DemographicSummary:
        """
        年齢・性別別の視聴者データを取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            end_date: 終了日 (YYYY-MM-DD)

        Returns:
            デモグラフィックサマリー
        """
        await self._ensure_analytics_service()

        try:
            response = self.analytics_service.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="viewerPercentage",
                dimensions="ageGroup,gender",
                sort="-viewerPercentage",
            ).execute()

            details = []
            for row in response.get("rows", []):
                details.append(
                    DemographicData(
                        age_group=row[0],
                        gender=row[1],
                        views=0,  # viewerPercentageは割合なのでviews=0
                        percentage=float(row[2]),
                    )
                )

            summary = DemographicSummary(details=details)
            logger.info(f"デモグラフィック取得: {len(details)}セグメント")
            logger.info(f"  主要年齢層: {summary.top_age_group}")

            return summary

        except Exception as e:
            logger.error(f"デモグラフィックの取得に失敗: {e}")
            raise RuntimeError(f"デモグラフィックの取得に失敗: {e}") from e

    async def get_device_breakdown(
        self, start_date: str, end_date: str
    ) -> list[DeviceData]:
        """
        デバイス別の視聴データを取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            end_date: 終了日 (YYYY-MM-DD)

        Returns:
            デバイス別データのリスト
        """
        await self._ensure_analytics_service()

        try:
            response = self.analytics_service.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="views,estimatedMinutesWatched",
                dimensions="deviceType",
                sort="-views",
            ).execute()

            total_views = sum(int(row[1]) for row in response.get("rows", []))
            results = []
            for row in response.get("rows", []):
                views = int(row[1])
                results.append(
                    DeviceData(
                        device_type=row[0],
                        views=views,
                        watch_time_minutes=float(row[2]),
                        percentage=round(views / total_views * 100, 1) if total_views else 0,
                    )
                )

            logger.info(f"デバイス別取得: {len(results)}種類")
            for r in results[:3]:
                logger.info(f"  {r.device_type}: {r.views:,} views ({r.percentage}%)")

            return results

        except Exception as e:
            logger.error(f"デバイス別データの取得に失敗: {e}")
            raise RuntimeError(f"デバイス別データの取得に失敗: {e}") from e

    async def get_video_subscriber_impact(
        self, start_date: str, end_date: str
    ) -> list[VideoSubscriberImpact]:
        """
        動画ごとの登録者獲得・離脱データを取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            end_date: 終了日 (YYYY-MM-DD)

        Returns:
            動画ごとの登録者影響データリスト
        """
        await self._ensure_analytics_service()

        try:
            response = self.analytics_service.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="subscribersGained,subscribersLost,views,estimatedMinutesWatched",
                dimensions="video",
                sort="-subscribersGained",
                maxResults=50,
            ).execute()

            results = []
            for row in response.get("rows", []):
                results.append(
                    VideoSubscriberImpact(
                        video_id=row[0],
                        title="",  # タイトルは後で付与
                        subscribers_gained=int(row[1]),
                        subscribers_lost=int(row[2]),
                        views=int(row[3]),
                        estimated_minutes_watched=float(row[4]),
                    )
                )

            # Data API v3でタイトルを取得
            if results and self.youtube_service:
                video_ids = [r.video_id for r in results]
                stats = await self.get_video_stats(video_ids)
                title_map = {s.video_id: s.title for s in stats}
                for r in results:
                    r.title = title_map.get(r.video_id, "不明")

            logger.info(f"動画別登録者影響取得: {len(results)}件")
            for r in results[:5]:
                logger.info(
                    f"  {r.title[:30]}: +{r.subscribers_gained}/-{r.subscribers_lost} "
                    f"(純増{r.net_subscribers})"
                )

            return results

        except Exception as e:
            logger.error(f"動画別登録者影響の取得に失敗: {e}")
            raise RuntimeError(f"動画別登録者影響の取得に失敗: {e}") from e

    async def get_daily_views_for_video(
        self, video_id: str, start_date: str, end_date: str
    ) -> list[dict]:
        """
        動画の日別再生数を取得（初動分析用）

        Args:
            video_id: YouTube動画ID
            start_date: 開始日 (YYYY-MM-DD)
            end_date: 終了日 (YYYY-MM-DD)

        Returns:
            日別再生数のリスト [{date, views}]
        """
        await self._ensure_analytics_service()

        try:
            response = self.analytics_service.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="views",
                dimensions="day",
                filters=f"video=={video_id}",
                sort="day",
            ).execute()

            results = []
            for row in response.get("rows", []):
                results.append({"date": row[0], "views": int(row[1])})

            total = sum(r["views"] for r in results)
            logger.info(f"日別再生数取得: {video_id} - {len(results)}日分, 合計{total}再生")

            return results

        except Exception as e:
            logger.error(f"日別再生数の取得に失敗 ({video_id}): {e}")
            raise RuntimeError(f"日別再生数の取得に失敗: {e}") from e

    async def search_niche_videos(
        self,
        query: str,
        max_results: int = 25,
        order: str = "viewCount",
        published_after: str | None = None,
    ) -> list[CompetitorVideo]:
        """
        YouTube Data API v3のsearch.listで競合動画を検索

        Args:
            query: 検索クエリ
            max_results: 最大取得件数
            order: ソート順 (viewCount, date, relevance)
            published_after: この日付以降の動画のみ (ISO 8601形式)

        Returns:
            競合動画のリスト
        """
        if not self.youtube_service:
            await self.authenticate()

        try:
            search_params: dict = {
                "part": "id,snippet",
                "q": query,
                "type": "video",
                "maxResults": min(max_results, 50),
                "order": order,
                "relevanceLanguage": "ja",
                "regionCode": "JP",
            }

            if published_after:
                search_params["publishedAfter"] = published_after

            response = self.youtube_service.search().list(**search_params).execute()

            video_ids = [item["id"]["videoId"] for item in response.get("items", [])]
            if not video_ids:
                logger.info(f"検索結果なし: {query}")
                return []

            # 詳細統計を取得
            detail_response = self.youtube_service.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(video_ids),
            ).execute()

            results = []
            for item in detail_response.get("items", []):
                snippet = item["snippet"]
                stats = item.get("statistics", {})
                results.append(
                    CompetitorVideo(
                        video_id=item["id"],
                        title=snippet["title"],
                        channel_title=snippet["channelTitle"],
                        channel_id=snippet["channelId"],
                        view_count=int(stats.get("viewCount", 0)),
                        like_count=int(stats.get("likeCount", 0)),
                        published_at=snippet["publishedAt"],
                        duration=item["contentDetails"]["duration"],
                        tags=snippet.get("tags", []),
                        description=snippet.get("description", "")[:200],
                    )
                )

            logger.info(f"競合検索: '{query}' → {len(results)}件")
            for r in results[:3]:
                logger.info(
                    f"  [{r.channel_title}] {r.title[:40]} - {r.view_count:,} views"
                )

            return results

        except Exception as e:
            logger.error(f"競合動画検索に失敗 ({query}): {e}")
            raise RuntimeError(f"競合動画検索に失敗: {e}") from e
