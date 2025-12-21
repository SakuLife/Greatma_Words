"""
Interactive script editor using chat interface.
Allows users to create and edit scripts through conversation with AI.
"""

import json
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from openai import OpenAI
import google.generativeai as genai

from app.config import settings
from app.models.schemas import VideoScript
from app.utils.logger import logger


class InteractiveScriptEditor:
    """Interactive script editor with chat interface."""

    def __init__(self):
        """Initialize interactive script editor."""
        self.openai_client = None
        self.anthropic_client = None
        self.gemini_enabled = False
        self.conversation_history = []

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

    async def start_interactive_session(
        self,
        topic: str,
        person_name: str,
        duration_minutes: int = 15,
        model: str | None = None,
    ) -> VideoScript:
        """
        Start an interactive script editing session.

        Args:
            topic: Main topic for the video
            person_name: Person/philosopher to feature
            duration_minutes: Target duration in minutes
            model: LLM model to use

        Returns:
            Final VideoScript instance
        """
        model = model or settings.default_llm_model

        # Initialize conversation
        system_prompt = self._create_system_prompt(topic, person_name, duration_minutes)
        self.conversation_history = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]

        # Initial draft
        initial_prompt = f"""
以下のテーマで台本を作成してください：
- 人物: {person_name}
- テーマ: {topic}
- 目標時間: {duration_minutes}分

まず、最初のドラフトを作成してください。JSON形式で出力してください。
"""

        initial_response = await self._send_message(initial_prompt, model)
        self.conversation_history.append({"role": "user", "content": initial_prompt})
        self.conversation_history.append({"role": "assistant", "content": initial_response})

        # Parse initial script
        script = self._parse_script_response(initial_response)

        return script

    async def continue_conversation(
        self, user_message: str, model: str | None = None
    ) -> tuple[str, Optional[VideoScript]]:
        """
        Continue the conversation and optionally update the script.

        Args:
            user_message: User's message/instruction
            model: LLM model to use

        Returns:
            Tuple of (AI response, updated script if JSON detected)
        """
        model = model or settings.default_llm_model

        self.conversation_history.append({"role": "user", "content": user_message})

        response = await self._send_message(user_message, model)
        self.conversation_history.append({"role": "assistant", "content": response})

        # Try to parse as script if JSON detected
        script = None
        if "```json" in response or '"sections"' in response:
            try:
                script = self._parse_script_response(response)
            except Exception as e:
                logger.debug(f"Could not parse response as script: {e}")

        return response, script

    async def apply_edits(
        self, edit_instruction: str, current_script: VideoScript, model: str | None = None
    ) -> VideoScript:
        """
        Apply edits to the current script based on user instruction.

        Args:
            edit_instruction: User's edit instruction
            current_script: Current script to edit
            model: LLM model to use

        Returns:
            Updated VideoScript
        """
        model = model or settings.default_llm_model

        prompt = f"""
現在の台本を以下の指示に従って編集してください：

【編集指示】
{edit_instruction}

【現在の台本（JSON形式）】
{json.dumps(current_script.model_dump(), ensure_ascii=False, indent=2)}

編集後の台本をJSON形式で出力してください。
"""

        response = await self._send_message(prompt, model)
        updated_script = self._parse_script_response(response)

        return updated_script

    async def _send_message(self, message: str, model: str) -> str:
        """Send a message to the AI and get response."""
        if "gpt" in model.lower():
            if not self.openai_client:
                raise ValueError("OpenAI API key not configured")
            return await self._send_with_openai(message, model)
        elif "claude" in model.lower():
            if not self.anthropic_client:
                raise ValueError("Anthropic API key not configured")
            return await self._send_with_anthropic(message, model)
        elif "gemini" in model.lower():
            if not self.gemini_enabled:
                raise ValueError("Gemini API key not configured")
            return await self._send_with_gemini(message, model)
        else:
            raise ValueError(f"Unsupported model: {model}")

    async def _send_with_openai(self, message: str, model: str) -> str:
        """Send message using OpenAI API."""
        # Prepare messages (system + conversation history)
        messages = []
        for msg in self.conversation_history:
            if msg["role"] == "system":
                messages.append(msg)
            elif msg["role"] == "user":
                messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                messages.append({"role": "assistant", "content": msg["content"]})

        # Add current message if not already in history
        if messages[-1]["content"] != message:
            messages.append({"role": "user", "content": message})

        response = self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=settings.default_temperature,
        )

        return response.choices[0].message.content

    async def _send_with_anthropic(self, message: str, model: str) -> str:
        """Send message using Anthropic API."""
        # Prepare messages (skip system, it goes in system parameter)
        system_msg = None
        messages = []

        for msg in self.conversation_history:
            if msg["role"] == "system":
                system_msg = msg["content"]
            elif msg["role"] == "user":
                messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                messages.append({"role": "assistant", "content": msg["content"]})

        # Add current message if not already in history
        if not messages or messages[-1]["content"] != message:
            messages.append({"role": "user", "content": message})

        response = self.anthropic_client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=settings.default_temperature,
            system=system_msg or "",
            messages=messages,
        )

        return response.content[0].text

    async def _send_with_gemini(self, message: str, model: str) -> str:
        """Send message using Gemini API."""
        system_msg = None
        history = []

        for msg in self.conversation_history:
            if msg["role"] == "system":
                system_msg = msg["content"]
                continue
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [msg["content"]]})

        if not history or history[-1]["parts"][0] != message:
            history.append({"role": "user", "parts": [message]})

        model_name = model if model.startswith("models/") else f"models/{model}"
        model_obj = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_msg or None,
        )
        chat = model_obj.start_chat(history=history)
        response = chat.send_message(message, generation_config={"temperature": settings.default_temperature})
        return response.text

    def _parse_script_response(self, response: str) -> VideoScript:
        """Parse AI response into VideoScript object."""
        # Extract JSON from response
        json_text = response

        # Remove markdown code blocks if present
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()

        # Parse JSON
        try:
            script_data = json.loads(json_text)
            script = VideoScript(**script_data)
            return script
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse script: {e}")
            logger.debug(f"Response text: {response[:500]}")
            raise ValueError(f"Failed to parse script from response: {e}") from e

    def _create_system_prompt(
        self, topic: str, person_name: str, duration_minutes: int
    ) -> str:
        """Create system prompt for interactive editing."""
        base_prompt = self.prompt_template.replace("{{TOPIC}}", topic)
        base_prompt = base_prompt.replace("{{PERSON_NAME}}", person_name)
        base_prompt = base_prompt.replace("{{DURATION_MINUTES}}", str(duration_minutes))

        interactive_instructions = """

# インタラクティブ編集モード

あなたは台本作成のアシスタントです。ユーザーと対話しながら台本を作成・編集します。

- ユーザーの指示に従って台本を修正・改善してください
- 質問があれば、積極的に質問してください
- 台本を更新する際は、必ずJSON形式で出力してください
- ユーザーが「完成」「OK」「これでいい」などと言ったら、最終版の台本をJSON形式で出力してください
"""

        return base_prompt + interactive_instructions

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
