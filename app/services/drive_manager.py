"""
Google Drive file management service.
Handles uploading videos and thumbnails to Google Drive.
"""

import os
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.config import settings
from app.utils.logger import logger


class DriveManager:
    """Manages file uploads to Google Drive."""

    SCOPES = ["https://www.googleapis.com/auth/drive.file"]

    def __init__(self, folder_id: str | None = None):
        """
        Initialize Drive manager.

        Args:
            folder_id: Google Drive folder ID to upload to (optional)
        """
        self.folder_id = folder_id or settings.google_drive_folder_id
        self.credentials = None
        self.service = None

    async def authenticate(self, token_file: str = "drive_token.json") -> None:
        """
        Authenticate with Google Drive API using OAuth 2.0.

        Args:
            token_file: Path to store/load OAuth token

        Raises:
            RuntimeError: If authentication fails
        """
        logger.info("Authenticating with Google Drive API")

        try:
            # Load credentials from token file if it exists and is not empty
            if os.path.exists(token_file) and os.path.getsize(token_file) > 0:
                logger.debug(f"Loading Drive credentials from {token_file}")
                self.credentials = Credentials.from_authorized_user_file(
                    token_file, self.SCOPES
                )
            elif os.path.exists(token_file):
                logger.warning(f"Drive token file {token_file} exists but is empty, skipping")

            # If credentials don't exist or are invalid, get new ones
            if not self.credentials or not self.credentials.valid:
                if (
                    self.credentials
                    and self.credentials.expired
                    and self.credentials.refresh_token
                ):
                    logger.info("Refreshing expired Drive credentials")
                    self.credentials.refresh(Request())
                else:
                    # Check if running in CI environment (no browser available)
                    is_ci = os.getenv("CI") or os.getenv("GITHUB_ACTIONS")
                    if is_ci:
                        raise RuntimeError(
                            f"Cannot authenticate in CI environment without valid token file. "
                            f"Please ensure {token_file} is properly configured with a valid refresh token."
                        )

                    if not os.path.exists(settings.google_client_secrets_file):
                        raise FileNotFoundError(
                            f"Client secrets file not found: {settings.google_client_secrets_file}. "
                            "Please download it from Google Cloud Console."
                        )

                    logger.info("Starting OAuth flow")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        settings.google_client_secrets_file, self.SCOPES
                    )
                    self.credentials = flow.run_local_server(port=0)

                    # Save credentials for future use
                    with open(token_file, "w") as token:
                        token.write(self.credentials.to_json())

            # Build Drive service
            self.service = build("drive", "v3", credentials=self.credentials)

            logger.info("Google Drive API authentication successful")

        except Exception as e:
            logger.error(f"Google Drive authentication failed: {e}")
            raise RuntimeError(f"Failed to authenticate with Google Drive: {e}") from e

    async def upload_file(
        self,
        file_path: Path,
        file_name: str | None = None,
        mime_type: str | None = None,
        folder_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Upload a file to Google Drive.

        Args:
            file_path: Path to the file to upload
            file_name: Name for the file in Drive (defaults to original name)
            mime_type: MIME type of the file (auto-detected if not provided)
            folder_id: Folder ID to upload to (uses default if not provided)

        Returns:
            File metadata including file ID and web view link

        Raises:
            RuntimeError: If upload fails
        """
        if not self.service:
            await self.authenticate()

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_name = file_name or file_path.name
        target_folder_id = folder_id or self.folder_id

        logger.info(f"Uploading file to Google Drive: {file_name}")

        try:
            # Detect MIME type if not provided
            if not mime_type:
                mime_type = self._get_mime_type(file_path)

            # Prepare file metadata
            file_metadata: dict[str, Any] = {"name": file_name}

            if target_folder_id:
                file_metadata["parents"] = [target_folder_id]

            # Prepare media file
            media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=True)

            # Upload file
            file = (
                self.service.files()
                .create(body=file_metadata, media_body=media, fields="id,name,webViewLink,size")
                .execute()
            )

            logger.info(
                f"File uploaded successfully: {file['name']} (ID: {file['id']})"
            )

            return {
                "id": file["id"],
                "name": file["name"],
                "url": file["webViewLink"],
                "size": int(file.get("size", 0)),
            }

        except Exception as e:
            logger.error(f"Failed to upload file to Google Drive: {e}")
            raise RuntimeError(f"Failed to upload file to Google Drive: {e}") from e

    async def create_folder(
        self, folder_name: str, parent_folder_id: str | None = None
    ) -> str:
        """
        Create a folder in Google Drive.

        Args:
            folder_name: Name of the folder to create
            parent_folder_id: Parent folder ID (creates in root if not provided)

        Returns:
            Created folder ID

        Raises:
            RuntimeError: If folder creation fails
        """
        if not self.service:
            await self.authenticate()

        logger.info(f"Creating folder: {folder_name}")

        try:
            file_metadata: dict[str, Any] = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }

            if parent_folder_id:
                file_metadata["parents"] = [parent_folder_id]

            folder = (
                self.service.files()
                .create(body=file_metadata, fields="id,name")
                .execute()
            )

            logger.info(f"Folder created: {folder['name']} (ID: {folder['id']})")

            return folder["id"]

        except Exception as e:
            logger.error(f"Failed to create folder: {e}")
            raise RuntimeError(f"Failed to create folder: {e}") from e

    async def get_file_info(self, file_id: str) -> dict[str, Any]:
        """
        Get information about a file.

        Args:
            file_id: Google Drive file ID

        Returns:
            File metadata

        Raises:
            RuntimeError: If request fails
        """
        if not self.service:
            await self.authenticate()

        try:
            file = (
                self.service.files()
                .get(fileId=file_id, fields="id,name,webViewLink,size,createdTime,modifiedTime")
                .execute()
            )
            return file

        except Exception as e:
            logger.error(f"Failed to get file info: {e}")
            raise RuntimeError(f"Failed to get file info: {e}") from e

    async def delete_file(self, file_id: str) -> None:
        """
        Delete a file from Google Drive.

        Args:
            file_id: Google Drive file ID

        Raises:
            RuntimeError: If deletion fails
        """
        if not self.service:
            await self.authenticate()

        try:
            self.service.files().delete(fileId=file_id).execute()
            logger.info(f"File deleted: {file_id}")

        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            raise RuntimeError(f"Failed to delete file: {e}") from e

    async def list_files(
        self, folder_id: str | None = None, max_results: int = 100
    ) -> list[dict[str, Any]]:
        """
        List files in a folder.

        Args:
            folder_id: Folder ID (lists all files if not provided)
            max_results: Maximum number of results to return

        Returns:
            List of file metadata

        Raises:
            RuntimeError: If request fails
        """
        if not self.service:
            await self.authenticate()

        try:
            query = ""
            if folder_id:
                query = f"'{folder_id}' in parents"

            results = (
                self.service.files()
                .list(
                    q=query,
                    pageSize=max_results,
                    fields="files(id,name,webViewLink,size,createdTime,mimeType)",
                )
                .execute()
            )

            return results.get("files", [])

        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            raise RuntimeError(f"Failed to list files: {e}") from e

    @staticmethod
    def _get_mime_type(file_path: Path) -> str:
        """
        Detect MIME type from file extension.

        Args:
            file_path: Path to file

        Returns:
            MIME type string
        """
        extension = file_path.suffix.lower()

        mime_types = {
            ".mp4": "video/mp4",
            ".avi": "video/x-msvideo",
            ".mov": "video/quicktime",
            ".mkv": "video/x-matroska",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".json": "application/json",
            ".txt": "text/plain",
            ".pdf": "application/pdf",
        }

        return mime_types.get(extension, "application/octet-stream")

    async def get_folder_url(self, folder_id: str) -> str:
        """
        Get the web view URL for a folder.

        Args:
            folder_id: Google Drive folder ID

        Returns:
            Web view URL
        """
        return f"https://drive.google.com/drive/folders/{folder_id}"
