"""
Data-driven video generation workflow.
Uses YouTube analytics to inform content creation decisions.
"""

from app.services.content_analyzer import ContentAnalyzer
from app.services.person_info_fetcher import PersonInfoFetcher
from app.services.script_generator import ScriptGenerator
from app.utils.logger import logger


class DataDrivenWorkflow:
    """Orchestrates data-driven video generation."""

    def __init__(self):
        """Initialize workflow services."""
        self.content_analyzer = ContentAnalyzer()
        self.person_fetcher = PersonInfoFetcher()
        self.script_generator = ScriptGenerator()

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

        # Step 1: Analyze channel performance
        logger.info("Step 1: Analyzing channel performance...")
        analysis_text = await self.content_analyzer.get_content_suggestions_for_llm()

        logger.info("Channel analysis complete")
        logger.debug(f"Analysis:\n{analysis_text[:500]}...")

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
        except Exception as e:
            logger.warning(f"Failed to get channel analysis, continuing without it: {e}")
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
