"""
YouTube upload service using Google API.
"""

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.config import settings
from app.models.schemas import VideoMetadata
from app.utils.logger import logger


class YouTubeUploader:
    """Uploads videos to YouTube using Google API."""

    def __init__(self):
        """Initialize YouTube uploader."""
        # Accept scopes as space-delimited string in settings and normalize to list
        if isinstance(settings.youtube_oauth_scopes, str):
            self.scopes = settings.youtube_oauth_scopes.split()
        else:
            self.scopes = list(settings.youtube_oauth_scopes)
        self.client_secrets_file = settings.youtube_client_secrets_file
        self.credentials = None
        self.youtube_service = None

    @staticmethod
    def _is_ci_environment() -> bool:
        """CI環境かどうかを判定する。"""
        return any(
            os.environ.get(v)
            for v in ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL")
        )

    async def authenticate(self, token_file: str = "token.json") -> None:
        """
        Authenticate with YouTube API using OAuth 2.0.

        Args:
            token_file: Path to store/load OAuth token

        Raises:
            RuntimeError: If authentication fails
        """
        logger.info("Authenticating with YouTube API")

        try:
            # Load credentials from token file if it exists and is not empty
            if os.path.exists(token_file) and os.path.getsize(token_file) > 0:
                logger.debug(f"Loading credentials from {token_file}")
                self.credentials = Credentials.from_authorized_user_file(
                    token_file, self.scopes
                )
            elif os.path.exists(token_file):
                logger.warning(f"Token file {token_file} exists but is empty, skipping")

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
                    # CI環境ではブラウザOAuthフローを実行できない
                    if self._is_ci_environment():
                        raise RuntimeError(
                            "YouTube token.json が無効または空です。"
                            "CI環境ではブラウザ認証ができません。\n"
                            "ローカルで以下を実行してtokenを再生成してください:\n"
                            "  python generate_youtube_token.py\n"
                            "生成された token.json をbase64エンコードして "
                            "GitHub Secrets の YOUTUBE_TOKEN_JSON_B64 に設定してください。"
                        )

                    if not os.path.exists(self.client_secrets_file):
                        raise FileNotFoundError(
                            f"Client secrets file not found: {self.client_secrets_file}. "
                            "Please download it from Google Cloud Console."
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

    async def upload_video(
        self,
        video_path: Path,
        metadata: VideoMetadata,
        notify_subscribers: bool = False,
    ) -> str:
        """
        Upload a video to YouTube.

        Args:
            video_path: Path to the video file
            metadata: Video metadata (title, description, tags, etc.)
            notify_subscribers: Whether to notify subscribers

        Returns:
            YouTube video ID

        Raises:
            RuntimeError: If upload fails
        """
        if not self.youtube_service:
            await self.authenticate()

        logger.info(f"Uploading video: {metadata.title}")

        try:
            # Prepare request body
            body = {
                "snippet": {
                    "title": metadata.title,
                    "description": metadata.description,
                    "tags": metadata.tags,
                    "categoryId": str(metadata.category_id),
                },
                "status": {
                    "privacyStatus": metadata.privacy_status,
                    "selfDeclaredMadeForKids": False,
                },
            }

            # Handle scheduled publishing
            if metadata.publish_at:
                # Ensure datetime is in UTC and convert to ISO 8601 format with 'Z' suffix
                # YouTube API requires RFC 3339 format in UTC timezone
                from datetime import datetime as dt, timezone as dt_timezone

                # Convert to UTC if not already
                if metadata.publish_at.tzinfo is None:
                    # Assume UTC if no timezone info
                    publish_at_utc = metadata.publish_at.replace(tzinfo=dt_timezone.utc)
                else:
                    publish_at_utc = metadata.publish_at.astimezone(dt_timezone.utc)

                # Remove microseconds for cleaner format
                publish_at_utc = publish_at_utc.replace(microsecond=0)

                # Validate publish time is in the future
                now_utc = dt.now(dt_timezone.utc).replace(microsecond=0)
                time_diff = (publish_at_utc - now_utc).total_seconds()

                if time_diff < 0:
                    raise ValueError(
                        f"Scheduled publish time must be in the future. "
                        f"Requested: {publish_at_utc}, Current: {now_utc}"
                    )

                # YouTube requires at least 15 minutes in the future (some sources say 1 hour)
                min_seconds = 15 * 60  # 15 minutes
                if time_diff < min_seconds:
                    raise ValueError(
                        f"Scheduled publish time must be at least 15 minutes in the future. "
                        f"Time difference: {time_diff / 60:.1f} minutes"
                    )

                # Format as RFC 3339 / ISO 8601 with milliseconds and 'Z' suffix
                # YouTube API expects: 2026-01-05T09:00:00.000Z
                publish_at_iso = publish_at_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")

                body["status"]["publishAt"] = publish_at_iso
                logger.info(
                    f"Scheduled publish time: {publish_at_iso} "
                    f"({time_diff / 3600:.1f} hours from now)"
                )

                # For scheduled publishing, privacy MUST be 'private'
                # YouTube will automatically change it to the final privacy status at publish time
                if metadata.privacy_status != "private":
                    logger.warning(
                        f"Scheduled publishing requires privacy to be 'private'. "
                        f"Changing from '{metadata.privacy_status}' to 'private'. "
                        f"Video will be published at the scheduled time."
                    )
                    body["status"]["privacyStatus"] = "private"

            if not notify_subscribers and not metadata.publish_at:
                # Only set publishAt to None if we're not using scheduled publishing
                body["status"]["publishAt"] = None

            # Prepare media file
            media = MediaFileUpload(
                str(video_path),
                chunksize=-1,
                resumable=True,
                mimetype="video/mp4",
            )

            # Execute upload request
            request = self.youtube_service.videos().insert(
                part="snippet,status", body=body, media_body=media
            )

            logger.info("Starting video upload...")

            response = None
            last_progress = 0

            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    if progress != last_progress and progress % 10 == 0:
                        logger.info(f"Upload progress: {progress}%")
                        last_progress = progress

            video_id = response["id"]

            logger.info(
                f"Upload successful! Video ID: {video_id}, "
                f"URL: https://www.youtube.com/watch?v={video_id}"
            )

            return video_id

        except Exception as e:
            logger.error(f"Video upload failed: {e}")
            raise RuntimeError(f"Failed to upload video to YouTube: {e}") from e

    async def update_video_metadata(
        self, video_id: str, metadata: VideoMetadata
    ) -> None:
        """
        Update metadata for an existing video.

        Args:
            video_id: YouTube video ID
            metadata: New metadata to set

        Raises:
            RuntimeError: If update fails
        """
        if not self.youtube_service:
            await self.authenticate()

        logger.info(f"Updating metadata for video: {video_id}")

        try:
            body = {
                "id": video_id,
                "snippet": {
                    "title": metadata.title,
                    "description": metadata.description,
                    "tags": metadata.tags,
                    "categoryId": str(metadata.category_id),
                },
            }

            self.youtube_service.videos().update(part="snippet", body=body).execute()

            logger.info(f"Metadata updated successfully for video {video_id}")

        except Exception as e:
            logger.error(f"Failed to update video metadata: {e}")
            raise RuntimeError(f"Failed to update video metadata: {e}") from e

    async def set_thumbnail(self, video_id: str, thumbnail_path: Path) -> None:
        """
        Set custom thumbnail for a video.

        Args:
            video_id: YouTube video ID
            thumbnail_path: Path to thumbnail image

        Raises:
            RuntimeError: If setting thumbnail fails
        """
        if not self.youtube_service:
            await self.authenticate()

        logger.info(f"Setting thumbnail for video: {video_id}")

        try:
            self.youtube_service.thumbnails().set(
                videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))
            ).execute()

            logger.info(f"Thumbnail set successfully for video {video_id}")

        except Exception as e:
            logger.error(f"Failed to set thumbnail: {e}")
            raise RuntimeError(f"Failed to set thumbnail: {e}") from e

    async def post_comment(
        self,
        video_id: str,
        comment_text: str,
    ) -> tuple[str | None, str]:
        """
        動画にコメントを投稿する。

        Args:
            video_id: YouTube動画ID
            comment_text: コメント本文

        Returns:
            (コメントID, ステータス) のタプル
            ステータス: "成功" / "コメント無効" / "失敗"
        """
        if not self.youtube_service:
            await self.authenticate()

        logger.info(f"Posting comment on video: {video_id} (text length: {len(comment_text)})")
        if not video_id or not video_id.strip():
            logger.error("video_idが空です。コメント投稿をスキップします")
            return None, "失敗"

        try:
            body = {
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": comment_text,
                        }
                    },
                }
            }

            response = (
                self.youtube_service.commentThreads()
                .insert(part="snippet", body=body)
                .execute()
            )

            comment_id = response.get("id", "")
            logger.info(f"Comment posted successfully: {comment_id}")
            return comment_id, "成功"

        except Exception as e:
            error_str = str(e)
            if "commentsDisabled" in error_str:
                logger.info(
                    f"コメント無効（予約投稿の動画は公開後にリトライ）: {video_id}"
                )
                return None, "コメント無効"
            elif "forbidden" in error_str.lower() or "403" in error_str:
                # private動画ではcommentsDisabledではなくforbiddenが返る場合がある
                # 自分の動画で403が出る場合はほぼコメント無効（private/予約投稿）
                logger.info(
                    f"コメント無効（権限エラー：予約投稿の動画は公開後にリトライ）: {video_id}"
                )
                return None, "コメント無効"
            else:
                logger.warning(f"Failed to post comment: {e}")
                return None, "失敗"

    async def get_video_info(self, video_id: str) -> dict:
        """
        Get information about a video.

        Args:
            video_id: YouTube video ID

        Returns:
            Video information dictionary

        Raises:
            RuntimeError: If request fails
        """
        if not self.youtube_service:
            await self.authenticate()

        try:
            response = (
                self.youtube_service.videos()
                .list(part="snippet,status,statistics", id=video_id)
                .execute()
            )

            if not response.get("items"):
                raise ValueError(f"Video not found: {video_id}")

            return response["items"][0]

        except Exception as e:
            logger.error(f"Failed to get video info: {e}")
            raise RuntimeError(f"Failed to get video info: {e}") from e
