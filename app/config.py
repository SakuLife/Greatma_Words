"""
Configuration management for GreatMan Words Generator.
Loads settings from environment variables using Pydantic.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "GreatMan Words Generator"
    app_env: Literal["development", "production"] = "development"
    debug: bool = True

    # AI API Keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # Image Generation
    use_dalle: bool = True
    skip_image_generation: bool = False  # 画像生成をスキップ（既存画像を使用）
    stability_api_key: str = ""
    replicate_api_key: str = ""

    # KIEAI API
    kieai_api_key: str = ""
    kieai_api_url: str = "https://api.kie.ai/api/v1"
    use_kieai: bool = False  # KIEAI APIを使用するか
    kieai_model: str = "google/nano-banana"  # nanobananaモデル（安い、文字なし）

    # VOICEVOX
    voicevox_api_url: str = "http://localhost:50021"
    voicevox_speaker_id: int = 13  # 青山龍星（VOICEVOX 0.13.0以降）�

    # YouTube API
    youtube_client_secrets_file: str = "client_secrets.json"
    youtube_oauth_scopes: str = "https://www.googleapis.com/auth/youtube.upload"
    youtube_default_category: int = 22  # People & Blogs
    youtube_default_privacy: Literal["public", "private", "unlisted"] = "private"

    # Google Drive API
    google_client_secrets_file: str = "client_secrets.json"
    google_drive_folder_id: str = ""  # Google Drive folder ID for uploads

    # Google Sheets API
    google_sheets_id: str = ""  # Google Sheets spreadsheet ID for task management

    # Discord Webhook
    discord_webhook_url: str = ""  # Discord webhook URL for notifications

    # File Paths
    data_dir: Path = Field(default=Path("./data"))
    projects_dir: Path = Field(default=Path("./data/projects"))
    templates_dir: Path = Field(default=Path("./data/templates"))

    # Video Settings
    video_resolution: str = "1920x1080"
    video_fps: int = 30
    video_bitrate: str = "5000k"
    default_background_color: str = "#1a1a2e"
    default_text_color: str = "#ffffff"

    # Script Generation
    default_script_length: int = 15  # minutes
    # Gemini Pro: 広く互換性のある安定モデル
    default_llm_model: str = "models/gemini-pro-latest"
    default_temperature: float = 0.7

    # Thumbnail Generation
    use_thumbnail_generation: bool = True
    skip_thumbnail_generation: bool = False  # サムネイル生成をスキップ（手動生成する場合）
    thumbnail_provider: Literal["nanobanana", "dalle", "stable-diffusion"] = "nanobanana"
    nanobanana_api_key: str = ""
    nanobanana_api_url: str = "https://api.nanobanana.ai/v1"

    @property
    def video_width(self) -> int:
        """Extract video width from resolution string."""
        return int(self.video_resolution.split("x")[0])

    @property
    def video_height(self) -> int:
        """Extract video height from resolution string."""
        return int(self.video_resolution.split("x")[1])

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        (self.templates_dir / "prompts").mkdir(exist_ok=True)
        (self.templates_dir / "slide_templates").mkdir(exist_ok=True)


# Global settings instance
settings = Settings()
