"""
YouTube analytics service for fetching video statistics.
Uses YouTube Data API v3 to analyze channel performance.
"""

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config import settings
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

            # Build YouTube service
            self.youtube_service = build("youtube", "v3", credentials=self.credentials)

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

        logger.info(f"Analysis complete: Top {top_n} videos")
        logger.info(f"  Average views: {avg_views:.0f}")
        logger.info(f"  Average likes: {avg_likes:.0f}")
        logger.info(f"  Average engagement: {avg_engagement:.2f}%")

        return analysis
