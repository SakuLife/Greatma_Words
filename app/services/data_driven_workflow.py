"""
Data-driven video generation workflow.
Uses YouTube analytics to inform content creation decisions.
"""

from app.config import settings
from app.services.content_analyzer import ContentAnalyzer
from app.services.dynamic_script_builder import DynamicScriptBuilder
from app.services.person_info_fetcher import PersonInfoFetcher
from app.services.script_generator import ScriptGenerator
from app.services.sheets_manager import SheetsManager
from app.utils.logger import logger
from app.utils.person_titles import register_person_info


class DataDrivenWorkflow:
    """Orchestrates data-driven video generation."""

    def __init__(self):
        """Initialize workflow services."""
        self.content_analyzer = ContentAnalyzer()
        self.person_fetcher = PersonInfoFetcher()
        self.script_generator = ScriptGenerator()
        self.dynamic_script_builder = DynamicScriptBuilder()
        self.sheets_manager = SheetsManager() if settings.google_sheets_id else None

    async def suggest_next_video(
        self, exclude_persons: list[str] | None = None
    ) -> dict:
        """
        Suggest next video topic based on channel performance.

        Args:
            exclude_persons: List of persons to exclude from suggestions

        Returns:
            Dictionary with video suggestion
        """
        logger.info("Starting data-driven video suggestion...")

        # Get recently featured persons from Google Sheets
        if self.sheets_manager and not exclude_persons:
            exclude_persons = await self._get_recently_featured_persons()
            if exclude_persons:
                logger.info(f"Excluding recently featured persons: {', '.join(exclude_persons)}")

        # Step 1: Analyze channel performance
        logger.info("Step 1: Analyzing channel performance...")
        try:
            analysis_text = await self.content_analyzer.get_content_suggestions_for_llm()
            logger.info("✅ Channel analysis complete")
            # 分析結果をログに出力
            logger.info("=" * 60)
            logger.info("[YouTube分析結果 - AI提案に使用]")
            for line in analysis_text.strip().split("\n"):
                if line.strip():
                    logger.info(f"  {line}")
            logger.info("=" * 60)
        except Exception as e:
            logger.warning(f"⚠️ YouTube API分析失敗（Sheetsフォールバック）: {e}")
            analysis_text = await self._get_analysis_from_sheets()
            if analysis_text:
                logger.info("✅ Sheetsデータで分析テキストを構築")
            else:
                logger.warning("Sheetsにもデータなし。最小限の情報で続行")
                analysis_text = (
                    "# チャンネル分析\n"
                    "分析データは利用できません。\n"
                    "偉人・哲学・ビジネスをテーマにしたYouTubeチャンネルです。\n"
                    "視聴者層は30-44歳のビジネスパーソンが中心です。\n"
                )

        # Step 2: Get person suggestion from AI
        logger.info("Step 2: Getting person suggestion from AI...")
        person_suggestion = await self.person_fetcher.suggest_next_person(
            analysis_context=analysis_text,
            exclude_persons=exclude_persons,
        )

        logger.info(f"Person suggested: {person_suggestion['person_name']}")
        logger.info(f"Theme: {person_suggestion['suggested_theme']}")
        logger.info(f"Reason: {person_suggestion['reason']}")

        # Step 3: Get detailed person information
        logger.info("Step 3: Fetching detailed person information...")
        person_info = await self.person_fetcher.get_person_info(
            person_suggestion["person_name"]
        )

        logger.info(f"Person info: {person_info['title']}")

        # 取得した情報を登録（画像生成で使用）
        register_person_info(
            person_name=person_suggestion["person_name"],
            title=person_info.get("title"),
            quote=person_info.get("famous_quote"),
            appearance=person_info.get("appearance"),
        )

        # Combine all information
        suggestion = {
            "person_name": person_suggestion["person_name"],
            "suggested_theme": person_suggestion["suggested_theme"],
            "person_title": person_info["title"],
            "famous_quote": person_info["famous_quote"],
            "person_info": person_info,
            "suggestion_reason": person_suggestion["reason"],
            "expected_engagement": person_suggestion.get("expected_engagement", "中"),
            "keywords": person_suggestion.get("keywords", []),
        }

        logger.info("Video suggestion complete")
        return suggestion

    async def generate_data_driven_script(
        self,
        person_name: str | None = None,
        topic: str | None = None,
        duration_minutes: int = 15,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> tuple[dict, any]:
        """
        Generate script with data-driven suggestions.

        Args:
            person_name: Person name (if None, will be suggested)
            topic: Video topic (if None, will be suggested)
            duration_minutes: Target duration in minutes
            model: LLM model to use
            temperature: LLM temperature

        Returns:
            Tuple of (suggestion_dict, script_object)
        """
        logger.info("Starting data-driven script generation...")

        # Get suggestion if person/topic not provided
        if not person_name or not topic:
            logger.info("Person or topic not provided, getting AI suggestion...")
            suggestion = await self.suggest_next_video()

            if not person_name:
                person_name = suggestion["person_name"]
                logger.info(f"Using suggested person: {person_name}")

            if not topic:
                topic = suggestion["suggested_theme"]
                logger.info(f"Using suggested theme: {topic}")
        else:
            # Get person info for provided person
            logger.info(f"Using provided person: {person_name}, topic: {topic}")
            person_info = await self.person_fetcher.get_person_info(person_name)

            # 取得した情報を登録（画像生成で使用）
            register_person_info(
                person_name=person_name,
                title=person_info.get("title"),
                quote=person_info.get("famous_quote"),
                appearance=person_info.get("appearance"),
            )

            suggestion = {
                "person_name": person_name,
                "suggested_theme": topic,
                "person_title": person_info["title"],
                "famous_quote": person_info["famous_quote"],
                "person_info": person_info,
                "suggestion_reason": "ユーザー指定",
                "expected_engagement": "不明",
                "keywords": person_info.get("keywords", []),
            }

        # Get channel analysis for script context (optional)
        try:
            logger.info("Getting channel analysis for script context...")
            analysis_text = await self.content_analyzer.get_content_suggestions_for_llm()
            logger.info("✅ Channel analysis retrieved successfully")
            # 分析結果をログに出力（台本生成に使用されるデータ）
            logger.info("=" * 60)
            logger.info("[台本生成に使用する分析データ]")
            for line in analysis_text.strip().split("\n"):
                if line.strip():
                    logger.info(f"  {line}")
            logger.info("=" * 60)
        except Exception as e:
            logger.warning(f"⚠️ YouTube API分析失敗（Sheetsフォールバック）: {e}")
            sheets_analysis = await self._get_analysis_from_sheets()
            analysis_text = sheets_analysis or "チャンネル分析データは利用できません。"

        # 動的プロンプト生成を試行
        dynamic_prompt = None
        try:
            # Sheetsから最新の戦略データを読み込み
            channel_analysis = None
            competitor_analysis = None

            if self.sheets_manager:
                try:
                    await self.sheets_manager.authenticate()
                    strategies = await self.sheets_manager.read_latest_strategy()
                    if strategies:
                        logger.info(f"最新戦略を読み込み: {len(strategies)}件")
                except Exception as e:
                    logger.debug(f"戦略読み込みスキップ: {e}")

            # 過去の冒頭テキストを取得（重複回避用）
            previous_openings = await self._get_previous_openings()

            # 動的プロンプトを構築
            dynamic_prompt = self.dynamic_script_builder.build_dynamic_prompt(
                person_name=person_name,
                topic=topic,
                duration_minutes=duration_minutes,
                channel_analysis=channel_analysis,
                competitor_analysis=competitor_analysis,
                previous_openings=previous_openings,
            )
            # 選択された戦略名をsuggestに保存（スプシ記録用）
            suggestion["hook_strategy"] = self.dynamic_script_builder.last_hook_key
            suggestion["structure_pattern"] = self.dynamic_script_builder.last_structure_key
            logger.info("動的プロンプト生成成功")

        except Exception as e:
            logger.warning(f"動的プロンプト生成に失敗（固定テンプレートを使用）: {e}")

        # 分析コンテキストを追加
        enhanced_prompt_context = f"""
【チャンネル分析に基づく指針】
{analysis_text}

【対象人物の情報】
- 人物名: {suggestion['person_name']}
- 肩書: {suggestion['person_title']}
- 代表的な名言: {suggestion['famous_quote']}
- 関連キーワード: {', '.join(suggestion.get('keywords', []))}

上記の分析結果と人物情報を踏まえて、視聴者の興味を引き、高いエンゲージメントが期待できる台本を生成してください。
"""

        # Generate script with enhanced context（動的プロンプト or 固定テンプレート）
        logger.info("Generating script with data-driven context...")
        script = await self.script_generator.generate_script(
            topic=topic,
            person_name=person_name,
            duration_minutes=duration_minutes,
            model=model,
            temperature=temperature,
            additional_context=enhanced_prompt_context,
            full_prompt_override=dynamic_prompt,
        )

        logger.info("Data-driven script generation complete")
        return suggestion, script

    async def _get_recently_featured_persons(
        self, lookback_count: int = 50
    ) -> list[str]:
        """
        Get list of recently featured persons from YouTube channel.

        Args:
            lookback_count: Number of recent videos to check

        Returns:
            List of person names to exclude
        """
        try:
            logger.info(f"Fetching last {lookback_count} videos from YouTube...")

            # Get channel stats with recent videos from YouTube Analytics
            channel_stats = await self.content_analyzer.youtube_analytics.get_channel_stats()

            if not channel_stats or not channel_stats.videos:
                logger.info("No video history found on YouTube")
                return []

            # Get most recent videos (already sorted by date in get_all_videos)
            recent_videos = channel_stats.videos[:lookback_count]

            # Extract person names from video titles
            # Expected format: "人物名・テーマ" or "人物名の哲学 - ..."
            person_names = []
            for video in recent_videos:
                title = video.title

                # Method 1: Split by "・" (most common format)
                if "・" in title:
                    person_name = title.split("・")[0].strip()
                # Method 2: Split by "の" (e.g., "ジェフ・ベゾスの哲学")
                elif "の" in title:
                    person_name = title.split("の")[0].strip()
                # Method 3: Use first part before "-" or ":"
                elif " - " in title:
                    person_name = title.split(" - ")[0].strip()
                elif "：" in title:
                    person_name = title.split("：")[0].strip()
                else:
                    # If no delimiter, skip this video
                    logger.debug(f"Could not extract person name from: {title}")
                    continue

                if person_name and person_name not in person_names:
                    person_names.append(person_name)
                    logger.debug(f"Extracted person: {person_name} from video: {title}")

            logger.info(f"Found {len(person_names)} recently featured persons from YouTube: {', '.join(person_names)}")
            return person_names

        except Exception as e:
            logger.warning(f"Failed to fetch recent persons from YouTube: {e}")
            logger.debug("Attempting fallback to Google Sheets...")

            # Fallback to Google Sheets if YouTube fails
            return await self._get_recently_featured_persons_from_sheets(lookback_count)

    async def _get_recently_featured_persons_from_sheets(
        self, lookback_count: int = 50
    ) -> list[str]:
        """
        Fallback method to get recently featured persons from Google Sheets.

        Args:
            lookback_count: Number of recent videos to check

        Returns:
            List of person names to exclude
        """
        if not self.sheets_manager:
            return []

        try:
            logger.info(f"Fetching last {lookback_count} videos from Google Sheets (fallback)...")

            # Authenticate if needed
            if not self.sheets_manager.service:
                await self.sheets_manager.authenticate()

            # Get video stats to find person names
            stats = await self.sheets_manager.get_video_stats()

            if not stats or stats.get("total_videos", 0) == 0:
                logger.info("No video history found in Sheets")
                return []

            # Read recent video logs
            range_name = "動画制作ログ!A:K"
            result = (
                self.sheets_manager.service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self.sheets_manager.spreadsheet_id,
                    range=range_name,
                )
                .execute()
            )

            values = result.get("values", [])

            if len(values) <= 1:  # Only header or empty
                logger.info("No video data found in Sheets")
                return []

            # Extract person names from recent videos (column B = index 1)
            # Skip header row, get last N videos
            recent_videos = values[-lookback_count:] if len(values) > lookback_count else values[1:]

            person_names = []
            for row in recent_videos:
                if len(row) > 1 and row[1]:  # Check if person name exists
                    person_name = row[1].strip()
                    if person_name and person_name not in person_names:
                        person_names.append(person_name)

            logger.info(f"Found {len(person_names)} recently featured persons from Sheets")
            return person_names

        except Exception as e:
            logger.warning(f"Failed to fetch recent persons from Sheets: {e}")
            return []

    async def _get_previous_openings(self, limit: int = 5) -> list[str]:
        """
        過去の動画の冒頭テキストをスプシから取得する。

        Args:
            limit: 取得する最大件数

        Returns:
            冒頭テキストのリスト
        """
        if not self.sheets_manager:
            return []

        try:
            return await self.sheets_manager.get_previous_openings(limit=limit)
        except Exception as e:
            logger.debug(f"過去の冒頭テキスト取得スキップ: {e}")
            return []

    async def _get_analysis_from_sheets(self) -> str | None:
        """
        YouTube API失敗時にSheetsデータから分析テキストを構築するフォールバック。

        Returns:
            分析テキスト（Sheetsにデータがなければ None）
        """
        if not self.sheets_manager:
            return None

        try:
            if not self.sheets_manager.service:
                await self.sheets_manager.authenticate()

            lines = ["# チャンネル分析（Google Sheetsデータ）\n"]

            # 動画制作ログから基本統計
            stats = await self.sheets_manager.get_video_stats()
            if stats and stats.get("total_videos", 0) > 0:
                lines.append(f"## チャンネル概要")
                lines.append(f"- 総動画数: {stats['total_videos']}")

            # 動画制作ログから人物別パフォーマンスを集計
            try:
                result = (
                    self.sheets_manager.service.spreadsheets()
                    .values()
                    .get(
                        spreadsheetId=self.sheets_manager.spreadsheet_id,
                        range="動画制作ログ!A:K",
                    )
                    .execute()
                )
                values = result.get("values", [])
                if len(values) > 1:
                    lines.append(f"\n## 制作済み動画（直近）")
                    for row in values[-10:]:
                        if len(row) >= 3:
                            date = row[0] if row[0] else ""
                            person = row[1] if len(row) > 1 else ""
                            topic = row[2] if len(row) > 2 else ""
                            lines.append(f"- {date} {person} / {topic}")
            except Exception as e:
                logger.debug(f"動画ログ読み込みスキップ: {e}")

            # チャンネル詳細分析（週次で保存済み）
            try:
                result = (
                    self.sheets_manager.service.spreadsheets()
                    .values()
                    .get(
                        spreadsheetId=self.sheets_manager.spreadsheet_id,
                        range="チャンネル詳細分析!A:O",
                    )
                    .execute()
                )
                values = result.get("values", [])
                if len(values) > 1:
                    latest = values[-1]
                    headers = values[0]
                    lines.append(f"\n## チャンネル詳細分析（最新）")
                    for i, header in enumerate(headers):
                        if i < len(latest) and latest[i]:
                            lines.append(f"- {header}: {latest[i]}")
            except Exception as e:
                logger.debug(f"詳細分析読み込みスキップ: {e}")

            # コンテンツ戦略（週次で保存済み）
            try:
                strategies = await self.sheets_manager.read_latest_strategy()
                if strategies:
                    lines.append(f"\n## 最新コンテンツ戦略")
                    for s in strategies[:3]:
                        person = s.get("人物", "")
                        topic = s.get("テーマ", "")
                        hook = s.get("フック戦略", "")
                        lines.append(f"- {person} / {topic}（フック: {hook}）")
            except Exception as e:
                logger.debug(f"戦略読み込みスキップ: {e}")

            lines.append(
                "\n---\n"
                "上記のデータに基づいて、視聴者が興味を持ち、"
                "高いエンゲージメントが期待できるテーマと人物を選んでください。"
            )

            analysis = "\n".join(lines)
            logger.info(f"Sheetsフォールバック分析テキスト構築完了（{len(lines)}行）")
            return analysis

        except Exception as e:
            logger.warning(f"Sheetsフォールバック分析失敗: {e}")
            return None
