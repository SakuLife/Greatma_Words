"""
Script generation service using LLM APIs.
"""

import json
from pathlib import Path

from openai import OpenAI
from anthropic import Anthropic
import google.generativeai as genai

from app.config import settings
from app.models.schemas import VideoScript
from app.utils.logger import logger


class ScriptGenerator:
    """Generates video scripts using LLM APIs."""

    def __init__(self):
        """Initialize script generator with API clients."""
        self.openai_client = None
        self.anthropic_client = None
        self.gemini_enabled = False

        if settings.openai_api_key:
            self.openai_client = OpenAI(api_key=settings.openai_api_key)

        if settings.anthropic_api_key:
            self.anthropic_client = Anthropic(api_key=settings.anthropic_api_key)

        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.gemini_enabled = True

        # Load prompt template
        template_path = settings.templates_dir / "prompts" / "script_template.md"
        if template_path.exists():
            with open(template_path, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()
        else:
            logger.warning(f"Prompt template not found at {template_path}")
            self.prompt_template = self._get_default_template()

    async def generate_script(
        self,
        topic: str,
        person_name: str,
        duration_minutes: int = 15,
        model: str | None = None,
        temperature: float | None = None,
        additional_context: str | None = None,
        full_prompt_override: str | None = None,
    ) -> VideoScript:
        """
        Generate a video script using LLM API.

        Args:
            topic: Main topic for the video
            person_name: Person/philosopher to feature
            duration_minutes: Target duration in minutes
            model: LLM model to use (defaults to config setting)
            temperature: Temperature for generation (defaults to config setting)
            additional_context: Additional context for script generation (e.g., channel analytics)
            full_prompt_override: 動的プロンプトで完全にオーバーライドする場合に使用

        Returns:
            Generated VideoScript instance

        Raises:
            ValueError: If no API key is configured
            RuntimeError: If script generation fails
        """
        model = model or settings.default_llm_model
        temperature = temperature or settings.default_temperature

        logger.info(
            f"Generating script for topic='{topic}', person='{person_name}', "
            f"duration={duration_minutes}min, model={model}"
        )

        # Prepare prompt（動的プロンプトが指定されていればそちらを使用）
        if full_prompt_override:
            prompt = full_prompt_override
            if additional_context:
                prompt = f"{additional_context}\n\n{prompt}"
            logger.info("動的プロンプトを使用")
        else:
            prompt = self._prepare_prompt(topic, person_name, duration_minutes, additional_context)

        # Generate using appropriate API
        if "gpt" in model.lower():
            if not self.openai_client:
                raise ValueError("OpenAI API key not configured")
            script_json = await self._generate_with_openai(prompt, model, temperature)
        elif "claude" in model.lower():
            if not self.anthropic_client:
                raise ValueError("Anthropic API key not configured")
            script_json = await self._generate_with_anthropic(prompt, model, temperature)
        elif "gemini" in model.lower():
            if not self.gemini_enabled:
                raise ValueError("Gemini API key not configured")
            script_json = await self._generate_with_gemini(prompt, model, temperature)
        else:
            raise ValueError(f"Unsupported model: {model}")

        # Parse and validate response
        try:
            script_data = json.loads(script_json)

            # AIがlistを返した場合の正規化
            if isinstance(script_data, list):
                logger.warning("AIがlistを返しました。dict形式に正規化します")
                # listの中にdictが1つだけある場合はそれを使う
                if len(script_data) == 1 and isinstance(script_data[0], dict):
                    script_data = script_data[0]
                # listがsectionsの配列の場合（トップレベルキーが欠落）
                elif all(isinstance(item, dict) and "narration" in item for item in script_data):
                    script_data = {
                        "topic": topic,
                        "person_name": person_name,
                        "total_duration_minutes": duration_minutes,
                        "sections": script_data,
                    }
                else:
                    raise ValueError(
                        f"AIのレスポンスが予期しないlist形式です: {str(script_data)[:200]}"
                    )

            if not isinstance(script_data, dict):
                raise ValueError(
                    f"AIのレスポンスがdict形式ではありません: type={type(script_data).__name__}"
                )

            script = VideoScript(**script_data)
            logger.info(f"Successfully generated script with {len(script.sections)} sections")

            # 台本の内容をログに出力
            logger.info("=" * 60)
            logger.info("[台本内容]")
            total_chars = 0
            for i, section in enumerate(script.sections, 1):
                section_chars = len(section.narration)
                total_chars += section_chars
                logger.info(f"  セクション{i}: {section.title}")
                narration_preview = section.narration[:100] + "..." if len(section.narration) > 100 else section.narration
                logger.info(f"    内容: {narration_preview}")
                logger.info(f"    長さ: {section.duration_seconds}秒 / 文字数: {section_chars}文字")
            total_duration = sum(s.duration_seconds for s in script.sections)
            logger.info(f"  合計時間: {total_duration}秒 ({total_duration/60:.1f}分)")
            logger.info(f"  合計文字数: {total_chars}文字")

            # ナレーション長チェック（VOICEVOX: 約350文字/分）
            chars_per_minute = 350
            expected_chars = duration_minutes * chars_per_minute
            estimated_minutes = total_chars / chars_per_minute
            logger.info(f"  推定読み上げ時間: {estimated_minutes:.1f}分（目標: {duration_minutes}分）")

            if total_chars < expected_chars * 0.7:
                logger.warning(
                    f"⚠️ ナレーション文字数が不足しています！"
                    f"（{total_chars}文字 / 目標{expected_chars}文字 = {total_chars/expected_chars*100:.0f}%）"
                    f"動画が目標の{duration_minutes}分より大幅に短くなる可能性があります。"
                )
            elif total_chars < expected_chars * 0.85:
                logger.warning(
                    f"⚠️ ナレーション文字数がやや少なめです"
                    f"（{total_chars}文字 / 目標{expected_chars}文字 = {total_chars/expected_chars*100:.0f}%）"
                )
            else:
                logger.info(f"  ✅ 文字数OK（{total_chars/expected_chars*100:.0f}%）")

            logger.info("=" * 60)

            return script
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse script: {e}")
            raise RuntimeError(f"Failed to parse generated script: {e}") from e

    async def _generate_with_openai(
        self, prompt: str, model: str, temperature: float
    ) -> str:
        """Generate script using OpenAI API."""
        try:
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional scriptwriter for educational YouTube videos. "
                        "Always respond with valid JSON format as specified in the prompt.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            logger.debug(f"OpenAI response received: {len(content)} characters")
            return content

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise RuntimeError(f"OpenAI API error: {e}") from e

    async def _generate_with_anthropic(
        self, prompt: str, model: str, temperature: float
    ) -> str:
        """Generate script using Anthropic API."""
        try:
            message = self.anthropic_client.messages.create(
                model=model,
                max_tokens=4096,
                temperature=temperature,
                system="You are a professional scriptwriter for educational YouTube videos. "
                "Always respond with valid JSON format as specified in the prompt.",
                messages=[{"role": "user", "content": prompt}],
            )

            content = message.content[0].text
            logger.debug(f"Anthropic response received: {len(content)} characters")

            # Extract JSON if wrapped in code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            return content

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise RuntimeError(f"Anthropic API error: {e}") from e

    async def _generate_with_gemini(
        self, prompt: str, model: str, temperature: float
    ) -> str:
        """Generate script using Gemini API."""
        try:
            model_name = model if model.startswith("models/") else f"models/{model}"
            model_obj = genai.GenerativeModel(model_name=model_name)
            response = model_obj.generate_content(
                prompt,
                generation_config={
                    "temperature": temperature,
                    "response_mime_type": "application/json",
                },
            )

            content = response.text
            logger.debug(f"Gemini response received: {len(content)} characters")

            # Extract JSON if wrapped in code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            return content

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise RuntimeError(f"Gemini API error: {e}") from e

    def _prepare_prompt(
        self, topic: str, person_name: str, duration_minutes: int, additional_context: str | None = None
    ) -> str:
        """Prepare the prompt by substituting template variables."""
        prompt = self.prompt_template.replace("{{TOPIC}}", topic)
        prompt = prompt.replace("{{PERSON_NAME}}", person_name)
        prompt = prompt.replace("{{DURATION_MINUTES}}", str(duration_minutes))

        # Add additional context if provided
        if additional_context:
            prompt = f"{additional_context}\n\n{prompt}"

        return prompt

    @staticmethod
    def _get_default_template() -> str:
        """Return a default prompt template if file is not found."""
        return """Generate a video script about {{TOPIC}} featuring {{PERSON_NAME}}.
The script should be approximately {{DURATION_MINUTES}} minutes long.

Output in JSON format with the following structure:
{
  "topic": "...",
  "person_name": "...",
  "total_duration_minutes": ...,
  "sections": [
    {
      "title": "...",
      "narration": "...",
      "scene_description": "...",
      "duration_seconds": ...
    }
  ]
}"""
