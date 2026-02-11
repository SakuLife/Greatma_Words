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
        auto_comment_status: str = "",
        auto_comment_text: str = "",
        opening_text: str = "",
        action_plan: str = "",
        hook_strategy: str = "",
        structure_pattern: str = "",
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
            auto_comment_status: 自動コメント投稿結果（"成功" / "失敗" / ""）
            auto_comment_text: 投稿したコメント本文
            opening_text: 冒頭テキスト（次回の重複回避用）
            action_plan: アクションプラン（現代への応用セクションの要約）
            hook_strategy: 使用したフック戦略名
            structure_pattern: 使用した構成パターン名
            sheet_name: Name of the sheet to write to

        Returns:
            True if successful, False otherwise
        """
        if not self.spreadsheet_id:
            logger.error("❌ Google Sheets ID is not configured (GOOGLE_SHEETS_ID)")
            return False

        if not self.service:
            logger.info("Google Sheets service not initialized, authenticating...")
            await self.authenticate()

        logger.info(f"Logging video production to Google Sheets: {person_name}")
        logger.info(f"   SpreadsheetID: {self.spreadsheet_id}")

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
                auto_comment_status,
                auto_comment_text[:100] if auto_comment_text else "",  # 長すぎる場合は100文字で切る
                opening_text[:200] if opening_text else "",  # 冒頭テキスト（次回の重複回避用）
                action_plan[:200] if action_plan else "",  # アクションプラン
                hook_strategy,  # フック戦略名
                structure_pattern,  # 構成パターン名
            ]

            # Append row to sheet
            range_name = f"{sheet_name}!A:Q"

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
            logger.error(f"❌ Failed to log video production: {e}")
            logger.error(f"   SpreadsheetID: {self.spreadsheet_id}")
            logger.error(f"   SheetName: {sheet_name}")
            import traceback
            logger.error(traceback.format_exc())
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

    async def get_pending_comments(
        self, sheet_name: str = "動画制作ログ"
    ) -> list[dict[str, str]]:
        """
        コメントが「保留」になっているエントリを取得する。

        Args:
            sheet_name: シート名

        Returns:
            保留コメントのリスト [{row_index, youtube_url, comment_text}, ...]
        """
        if not self.service:
            await self.authenticate()

        try:
            range_name = f"{sheet_name}!A:M"
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=range_name)
                .execute()
            )

            values = result.get("values", [])
            pending = []

            for i, row in enumerate(values[1:], start=2):  # 1-indexed, skip header
                if len(row) >= 13 and row[11] == "保留" and row[12]:
                    youtube_url = row[6] if len(row) > 6 else ""
                    if youtube_url:
                        # URLからvideo_idを抽出
                        video_id = youtube_url.split("v=")[-1].split("&")[0] if "v=" in youtube_url else ""
                        if video_id:
                            pending.append({
                                "row_index": i,
                                "video_id": video_id,
                                "youtube_url": youtube_url,
                                "comment_text": row[12],
                                "person_name": row[1] if len(row) > 1 else "",
                            })

            logger.info(f"保留コメント: {len(pending)}件")
            return pending

        except Exception as e:
            logger.error(f"保留コメント取得に失敗: {e}")
            return []

    async def update_comment_status(
        self,
        row_index: int,
        status: str,
        sheet_name: str = "動画制作ログ",
    ) -> bool:
        """
        コメントステータスを更新する。

        Args:
            row_index: 行番号（1-indexed）
            status: 新しいステータス（"成功" / "失敗"）
            sheet_name: シート名

        Returns:
            成功したらTrue
        """
        if not self.service:
            await self.authenticate()

        try:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!L{row_index}",
                valueInputOption="RAW",
                body={"values": [[status]]},
            ).execute()

            logger.info(f"コメントステータスを更新: 行{row_index} → {status}")
            return True

        except Exception as e:
            logger.error(f"コメントステータス更新に失敗: {e}")
            return False

    async def update_video_stats(
        self,
        row_index: int,
        view_count: int,
        like_count: int,
        comment_count: int,
        sheet_name: str = "動画制作ログ",
    ) -> bool:
        """
        動画の視聴回数・いいね数・コメント数を更新する（HIJ列）。

        Args:
            row_index: 行番号（1-indexed）
            view_count: 視聴回数
            like_count: いいね数
            comment_count: コメント数
            sheet_name: シート名

        Returns:
            成功したらTrue
        """
        if not self.service:
            await self.authenticate()

        try:
            # H列=8列目, I列=9列目, J列=10列目
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!H{row_index}:J{row_index}",
                valueInputOption="RAW",
                body={"values": [[view_count, like_count, comment_count]]},
            ).execute()

            logger.info(
                f"動画統計を更新: 行{row_index} "
                f"(再生{view_count}, いいね{like_count}, コメント{comment_count})"
            )
            return True

        except Exception as e:
            logger.error(f"動画統計の更新に失敗: {e}")
            return False

    async def get_videos_for_stats_update(
        self,
        sheet_name: str = "動画制作ログ",
    ) -> list[dict[str, Any]]:
        """
        統計情報を更新すべき動画のリストを取得する。
        YouTube URLがあり、HIJ列が空のもの、または全件を返す。

        Args:
            sheet_name: シート名

        Returns:
            更新対象の動画リスト [{row_index, video_id, person_name}, ...]
        """
        if not self.service:
            await self.authenticate()

        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{sheet_name}!A:J",
                )
                .execute()
            )

            values = result.get("values", [])
            if len(values) <= 1:
                return []

            videos = []
            for i, row in enumerate(values[1:], start=2):  # 1-indexed, skip header
                if len(row) < 7:
                    continue

                youtube_url = row[6] if len(row) > 6 else ""
                if not youtube_url or "youtube.com" not in youtube_url:
                    continue

                # URLからvideo_idを抽出
                video_id = ""
                if "v=" in youtube_url:
                    video_id = youtube_url.split("v=")[-1].split("&")[0]
                if not video_id:
                    continue

                videos.append({
                    "row_index": i,
                    "video_id": video_id,
                    "person_name": row[1] if len(row) > 1 else "",
                })

            logger.info(f"統計更新対象の動画: {len(videos)}件")
            return videos

        except Exception as e:
            logger.error(f"統計更新対象の取得に失敗: {e}")
            return []

    async def get_previous_openings(
        self,
        limit: int = 5,
        sheet_name: str = "動画制作ログ",
    ) -> list[str]:
        """
        過去の動画の冒頭テキストを取得する（重複回避用）。

        Args:
            limit: 取得する最大件数
            sheet_name: シート名

        Returns:
            冒頭テキストのリスト（新しい順）
        """
        if not self.service:
            await self.authenticate()

        try:
            # N列（14列目）が冒頭テキスト
            result = (
                self.service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{sheet_name}!N:N",
                )
                .execute()
            )

            values = result.get("values", [])
            if len(values) <= 1:
                return []

            # ヘッダーをスキップし、空でないものを新しい順に取得
            openings = []
            for row in reversed(values[1:]):
                if row and row[0].strip():
                    openings.append(row[0].strip())
                if len(openings) >= limit:
                    break

            logger.info(f"過去の冒頭テキストを取得: {len(openings)}件")
            return openings

        except Exception as e:
            logger.warning(f"過去の冒頭テキスト取得に失敗: {e}")
            return []

    # ========================================
    # 週次分析・A/Bテスト用メソッド
    # ========================================

    async def ensure_sheet_exists(
        self, sheet_name: str, headers: list[str]
    ) -> None:
        """
        シートが存在しない場合は作成し、ヘッダー行を書き込む

        Args:
            sheet_name: シート名
            headers: ヘッダー行の値リスト
        """
        if not self.service:
            await self.authenticate()

        try:
            # 既存のシート一覧を取得
            spreadsheet = (
                self.service.spreadsheets()
                .get(spreadsheetId=self.spreadsheet_id)
                .execute()
            )

            existing_sheets = [
                s["properties"]["title"] for s in spreadsheet.get("sheets", [])
            ]

            if sheet_name in existing_sheets:
                logger.debug(f"シート '{sheet_name}' は既に存在します")
                return

            # シートを新規作成
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={
                    "requests": [
                        {
                            "addSheet": {
                                "properties": {"title": sheet_name}
                            }
                        }
                    ]
                },
            ).execute()

            # ヘッダー行を書き込み
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="RAW",
                body={"values": [headers]},
            ).execute()

            logger.info(f"シート '{sheet_name}' を作成しました")

        except Exception as e:
            logger.error(f"シート作成に失敗 ({sheet_name}): {e}")
            raise

    async def write_weekly_analytics(
        self,
        subscriber_data: list[dict],
        trending_videos: list[dict],
        retention_data: list[dict],
        report_date: str,
        sheet_name: str = "週次分析レポート",
    ) -> bool:
        """
        週次分析結果をGoogle Sheetsに書き込む

        Args:
            subscriber_data: 登録者推移データ [{date, gained, lost, net}]
            trending_videos: 注目動画 [{video_id, title, current_views, previous_views, growth_rate}]
            retention_data: 維持率データ [{video_id, title, average_retention}]
            report_date: レポート日 (YYYY-MM-DD)
            sheet_name: シート名

        Returns:
            成功したらTrue
        """
        if not self.service:
            await self.authenticate()

        headers = [
            "レポート日", "期間", "登録者増加", "登録者減少", "純増減",
            "注目動画ID", "注目動画タイトル", "視聴回数(今週)",
            "視聴回数(先週)", "成長率", "平均維持率(%)",
        ]

        try:
            await self.ensure_sheet_exists(sheet_name, headers)

            rows = []

            # 登録者サマリー行
            total_gained = sum(d.get("gained", 0) for d in subscriber_data)
            total_lost = sum(d.get("lost", 0) for d in subscriber_data)
            period = ""
            if subscriber_data:
                dates = [d["date"] for d in subscriber_data]
                period = f"{min(dates)} ~ {max(dates)}"

            # 注目動画ごとに1行
            if trending_videos:
                for video in trending_videos:
                    # 維持率を検索
                    avg_ret = ""
                    for r in retention_data:
                        if r.get("video_id") == video.get("video_id"):
                            avg_ret = f"{r.get('average_retention', 0):.1f}"
                            break

                    growth_rate = video.get("growth_rate", 0)
                    growth_str = (
                        f"{growth_rate:.1f}倍"
                        if growth_rate != float("inf")
                        else "新規"
                    )

                    rows.append([
                        report_date,
                        period,
                        total_gained,
                        total_lost,
                        total_gained - total_lost,
                        video.get("video_id", ""),
                        video.get("title", "不明"),
                        video.get("current_views", 0),
                        video.get("previous_views", 0),
                        growth_str,
                        avg_ret,
                    ])
            else:
                # 注目動画がなくても登録者データは記録
                rows.append([
                    report_date, period,
                    total_gained, total_lost, total_gained - total_lost,
                    "", "", "", "", "", "",
                ])

            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A:K",
                valueInputOption="RAW",
                body={"values": rows},
            ).execute()

            logger.info(f"週次分析レポートを記録: {len(rows)}行")
            return True

        except Exception as e:
            logger.error(f"週次分析レポートの書き込みに失敗: {e}")
            return False

    async def write_ab_test_results(
        self,
        test_results: list[dict],
        sheet_name: str = "サムネイルA/Bテスト",
    ) -> bool:
        """
        A/Bテスト結果をGoogle Sheetsに書き込む（全行上書き）

        Args:
            test_results: テスト結果リスト
            sheet_name: シート名

        Returns:
            成功したらTrue
        """
        if not self.service:
            await self.authenticate()

        headers = [
            "動画ID", "動画タイトル", "ステータス", "現在のバリアント",
            "Aコピー", "Aスタイル", "Aインプレッション", "A CTR(%)", "A表示日数",
            "Bコピー", "Bスタイル", "Bインプレッション", "B CTR(%)", "B表示日数",
            "勝者", "作成日", "最終切替日", "完了日",
        ]

        try:
            await self.ensure_sheet_exists(sheet_name, headers)

            if not test_results:
                logger.info("A/Bテスト結果なし（書き込みスキップ）")
                return True

            rows = []
            for t in test_results:
                rows.append([
                    t.get("video_id", ""),
                    t.get("video_title", ""),
                    t.get("status", ""),
                    t.get("current_variant", ""),
                    t.get("variant_a_copy", ""),
                    t.get("variant_a_style", ""),
                    t.get("variant_a_impressions", 0),
                    t.get("variant_a_ctr", 0),
                    t.get("variant_a_days", 0),
                    t.get("variant_b_copy", ""),
                    t.get("variant_b_style", ""),
                    t.get("variant_b_impressions", 0),
                    t.get("variant_b_ctr", 0),
                    t.get("variant_b_days", 0),
                    t.get("winner", ""),
                    t.get("created_at", ""),
                    t.get("last_rotated_at", ""),
                    t.get("completed_at", ""),
                ])

            # ヘッダー行以降をクリアして書き直し
            self.service.spreadsheets().values().clear(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A2:R",
            ).execute()

            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A2",
                valueInputOption="RAW",
                body={"values": rows},
            ).execute()

            logger.info(f"A/Bテスト結果を記録: {len(rows)}件")
            return True

        except Exception as e:
            logger.error(f"A/Bテスト結果の書き込みに失敗: {e}")
            return False

    async def read_ab_test_state(
        self, sheet_name: str = "サムネイルA/Bテスト"
    ) -> list[dict]:
        """
        A/Bテストの現在の状態をGoogle Sheetsから読み込む

        Args:
            sheet_name: シート名

        Returns:
            テスト状態のリスト
        """
        if not self.service:
            await self.authenticate()

        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{sheet_name}!A:R",
                )
                .execute()
            )

            values = result.get("values", [])
            if len(values) <= 1:
                return []

            headers = values[0]
            tests = []
            for row in values[1:]:
                test = {}
                for i, header in enumerate(headers):
                    test[header] = row[i] if i < len(row) else ""
                tests.append(test)

            logger.info(f"A/Bテスト状態を読み込み: {len(tests)}件")
            return tests

        except Exception as e:
            logger.warning(f"A/Bテスト状態の読み込みに失敗（シート未作成の可能性）: {e}")
            return []

    # ========================================
    # 包括的チャンネル分析用メソッド (Phase 1)
    # ========================================

    async def write_deep_analysis(
        self,
        analysis_data: dict[str, Any],
        sheet_name: str = "チャンネル詳細分析",
    ) -> bool:
        """
        包括的チャンネル分析結果をGoogle Sheetsに書き込む

        Args:
            analysis_data: 分析データ辞書
            sheet_name: シート名

        Returns:
            成功したらTrue
        """
        if not self.service:
            await self.authenticate()

        headers = [
            "分析日", "分析期間", "登録者数", "総再生数", "総動画数",
            "主要トラフィック", "トラフィック詳細",
            "主要年齢層", "性別比率",
            "主要デバイス", "デバイス詳細",
            "登録者獲得TOP動画", "登録者獲得数",
            "推奨投稿時間", "投稿時間信頼度",
        ]

        try:
            await self.ensure_sheet_exists(sheet_name, headers)

            # データ行を構築
            traffic_detail = ""
            if analysis_data.get("traffic_sources"):
                traffic_detail = " / ".join(
                    f"{t['source_type']}:{t['percentage']}%"
                    for t in analysis_data["traffic_sources"][:5]
                )

            device_detail = ""
            if analysis_data.get("devices"):
                device_detail = " / ".join(
                    f"{d['device_type']}:{d['percentage']}%"
                    for d in analysis_data["devices"][:5]
                )

            top_sub_video = ""
            top_sub_count = ""
            if analysis_data.get("top_subscriber_videos"):
                top = analysis_data["top_subscriber_videos"][0]
                top_sub_video = top.get("title", "")[:40]
                top_sub_count = str(top.get("subscribers_gained", 0))

            row = [
                analysis_data.get("analysis_date", ""),
                f"過去{analysis_data.get('analysis_period_days', 90)}日",
                analysis_data.get("subscriber_count", 0),
                analysis_data.get("total_views", 0),
                analysis_data.get("total_videos", 0),
                analysis_data.get("top_traffic_source", ""),
                traffic_detail,
                analysis_data.get("top_age_group", ""),
                analysis_data.get("gender_ratio", ""),
                analysis_data.get("primary_device", ""),
                device_detail,
                top_sub_video,
                top_sub_count,
                analysis_data.get("recommended_publish_time", ""),
                analysis_data.get("upload_time_confidence", ""),
            ]

            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A:O",
                valueInputOption="RAW",
                body={"values": [row]},
            ).execute()

            logger.info(f"チャンネル詳細分析を記録: {sheet_name}")
            return True

        except Exception as e:
            logger.error(f"チャンネル詳細分析の書き込みに失敗: {e}")
            return False

    async def write_upload_time_analysis(
        self,
        day_performances: list[dict],
        best_time: str,
        confidence: float,
        sheet_name: str = "投稿時間分析",
    ) -> bool:
        """
        投稿時間分析結果をGoogle Sheetsに書き込む

        Args:
            day_performances: 曜日別パフォーマンスデータ
            best_time: 推奨投稿時間
            confidence: 信頼度
            sheet_name: シート名

        Returns:
            成功したらTrue
        """
        if not self.service:
            await self.authenticate()

        headers = [
            "分析日", "推奨投稿時間", "信頼度",
            "曜日", "投稿数", "平均初動再生数(48h)",
        ]

        try:
            await self.ensure_sheet_exists(sheet_name, headers)

            analysis_date = datetime.now().strftime("%Y-%m-%d")
            rows = []

            for dp in day_performances:
                rows.append([
                    analysis_date,
                    best_time,
                    f"{confidence:.0%}",
                    f"{dp.get('day_name', '')}曜日",
                    dp.get("total_uploads", 0),
                    f"{dp.get('avg_initial_views_48h', 0):.0f}",
                ])

            if not rows:
                rows.append([analysis_date, best_time, f"{confidence:.0%}", "", "", ""])

            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A:F",
                valueInputOption="RAW",
                body={"values": rows},
            ).execute()

            logger.info(f"投稿時間分析を記録: {len(rows)}行")
            return True

        except Exception as e:
            logger.error(f"投稿時間分析の書き込みに失敗: {e}")
            return False

    async def write_competitor_analysis(
        self,
        competitor_data: dict[str, Any],
        sheet_name: str = "競合分析",
    ) -> bool:
        """
        競合分析結果をGoogle Sheetsに書き込む

        Args:
            competitor_data: 競合分析データ
            sheet_name: シート名

        Returns:
            成功したらTrue
        """
        if not self.service:
            await self.authenticate()

        headers = [
            "調査日", "検索クエリ", "動画タイトル", "チャンネル名",
            "再生回数", "いいね数", "エンゲージメント率",
            "人物名", "ギャップ機会",
        ]

        try:
            await self.ensure_sheet_exists(sheet_name, headers)

            rows = []
            analysis_date = competitor_data.get("analyzed_at", datetime.now().strftime("%Y-%m-%d"))

            # 競合動画
            for video in competitor_data.get("videos", [])[:30]:
                rows.append([
                    analysis_date,
                    ", ".join(competitor_data.get("search_queries", [])),
                    video.get("title", "")[:60],
                    video.get("channel_title", ""),
                    video.get("view_count", 0),
                    video.get("like_count", 0),
                    f"{video.get('engagement_rate', 0):.2f}%",
                    "",  # 人物名は後で分析
                    "",
                ])

            # ギャップ機会
            for gap in competitor_data.get("gap_opportunities", []):
                rows.append([
                    analysis_date,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    gap.get("person", ""),
                    gap.get("reason", ""),
                ])

            if rows:
                self.service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{sheet_name}!A:I",
                    valueInputOption="RAW",
                    body={"values": rows},
                ).execute()

            logger.info(f"競合分析を記録: {len(rows)}行")
            return True

        except Exception as e:
            logger.error(f"競合分析の書き込みに失敗: {e}")
            return False

    async def write_content_strategy(
        self,
        strategy_data: dict[str, Any],
        sheet_name: str = "コンテンツ戦略",
    ) -> bool:
        """
        コンテンツ戦略をGoogle Sheetsに書き込む

        Args:
            strategy_data: 戦略データ
            sheet_name: シート名

        Returns:
            成功したらTrue
        """
        if not self.service:
            await self.authenticate()

        headers = [
            "生成日", "推奨人物", "推奨テーマ", "フック戦略",
            "構成パターン", "差別化ポイント",
            "タイトル案", "ハッシュタグ案",
            "推奨投稿日時", "理由",
        ]

        try:
            await self.ensure_sheet_exists(sheet_name, headers)

            rows = []
            strategy_date = strategy_data.get("date", datetime.now().strftime("%Y-%m-%d"))

            for suggestion in strategy_data.get("next_video_suggestions", []):
                rows.append([
                    strategy_date,
                    suggestion.get("person", ""),
                    suggestion.get("topic", ""),
                    suggestion.get("hook_strategy", ""),
                    suggestion.get("structure", ""),
                    suggestion.get("differentiation", ""),
                    suggestion.get("title_suggestion", ""),
                    suggestion.get("hashtags", ""),
                    strategy_data.get("upload_schedule", {}).get("publish_at", ""),
                    suggestion.get("reason", ""),
                ])

            if rows:
                self.service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{sheet_name}!A:J",
                    valueInputOption="RAW",
                    body={"values": rows},
                ).execute()

            logger.info(f"コンテンツ戦略を記録: {len(rows)}行")
            return True

        except Exception as e:
            logger.error(f"コンテンツ戦略の書き込みに失敗: {e}")
            return False

    async def read_latest_strategy(
        self, sheet_name: str = "コンテンツ戦略"
    ) -> list[dict]:
        """
        最新のコンテンツ戦略をGoogle Sheetsから読み込む

        Args:
            sheet_name: シート名

        Returns:
            戦略データのリスト
        """
        if not self.service:
            await self.authenticate()

        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{sheet_name}!A:J",
                )
                .execute()
            )

            values = result.get("values", [])
            if len(values) <= 1:
                return []

            headers = values[0]
            strategies = []
            for row in values[1:]:
                strategy = {}
                for i, header in enumerate(headers):
                    strategy[header] = row[i] if i < len(row) else ""
                strategies.append(strategy)

            # 最新の日付のもののみ返す
            if strategies:
                latest_date = strategies[-1].get("生成日", "")
                strategies = [s for s in strategies if s.get("生成日") == latest_date]

            logger.info(f"コンテンツ戦略を読み込み: {len(strategies)}件")
            return strategies

        except Exception as e:
            logger.warning(f"コンテンツ戦略の読み込みに失敗: {e}")
            return []

    async def get_published_videos(
        self,
        exclude_person: str | None = None,
        limit: int = 10,
        sheet_name: str = "動画制作ログ",
    ) -> list[dict[str, str]]:
        """
        公開済み動画のリストを取得する（説明文の関連動画リンク用）

        Args:
            exclude_person: 除外する人物名（現在の動画の人物）
            limit: 取得する最大件数
            sheet_name: シート名

        Returns:
            動画情報のリスト [{person_name, theme, youtube_url}, ...]
        """
        if not self.service:
            await self.authenticate()

        try:
            # A:G列を取得（タイムスタンプ、人物名、テーマ、動画長、生成時間、プロジェクトパス、YouTubeURL）
            result = (
                self.service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{sheet_name}!A:G",
                )
                .execute()
            )

            values = result.get("values", [])
            if len(values) <= 1:
                return []

            videos = []
            # 新しい順に取得するため逆順
            for row in reversed(values[1:]):
                if len(row) >= 7 and row[6]:  # YouTubeURLがある
                    youtube_url = row[6]
                    person_name = row[1] if len(row) > 1 else ""
                    theme = row[2] if len(row) > 2 else ""

                    # 除外条件
                    if exclude_person and person_name == exclude_person:
                        continue

                    # URLが有効か確認
                    if "youtube.com" in youtube_url or "youtu.be" in youtube_url:
                        videos.append({
                            "person_name": person_name,
                            "theme": theme,
                            "youtube_url": youtube_url,
                        })

                    if len(videos) >= limit:
                        break

            logger.info(f"公開済み動画を取得: {len(videos)}件")
            return videos

        except Exception as e:
            logger.warning(f"公開済み動画の取得に失敗: {e}")
            return []
