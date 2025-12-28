"""
Data-driven video generation workflow.
Uses YouTube analytics to inform content creation decisions.
"""

from app.config import settings
from app.services.content_analyzer import ContentAnalyzer
from app.services.person_info_fetcher import PersonInfoFetcher
from app.services.script_generator import ScriptGenerator
from app.services.sheets_manager import SheetsManager
from app.utils.logger import logger


class DataDrivenWorkflow:
    """Orchestrates data-driven video generation."""

    def __init__(self):
        """Initialize workflow services."""
        self.content_analyzer = ContentAnalyzer()
        self.person_fetcher = PersonInfoFetcher()
        self.script_generator = ScriptGenerator()
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
            logger.debug(f"Analysis:\n{analysis_text[:500]}...")
        except Exception as e:
            logger.error(f"❌ Failed to analyze channel performance: {e}")
            logger.error("Cannot suggest next video without performance data.")
            logger.error("To fix: Run 'python update_youtube_stats.py' to update statistics.")
            raise RuntimeError(
                "Channel performance analysis failed. "
                "Please ensure YouTube statistics are up to date in Google Sheets. "
                f"Error: {e}"
            ) from e

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
            logger.debug(f"Analysis preview: {analysis_text[:200]}...")
        except Exception as e:
            logger.error(f"❌ Failed to get channel analysis: {e}")
            logger.error("This means past video performance data is NOT being used for content optimization.")
            logger.error("To fix: Run 'python update_youtube_stats.py' to update statistics in Google Sheets.")
            import traceback
            logger.debug(traceback.format_exc())
            analysis_text = "チャンネル分析データは利用できません。"

        # Add analysis context to script generation
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

        # Generate script with enhanced context
        logger.info("Generating script with data-driven context...")
        script = await self.script_generator.generate_script(
            topic=topic,
            person_name=person_name,
            duration_minutes=duration_minutes,
            model=model,
            temperature=temperature,
            additional_context=enhanced_prompt_context,
        )

        logger.info("Data-driven script generation complete")
        return suggestion, script

    async def _get_recently_featured_persons(
        self, lookback_count: int = 10
    ) -> list[str]:
        """
        Get list of recently featured persons from Google Sheets.

        Args:
            lookback_count: Number of recent videos to check

        Returns:
            List of person names to exclude
        """
        if not self.sheets_manager:
            return []

        try:
            logger.info(f"Fetching last {lookback_count} videos from Google Sheets...")

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

            logger.info(f"Found {len(person_names)} recently featured persons")
            return person_names

        except Exception as e:
            logger.warning(f"Failed to fetch recent persons from Sheets: {e}")
            return []
