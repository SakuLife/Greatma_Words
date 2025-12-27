"""
Google Sheets management service.
Handles logging video production and task management.
"""

import os
from datetime import datetime
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config import settings
from app.utils.logger import logger


class SheetsManager:
    """Manages Google Sheets for task and video tracking."""

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    def __init__(self, spreadsheet_id: str | None = None):
        """
        Initialize Sheets manager.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID (optional)
        """
        self.spreadsheet_id = spreadsheet_id or settings.google_sheets_id
        self.credentials = None
        self.service = None

    async def authenticate(self, token_file: str = "sheets_token.json") -> None:
        """
        Authenticate with Google Sheets API using OAuth 2.0.

        Args:
            token_file: Path to store/load OAuth token

        Raises:
            RuntimeError: If authentication fails
        """
        logger.info("Authenticating with Google Sheets API")

        try:
            # Load credentials from token file if it exists and is not empty
            if os.path.exists(token_file) and os.path.getsize(token_file) > 0:
                logger.debug(f"Loading Sheets credentials from {token_file}")
                self.credentials = Credentials.from_authorized_user_file(
                    token_file, self.SCOPES
                )
            elif os.path.exists(token_file):
                logger.warning(f"Sheets token file {token_file} exists but is empty, skipping")

            # If credentials don't exist or are invalid, get new ones
            if not self.credentials or not self.credentials.valid:
                if (
                    self.credentials
                    and self.credentials.expired
                    and self.credentials.refresh_token
                ):
                    logger.info("Refreshing expired Sheets credentials")
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

            # Build Sheets service
            self.service = build("sheets", "v4", credentials=self.credentials)

            logger.info("Google Sheets API authentication successful")

        except Exception as e:
            logger.error(f"Google Sheets authentication failed: {e}")
            raise RuntimeError(f"Failed to authenticate with Google Sheets: {e}") from e

    async def log_video_production(
        self,
        person_name: str,
        theme: str,
        video_duration: float,
        generation_time: float,
        youtube_url: str | None = None,
        drive_url: str | None = None,
        project_path: str | None = None,
        sheet_name: str = "動画制作ログ",
    ) -> bool:
        """
        Log video production to Google Sheets.

        Args:
            person_name: Name of the person/figure
            theme: Video theme
            video_duration: Video duration in seconds
            generation_time: Time taken to generate video in seconds
            youtube_url: YouTube video URL (optional)
            drive_url: Google Drive URL (optional)
            project_path: Project directory path (optional)
            sheet_name: Name of the sheet to write to

        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            await self.authenticate()

        logger.info(f"Logging video production to Google Sheets: {person_name}")

        try:
            # Format data
            video_minutes = int(video_duration // 60)
            video_seconds = int(video_duration % 60)
            gen_minutes = int(generation_time // 60)
            gen_seconds = int(generation_time % 60)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            row_data = [
                timestamp,
                person_name,
                theme,
                f"{video_minutes}:{video_seconds:02d}",
                f"{gen_minutes}:{gen_seconds:02d}",
                project_path or "",
                youtube_url or "",
                "",  # 視聴回数 (will be updated later)
                "",  # いいね数 (will be updated later)
                "",  # コメント数 (will be updated later)
                drive_url or "",
            ]

            # Append row to sheet
            range_name = f"{sheet_name}!A:K"

            body = {"values": [row_data]}

            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption="RAW",
                body=body,
            ).execute()

            logger.info(f"Video production logged successfully: {person_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to log video production: {e}")
            return False

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        assignee: str | None = None,
        completion_date: str | None = None,
        notes: str | None = None,
        sheet_name: str = "タスクマスター",
    ) -> bool:
        """
        Update task status in Google Sheets.

        Args:
            task_id: Task ID (e.g., "YT-001")
            status: New status (e.g., "完了", "進行中", "未着手")
            assignee: Person assigned to task (optional)
            completion_date: Date task was completed (optional)
            notes: Additional notes (optional)
            sheet_name: Name of the sheet to update

        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            await self.authenticate()

        logger.info(f"Updating task status: {task_id} -> {status}")

        try:
            # Find the row with the task ID
            range_name = f"{sheet_name}!A:J"

            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=range_name)
                .execute()
            )

            values = result.get("values", [])

            # Find task row
            row_index = None
            for i, row in enumerate(values):
                if row and row[0] == task_id:
                    row_index = i + 1  # 1-indexed
                    break

            if row_index is None:
                logger.warning(f"Task not found in sheet: {task_id}")
                return False

            # Prepare updates
            updates = []

            # Update status (column E = index 4)
            updates.append(
                {
                    "range": f"{sheet_name}!E{row_index}",
                    "values": [[status]],
                }
            )

            # Update assignee if provided (column F = index 5)
            if assignee:
                updates.append(
                    {
                        "range": f"{sheet_name}!F{row_index}",
                        "values": [[assignee]],
                    }
                )

            # Update completion date if provided (column G = index 6)
            if completion_date:
                updates.append(
                    {
                        "range": f"{sheet_name}!G{row_index}",
                        "values": [[completion_date]],
                    }
                )

            # Update notes if provided (column H = index 7)
            if notes:
                updates.append(
                    {
                        "range": f"{sheet_name}!H{row_index}",
                        "values": [[notes]],
                    }
                )

            # Batch update
            body = {
                "valueInputOption": "RAW",
                "data": updates,
            }

            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id, body=body
            ).execute()

            logger.info(f"Task status updated successfully: {task_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update task status: {e}")
            return False

    async def log_cost(
        self,
        service: str,
        usage_type: str,
        usage_amount: float,
        unit_price: float,
        total_cost: float,
        notes: str | None = None,
        sheet_name: str = "コスト管理",
    ) -> bool:
        """
        Log API usage cost to Google Sheets.

        Args:
            service: Service name (e.g., "Claude API", "OpenAI API")
            usage_type: Type of usage (e.g., "台本生成", "画像生成")
            usage_amount: Amount used (e.g., tokens, images)
            unit_price: Price per unit
            total_cost: Total cost
            notes: Additional notes (optional)
            sheet_name: Name of the sheet to write to

        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            await self.authenticate()

        logger.info(f"Logging cost: {service} - {usage_type}")

        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            row_data = [
                timestamp,
                service,
                usage_type,
                usage_amount,
                unit_price,
                total_cost,
                notes or "",
            ]

            range_name = f"{sheet_name}!A:G"

            body = {"values": [row_data]}

            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption="RAW",
                body=body,
            ).execute()

            logger.info(f"Cost logged successfully: {service}")
            return True

        except Exception as e:
            logger.error(f"Failed to log cost: {e}")
            return False

    async def get_all_tasks(
        self, sheet_name: str = "タスクマスター"
    ) -> list[dict[str, Any]]:
        """
        Get all tasks from the task management sheet.

        Args:
            sheet_name: Name of the sheet to read from

        Returns:
            List of task dictionaries
        """
        if not self.service:
            await self.authenticate()

        try:
            range_name = f"{sheet_name}!A:H"

            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=range_name)
                .execute()
            )

            values = result.get("values", [])

            if not values:
                return []

            # Assume first row is header
            headers = values[0]
            tasks = []

            for row in values[1:]:
                task = {}
                for i, header in enumerate(headers):
                    task[header] = row[i] if i < len(row) else ""
                tasks.append(task)

            return tasks

        except Exception as e:
            logger.error(f"Failed to get tasks: {e}")
            return []

    async def get_video_stats(
        self, sheet_name: str = "動画制作ログ"
    ) -> dict[str, Any]:
        """
        Get statistics about video production.

        Args:
            sheet_name: Name of the sheet to read from

        Returns:
            Dictionary with statistics
        """
        if not self.service:
            await self.authenticate()

        try:
            range_name = f"{sheet_name}!A:K"

            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=range_name)
                .execute()
            )

            values = result.get("values", [])

            if len(values) <= 1:  # Only header or empty
                return {
                    "total_videos": 0,
                    "total_duration": 0,
                    "average_generation_time": 0,
                }

            total_videos = len(values) - 1  # Exclude header
            total_duration = 0
            total_gen_time = 0

            for row in values[1:]:
                if len(row) >= 5:
                    # Parse duration (format: "MM:SS")
                    if row[3]:
                        parts = row[3].split(":")
                        if len(parts) == 2:
                            total_duration += int(parts[0]) * 60 + int(parts[1])

                    # Parse generation time
                    if row[4]:
                        parts = row[4].split(":")
                        if len(parts) == 2:
                            total_gen_time += int(parts[0]) * 60 + int(parts[1])

            return {
                "total_videos": total_videos,
                "total_duration_seconds": total_duration,
                "total_duration_minutes": total_duration // 60,
                "average_generation_time_seconds": (
                    total_gen_time // total_videos if total_videos > 0 else 0
                ),
                "average_generation_time_minutes": (
                    (total_gen_time // total_videos) // 60 if total_videos > 0 else 0
                ),
            }

        except Exception as e:
            logger.error(f"Failed to get video stats: {e}")
            return {}
