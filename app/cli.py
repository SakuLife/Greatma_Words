"""
Command-line interface for GreatMan Words video generator.
"""

import asyncio
import sys
from pathlib import Path

from app.config import settings
from app.main import orchestrator
from app.models.schemas import GenerationConfig
from app.services.interactive_script_editor import InteractiveScriptEditor
from app.utils.file_manager import FileManager
from app.utils.logger import logger, setup_logger


class CLI:
    """Command-line interface for the video generator."""

    def __init__(self):
        """Initialize CLI."""
        self.file_manager = FileManager()

    def print_banner(self):
        """Print application banner."""
        banner = """
TPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPW
Q                                                               Q
Q         GreatMan Words - AI Video Generator                  Q
Q         Automated YouTube Content Creation System            Q
Q                                                               Q
ZPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP]
"""
        print(banner)

    async def run(self):
        """Run the CLI interface."""
        self.print_banner()

        # Check VOICEVOX connection
        print("\n= Checking VOICEVOX connection...")
        if await orchestrator.check_voicevox_connection():
            print("[OK] VOICEVOX is ready")
        else:
            print(
                "[WARN] VOICEVOX is not running. Please start VOICEVOX before proceeding."
            )
            print(
                f"   Expected at: {settings.voicevox_api_url}\n"
            )

        while True:
            print("\n" + "=" * 60)
            print("MAIN MENU")
            print("=" * 60)
            print("1. Create script interactively (チャット形式で台本作成)")
            print("2. Generate video automatically (完全自動生成)")
            print("3. List projects")
            print("4. View project details")
            print("5. Check settings")
            print("6. Exit")
            print("=" * 60)

            choice = input("\nSelect option (1-6): ").strip()

            if choice == "1":
                await self.create_script_interactively()
            elif choice == "2":
                await self.generate_video()
            elif choice == "3":
                self.list_projects()
            elif choice == "4":
                self.view_project()
            elif choice == "5":
                self.show_settings()
            elif choice == "6":
                print("\n[INFO] Goodbye!")
                break
            else:
                print("[WARN] Invalid option. Please try again.")

    async def create_script_interactively(self):
        """Create script interactively through chat interface."""
        print("\n" + "=" * 60)
        print("INTERACTIVE SCRIPT CREATION")
        print("=" * 60)
        print("AIとチャットしながら台本を作成します。")
        print("台本が完成したら、自動で動画生成に進みます。\n")

        # Get basic info
        person_name = input("[INPUT] Person/Philosopher name (e.g., Peter Thiel): ").strip()
        if not person_name:
            print("[ERROR] Person name is required.")
            return

        topic = input("[INPUT] Topic/Theme (e.g., 競争を避ける戦略): ").strip()
        if not topic:
            print("[ERROR] Topic is required.")
            return

        duration_input = input(
            f"[INPUT] Duration in minutes (default: {settings.default_script_length}): "
        ).strip()
        try:
            duration = int(duration_input) if duration_input else settings.default_script_length
        except ValueError:
            print(f"[WARN] Invalid duration. Using default: {settings.default_script_length}")
            duration = settings.default_script_length

        # Create project
        project = self.file_manager.create_project(topic, person_name)
        print(f"\n[INFO] Project created: {project.project_id}")

        # Initialize interactive editor
        editor = InteractiveScriptEditor()
        script = await editor.start_interactive_session(
            topic=topic,
            person_name=person_name,
            duration_minutes=duration,
        )

        # Save initial script
        script_text = script.total_narration
        self.file_manager.save_script(project, script_text)
        project.script = script
        self.file_manager.save_project(project)

        print("\n" + "=" * 60)
        print("INITIAL SCRIPT DRAFT")
        print("=" * 60)
        self._print_script_summary(script)
        print("=" * 60)

        # Interactive editing loop
        print("\n台本を編集できます。以下のコマンドが使えます：")
        print("  - 通常のメッセージ: AIに指示を送る")
        print("  - '完成' または 'OK': 台本を確定して動画生成に進む")
        print("  - '保存': 現在の台本を保存（動画生成はしない）")
        print("  - '終了': セッションを終了\n")

        while True:
            user_input = input("\nあなた: ").strip()

            if not user_input:
                continue

            # Check for commands
            if user_input.lower() in ["完成", "ok", "ok!", "完了", "これでいい"]:
                print("\n[INFO] 台本を確定しました。動画生成に進みます...")
                break
            elif user_input.lower() in ["保存", "save"]:
                script_text = script.total_narration
                self.file_manager.save_script(project, script_text)
                project.script = script
                self.file_manager.save_project(project)
                print("[INFO] 台本を保存しました。")
                continue
            elif user_input.lower() in ["終了", "exit", "quit"]:
                print("[INFO] セッションを終了します。")
                return

            # Continue conversation
            print("\nAI: ", end="", flush=True)
            try:
                response, updated_script = await editor.continue_conversation(user_input)

                # Print response word by word for better UX
                import time
                words = response.split()
                for i, word in enumerate(words):
                    print(word, end=" ", flush=True)
                    if (i + 1) % 10 == 0:  # New line every 10 words
                        print()
                print()  # Final newline

                # Update script if new version provided
                if updated_script:
                    script = updated_script
                    script_text = script.total_narration
                    self.file_manager.save_script(project, script_text)
                    project.script = script
                    self.file_manager.save_project(project)
                    print("\n[INFO] 台本が更新されました。")

            except Exception as e:
                print(f"\n[ERROR] エラーが発生しました: {e}")
                logger.exception("Error in interactive editing")

        # Proceed to video generation
        print("\n" + "=" * 60)
        print("VIDEO GENERATION")
        print("=" * 60)

        upload_choice = input("[INPUT] Upload to YouTube? (y/n, default: n): ").strip().lower()
        upload_to_youtube = upload_choice == "y"

        privacy = "private"
        if upload_to_youtube:
            privacy_input = input(
                "[INPUT] Privacy status (public/private/unlisted, default: private): "
            ).strip().lower()
            if privacy_input in ["public", "private", "unlisted"]:
                privacy = privacy_input

        config = GenerationConfig(
            topic=topic,
            person_name=person_name,
            target_duration_minutes=duration,
            upload_to_youtube=upload_to_youtube,
            youtube_privacy=privacy,
        )

        print("\n[INFO] Starting video generation from script...\n")

        try:
            project, video_path = await orchestrator.generate_video_from_script(
                project, script, config
            )

            print("\n" + "=" * 60)
            print("[SUCCESS] VIDEO GENERATION SUCCESSFUL!")
            print("=" * 60)
            print(f"Project ID: {project.project_id}")
            print(f"Video Path: {video_path}")
            if project.thumbnail_path:
                print(f"Thumbnail: {project.thumbnail_path}")
            if project.youtube_video_id:
                print(
                    f"YouTube URL: https://www.youtube.com/watch?v={project.youtube_video_id}"
                )
            print("=" * 60)

        except Exception as e:
            print("\n" + "=" * 60)
            print("[ERROR] VIDEO GENERATION FAILED")
            print("=" * 60)
            print(f"Error: {e}")
            print("=" * 60)
            logger.exception("Video generation error")

    def _print_script_summary(self, script):
        """Print a summary of the script."""
        print(f"Topic: {script.topic}")
        print(f"Person: {script.person_name}")
        print(f"Duration: {script.total_duration_minutes} minutes")
        print(f"\nSections ({len(script.sections)}):")
        for i, section in enumerate(script.sections, 1):
            print(f"  {i}. {section.title} ({section.duration_seconds}秒)")

    async def generate_video(self):
        """Generate a new video interactively."""
        print("\n" + "=" * 60)
        print("NEW VIDEO GENERATION")
        print("=" * 60)

        # Get user inputs
        person_name = input("\n[INPUT] Person/Philosopher name (e.g., Peter Thiel): ").strip()
        if not person_name:
            print("[ERROR] Person name is required.")
            return

        topic = input("[INPUT] Topic/Theme (e.g., 競争を避ける戦略): ").strip()
        if not topic:
            print("[ERROR] Topic is required.")
            return

        duration_input = input(
            f"[INPUT] Duration in minutes (default: {settings.default_script_length}): "
        ).strip()
        try:
            duration = int(duration_input) if duration_input else settings.default_script_length
        except ValueError:
            print(f"[WARN] Invalid duration. Using default: {settings.default_script_length}")
            duration = settings.default_script_length

        upload_choice = input("[INPUT] Upload to YouTube? (y/n, default: n): ").strip().lower()
        upload_to_youtube = upload_choice == "y"

        privacy = "private"
        if upload_to_youtube:
            privacy_input = input(
                "[INPUT] Privacy status (public/private/unlisted, default: private): "
            ).strip().lower()
            if privacy_input in ["public", "private", "unlisted"]:
                privacy = privacy_input

        config = GenerationConfig(
            topic=topic,
            person_name=person_name,
            target_duration_minutes=duration,
            upload_to_youtube=upload_to_youtube,
            youtube_privacy=privacy,
        )

        print("\n" + "=" * 60)
        print("CONFIGURATION SUMMARY")
        print("=" * 60)
        print(f"Person: {person_name}")
        print(f"Topic: {topic}")
        print(f"Duration: {duration} minutes")
        print(f"Upload to YouTube: {'Yes' if upload_to_youtube else 'No'}")
        if upload_to_youtube:
            print(f"Privacy: {privacy}")
        print("=" * 60)

        confirm = input("\n[CONFIRM] Proceed with generation? (y/n): ").strip().lower()
        if confirm != "y":
            print("[WARN] Cancelled.")
            return

        print("\n[INFO] Starting video generation...\n")

        try:
            project, video_path = await orchestrator.generate_complete_video(config)

            print("\n" + "=" * 60)
            print("[OK] VIDEO GENERATION SUCCESSFUL!")
            print("=" * 60)
            print(f"Project ID: {project.project_id}")
            print(f"Video Path: {video_path}")
            if project.youtube_video_id:
                print(
                    f"YouTube URL: https://www.youtube.com/watch?v={project.youtube_video_id}"
                )
            print("=" * 60)

        except Exception as e:
            print("\n" + "=" * 60)
            print("[ERROR] VIDEO GENERATION FAILED")
            print("=" * 60)
            print(f"Error: {e}")
            print("=" * 60)
            logger.exception("Video generation error")

    def list_projects(self):
        """List all projects."""
        projects = self.file_manager.list_projects()

        print("\n" + "=" * 60)
        print("ALL PROJECTS")
        print("=" * 60)

        if not projects:
            print("No projects found.")
            return

        for i, project in enumerate(projects, 1):
            print(f"\n{i}. {project.person_name} - {project.topic}")
            print(f"   ID: {project.project_id}")
            print(f"   Status: {project.status}")
            print(f"   Created: {project.created_at.strftime('%Y-%m-%d %H:%M')}")

        print("=" * 60)

    def view_project(self):
        """View project details."""
        project_id = input("\n[INPUT] Enter project ID: ").strip()

        project = self.file_manager.load_project(project_id)

        if not project:
            print(f"[ERROR] Project not found: {project_id}")
            return

        print("\n" + "=" * 60)
        print("PROJECT DETAILS")
        print("=" * 60)
        print(f"ID: {project.project_id}")
        print(f"Person: {project.person_name}")
        print(f"Topic: {project.topic}")
        print(f"Status: {project.status}")
        print(f"Created: {project.created_at}")
        print(f"Updated: {project.updated_at}")
        print(f"\nProject Directory: {project.project_dir}")

        if project.script_path:
            print(f"Script: {project.script_path}")
        if project.video_path:
            print(f"Video: {project.video_path}")
        if project.youtube_video_id:
            print(
                f"YouTube: https://www.youtube.com/watch?v={project.youtube_video_id}"
            )

        print("=" * 60)

    def show_settings(self):
        """Show current settings."""
        print("\n" + "=" * 60)
        print("CURRENT SETTINGS")
        print("=" * 60)
        print(f"App Name: {settings.app_name}")
        print(f"Environment: {settings.app_env}")
        print(f"\nVOICEVOX API: {settings.voicevox_api_url}")
        print(f"Speaker ID: {settings.voicevox_speaker_id}")
        print(f"\nVideo Resolution: {settings.video_resolution}")
        print(f"FPS: {settings.video_fps}")
        print(f"\nDefault LLM Model: {settings.default_llm_model}")
        print(f"Default Duration: {settings.default_script_length} minutes")
        print(f"\nOpenAI API: {'Configured' if settings.openai_api_key else 'Not configured'}")
        print(f"Anthropic API: {'Configured' if settings.anthropic_api_key else 'Not configured'}")
        print(f"\nData Directory: {settings.data_dir}")
        print(f"Projects Directory: {settings.projects_dir}")
        print("=" * 60)


async def main():
    """Main entry point."""
    # Set up logging
    setup_logger(log_file=Path("./greatman_words.log"))

    # Run CLI
    cli = CLI()
    try:
        await cli.run()
    except KeyboardInterrupt:
        print("\n\n[INFO] Interrupted. Goodbye!")
        sys.exit(0)
    except Exception as e:
        logger.exception("Fatal error in CLI")
        print(f"\n[ERROR] Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
