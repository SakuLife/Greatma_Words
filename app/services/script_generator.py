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
    ) -> VideoScript:
        """
        Generate a video script using LLM API.

        Args:
            topic: Main topic for the video
            person_name: Person/philosopher to feature
            duration_minutes: Target duration in minutes
            model: LLM model to use (defaults to config setting)
            temperature: Temperature for generation (defaults to config setting)

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

        # Prepare prompt
        prompt = self._prepare_prompt(topic, person_name, duration_minutes)

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
            script = VideoScript(**script_data)
            logger.info(f"Successfully generated script with {len(script.sections)} sections")
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
        self, topic: str, person_name: str, duration_minutes: int
    ) -> str:
        """Prepare the prompt by substituting template variables."""
        prompt = self.prompt_template.replace("{{TOPIC}}", topic)
        prompt = prompt.replace("{{PERSON_NAME}}", person_name)
        prompt = prompt.replace("{{DURATION_MINUTES}}", str(duration_minutes))
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
