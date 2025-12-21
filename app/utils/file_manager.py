"""
File and folder management utilities.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import settings
from app.models.schemas import Project, ProjectStatus


class FileManager:
    """Manages project files and directories."""

    def __init__(self):
        """Initialize file manager and ensure base directories exist."""
        settings.ensure_directories()

    def create_project(self, topic: str, person_name: str) -> Project:
        """
        Create a new project with directory structure.
        Uses person_name as the base folder name for better organization.
        Always adds timestamp to prevent conflicts and ensure one project per execution.

        Args:
            topic: Video topic
            person_name: Featured person name

        Returns:
            Created Project instance
        """
        # Generate project ID based on person name and topic
        # Format: {person_name}_{topic}_{timestamp}
        # Always include timestamp to ensure unique folder per execution
        safe_person = self._sanitize_filename(person_name)
        safe_topic = self._sanitize_filename(topic)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        project_id = f"{safe_person}_{safe_topic}_{timestamp}"
        project_dir = settings.projects_dir / project_id

        # Create project directory structure
        project_dir.mkdir(parents=True, exist_ok=True)

        images_dir = project_dir / "images"
        images_dir.mkdir(exist_ok=True)

        audio_dir = project_dir / "audio"
        audio_dir.mkdir(exist_ok=True)

        video_dir = project_dir / "video"
        video_dir.mkdir(exist_ok=True)

        # Create project instance
        project = Project(
            project_id=project_id,
            topic=topic,
            person_name=person_name,
            project_dir=project_dir,
            images_dir=images_dir,
            audio_dir=audio_dir,
        )

        # Save project metadata
        self.save_project(project)

        return project

    def save_project(self, project: Project) -> None:
        """
        Save project metadata to JSON file.

        Args:
            project: Project instance to save
        """
        project.updated_at = datetime.now()
        metadata_path = project.project_dir / "metadata.json"

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(project.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

    def load_project(self, project_id: str) -> Optional[Project]:
        """
        Load project from metadata file.

        Args:
            project_id: Project identifier

        Returns:
            Project instance or None if not found
        """
        metadata_path = settings.projects_dir / project_id / "metadata.json"

        if not metadata_path.exists():
            return None

        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return Project(**data)

    def list_projects(self) -> list[Project]:
        """
        List all projects.

        Returns:
            List of Project instances
        """
        projects = []

        for project_dir in settings.projects_dir.iterdir():
            if project_dir.is_dir():
                project = self.load_project(project_dir.name)
                if project:
                    projects.append(project)

        # Sort by creation date, newest first
        projects.sort(key=lambda p: p.created_at, reverse=True)

        return projects

    def delete_project(self, project_id: str) -> bool:
        """
        Delete a project and all its files.

        Args:
            project_id: Project identifier

        Returns:
            True if deleted successfully, False otherwise
        """
        project_dir = settings.projects_dir / project_id

        if not project_dir.exists():
            return False

        shutil.rmtree(project_dir)
        return True

    def save_script(self, project: Project, script_content: str) -> Path:
        """
        Save script to project directory.

        Args:
            project: Project instance
            script_content: Script text content

        Returns:
            Path to saved script file
        """
        script_path = project.project_dir / "script.txt"

        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        project.script_path = script_path
        project.status = ProjectStatus.SCRIPT_GENERATED
        self.save_project(project)

        return script_path

    def get_image_path(self, project: Project, image_name: str) -> Path:
        """
        Get path for an image file.

        Args:
            project: Project instance
            image_name: Image filename

        Returns:
            Path to image file
        """
        return project.images_dir / image_name

    def get_audio_path(self, project: Project, audio_name: str) -> Path:
        """
        Get path for an audio file.

        Args:
            project: Project instance
            audio_name: Audio filename

        Returns:
            Path to audio file
        """
        return project.audio_dir / audio_name

    def get_video_path(self, project: Project) -> Path:
        """
        Get path for the final video file.

        Args:
            project: Project instance

        Returns:
            Path to video file
        """
        video_dir = project.project_dir / "video"
        return video_dir / f"{project.project_id}.mp4"

    def get_thumbnail_path(self, project: Project) -> Path:
        """
        Get path for the thumbnail image.

        Args:
            project: Project instance

        Returns:
            Path to thumbnail file
        """
        return project.project_dir / "thumbnail.jpg"

    @staticmethod
    def _sanitize_filename(filename: str, max_length: int = 50) -> str:
        """
        Sanitize filename for safe file system usage.

        Args:
            filename: Original filename
            max_length: Maximum length of sanitized filename

        Returns:
            Sanitized filename
        """
        # Remove invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, "_")

        # Replace spaces with underscores
        filename = filename.replace(" ", "_")

        # Truncate if too long
        if len(filename) > max_length:
            filename = filename[:max_length]

        return filename
