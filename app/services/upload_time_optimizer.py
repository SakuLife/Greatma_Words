"""
投稿時間最適化サービス。
分析データに基づいて最適な公開日時を算出する。
Sheetsから最新の戦略を読み込み、publish_at パラメータを返す。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.services.sheets_manager import SheetsManager
from app.utils.logger import logger


class UploadTimeOptimizer:
    """投稿時間を最適化し、publish_at を算出する"""

    def __init__(self):
        self.sheets = SheetsManager()

    async def get_optimal_publish_datetime(self) -> datetime | None:
        """
        Sheetsの投稿時間分析タブから最適な公開日時を算出

        Returns:
            最適な公開日時（UTC）。データがない場合はNone。
        """
        try:
            await self.sheets.authenticate()

            result = (
                self.sheets.service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self.sheets.spreadsheet_id,
                    range="投稿時間分析!A:F",
                )
                .execute()
            )

            values = result.get("values", [])
            if len(values) <= 1:
                logger.info("投稿時間分析データなし（デフォルト使用）")
                return self._default_publish_time()

            # 最新のデータを読む（最終行グループ）
            headers = values[0]
            latest_row = values[-1]

            recommended_time = ""
            for i, header in enumerate(headers):
                if header == "推奨投稿時間" and i < len(latest_row):
                    recommended_time = latest_row[i]
                    break

            if not recommended_time:
                return self._default_publish_time()

            # "水曜日 17:00 JST" 形式をパース
            return self._parse_recommended_time(recommended_time)

        except Exception as e:
            logger.warning(f"投稿時間最適化データの読み込みに失敗: {e}")
            return self._default_publish_time()

    def _parse_recommended_time(self, time_str: str) -> datetime | None:
        """
        "水曜日 17:00 JST" 形式の文字列から次の公開日時（UTC）を算出

        Args:
            time_str: 推奨投稿時間文字列

        Returns:
            次の公開日時（UTC）
        """
        day_map = {
            "月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6,
        }

        try:
            # 曜日を抽出
            target_weekday = None
            for day_char, idx in day_map.items():
                if day_char in time_str:
                    target_weekday = idx
                    break

            if target_weekday is None:
                logger.warning(f"曜日をパースできません: {time_str}")
                return self._default_publish_time()

            # 時間を抽出
            import re
            hour_match = re.search(r"(\d{1,2}):", time_str)
            target_hour = int(hour_match.group(1)) if hour_match else 17

            # 次の該当曜日を計算
            today = datetime.now()
            days_ahead = target_weekday - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7

            next_date = today + timedelta(days=days_ahead)
            publish_jst = next_date.replace(
                hour=target_hour, minute=0, second=0, microsecond=0
            )

            # JST→UTC (-9h)
            publish_utc = publish_jst - timedelta(hours=9)

            logger.info(
                f"最適公開日時: {publish_jst.strftime('%Y-%m-%d %H:%M')} JST "
                f"(UTC: {publish_utc.strftime('%Y-%m-%d %H:%M')})"
            )

            return publish_utc

        except Exception as e:
            logger.warning(f"推奨時間パース失敗: {e}")
            return self._default_publish_time()

    @staticmethod
    def _default_publish_time() -> datetime:
        """デフォルトの公開日時（次の水曜日17:00 JST）"""
        today = datetime.now()
        days_ahead = 2 - today.weekday()  # 水曜日 = 2
        if days_ahead <= 0:
            days_ahead += 7
        next_wed = today + timedelta(days=days_ahead)
        publish_jst = next_wed.replace(hour=17, minute=0, second=0, microsecond=0)
        publish_utc = publish_jst - timedelta(hours=9)

        logger.info(
            f"デフォルト公開日時: {publish_jst.strftime('%Y-%m-%d %H:%M')} JST"
        )
        return publish_utc
