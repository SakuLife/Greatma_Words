"""
Pydantic models for data validation and serialization.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    """Project status enumeration."""

    CREATED = "created"
    SCRIPT_GENERATED = "script_generated"
    IMAGES_GENERATED = "images_generated"
    AUDIO_GENERATED = "audio_generated"
    VIDEO_GENERATED = "video_generated"
    UPLOADED = "uploaded"
    FAILED = "failed"


class SubtitleLine(BaseModel):
    """A single subtitle line with timing."""

    text: str = Field(..., description="Subtitle text (1行、自然な区切り)")
    start_time: float = Field(..., description="Start time in seconds (relative to section start)")
    duration: float = Field(..., description="Duration in seconds")


class ScriptSection(BaseModel):
    """A section of the video script."""

    title: str = Field(..., description="Section title (e.g., 'e', ',1�')")
    narration: str = Field(..., description="Narration text to be read")
    scene_description: str = Field(..., description="Visual description for this section")
    duration_seconds: float = Field(..., description="Estimated duration in seconds")
    subtitles: list[SubtitleLine] = Field(
        default_factory=list,
        description="Subtitle lines with timing (自然な区切りで1行ずつ)",
    )


class VideoScript(BaseModel):
    """Complete video script with sections."""

    topic: str = Field(..., description="Main topic of the video")
    person_name: str = Field(..., description="Main person/philosopher featured")
    total_duration_minutes: float = Field(..., description="Target duration in minutes")
    sections: list[ScriptSection] = Field(..., description="Script sections in order")

    @property
    def total_narration(self) -> str:
        """Get complete narration text."""
        return "\n\n".join(section.narration for section in self.sections)


class ImageGenerationRequest(BaseModel):
    """Request for generating an image."""

    prompt: str = Field(..., description="Image generation prompt")
    person_name: str = Field(..., description="Person name for the image")
    background_color: str = Field(default="#1a1a2e", description="Background color hex")
    output_path: Path = Field(..., description="Where to save the generated image")


class VideoMetadata(BaseModel):
    """Metadata for YouTube upload."""

    title: str = Field(..., max_length=100, description="Video title")
    description: str = Field(..., max_length=5000, description="Video description")
    tags: list[str] = Field(default_factory=list, max_items=500, description="Video tags")
    category_id: int = Field(default=22, description="YouTube category ID")
    privacy_status: str = Field(default="private", description="Privacy: public/private/unlisted")
    publish_at: Optional[datetime] = Field(
        default=None,
        description="Scheduled publish time (ISO 8601 format). Must be in the future and privacy must be public/unlisted."
    )


class Project(BaseModel):
    """Complete project information."""

    project_id: str = Field(..., description="Unique project identifier")
    topic: str = Field(..., description="Video topic")
    person_name: str = Field(..., description="Featured person name")
    status: ProjectStatus = Field(default=ProjectStatus.CREATED)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # File paths
    project_dir: Path = Field(..., description="Project directory path")
    script_path: Optional[Path] = None
    images_dir: Optional[Path] = None
    audio_dir: Optional[Path] = None
    video_path: Optional[Path] = None
    thumbnail_path: Optional[Path] = None

    # Generated content
    script: Optional[VideoScript] = None
    video_metadata: Optional[VideoMetadata] = None
    youtube_video_id: Optional[str] = None

    class Config:
        use_enum_values = True


class GenerationConfig(BaseModel):
    """Configuration for video generation."""

    topic: str = Field(..., description="Main topic to generate video about")
    person_name: str = Field(..., description="Person/philosopher to feature")
    target_duration_minutes: int = Field(default=15, ge=5, le=30)
    llm_model: str = Field(default="models/gemini-pro-latest")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    voicevox_speaker_id: int = Field(default=13)  # 青山龍星
    upload_to_youtube: bool = Field(default=False)
    youtube_privacy: str = Field(default="private")
