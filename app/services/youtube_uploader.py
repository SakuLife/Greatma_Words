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

            if not notify_subscribers:
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
