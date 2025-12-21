"""
Main orchestrator for GreatMan Words video generation.
Coordinates all services to generate complete videos.
"""

from pathlib import Path

from app.config import settings
from app.models.schemas import (
    GenerationConfig,
    Project,
    ProjectStatus,
    VideoMetadata,
    VideoScript,
)
from app.services.script_generator import ScriptGenerator
from app.services.image_generator import ImageGenerator
from app.services.thumbnail_generator import ThumbnailGenerator
from app.services.voice_synthesizer import VoiceSynthesizer
from app.services.video_creator import VideoCreator
from app.services.youtube_uploader import YouTubeUploader
from app.utils.file_manager import FileManager
from app.utils.logger import logger
from app.utils.voicevox_launcher import launcher as voicevox_launcher


class VideoGenerationOrchestrator:
    """Orchestrates the entire video generation pipeline."""

    def __init__(self):
        """Initialize all services."""
        self.file_manager = FileManager()
        self.script_generator = ScriptGenerator()
        self.image_generator = ImageGenerator()
        self.thumbnail_generator = ThumbnailGenerator()
        self.voice_synthesizer = VoiceSynthesizer()
        self.video_creator = VideoCreator()
        self.youtube_uploader = YouTubeUploader()

    async def generate_complete_video(
        self, config: GenerationConfig
    ) -> tuple[Project, Path]:
        """
        Generate a complete video from start to finish.

        Args:
            config: Generation configuration

        Returns:
            Tuple of (Project, video_path)

        Raises:
            RuntimeError: If any step fails
        """
        logger.info(
            f"Starting video generation: topic='{config.topic}', person='{config.person_name}'"
        )

        # Step 1: Create project
        project = self.file_manager.create_project(config.topic, config.person_name)
        logger.info(f"Created project: {project.project_id}")

        try:
            # Step 2: Generate script
            logger.info("Step 1/5: Generating script...")
            script = await self.script_generator.generate_script(
                topic=config.topic,
                person_name=config.person_name,
                duration_minutes=config.target_duration_minutes,
                model=config.llm_model,
                temperature=config.temperature,
            )

            # Save script
            script_text = script.total_narration
            self.file_manager.save_script(project, script_text)
            project.script = script
            self.file_manager.save_project(project)

            logger.info(f"Script generated: {len(script_text)} characters")

            # Step 3: Generate images (optional)
            image_path = self.file_manager.get_image_path(
                project, f"{config.person_name}.png"
            )

            if settings.skip_image_generation:
                logger.info("Step 2/5: Skipping image generation (using existing images)")
                if not image_path.exists():
                    logger.warning(f"Image not found at {image_path}. Please add image manually.")
            elif image_path.exists():
                # 既存の画像がある場合はスキップ
                logger.info(f"Step 2/5: Image already exists, skipping generation: {image_path}")
                logger.info(f"[INFO] 既存の画像を使用します: {image_path}")
            else:
                logger.info("Step 2/5: Generating images...")
                logger.info(f"[INFO] 画像生成を開始します: {config.person_name}")

                # Create main person slide
                person_description = f"Professional portrait of {config.person_name}"

                await self.image_generator.generate_person_slide(
                    person_name=config.person_name,
                    person_description=person_description,
                    output_path=image_path,
                )

                logger.info(f"[OK] 画像生成が完了しました: {image_path}")

            project.status = ProjectStatus.IMAGES_GENERATED
            self.file_manager.save_project(project)

            # Step 4: Synthesize voice
            logger.info("Step 3/5: Synthesizing voice...")

            audio_path = self.file_manager.get_audio_path(project, "narration.wav")

            # 字幕データを準備（字幕ごとに1フレーズずつ音声を生成）
            subtitles_for_audio = []
            if script:
                for section in script.sections:
                    if section.subtitles:
                        for subtitle in section.subtitles:
                            subtitles_for_audio.append({
                                "text": subtitle.text,
                                "start_time": subtitle.start_time,
                                "duration": subtitle.duration,
                            })

            total_subtitles = len(subtitles_for_audio) if subtitles_for_audio else 0
            if total_subtitles > 0:
                logger.info(f"[INFO] 字幕数: {total_subtitles}フレーズ")
                logger.info(f"[INFO] 音声合成には時間がかかります。しばらくお待ちください...")

            audio_path_result, updated_subtitles = await self.voice_synthesizer.synthesize_script(
                script_text=script_text,
                output_path=audio_path,
                speaker_id=config.voicevox_speaker_id,
                subtitles=subtitles_for_audio if subtitles_for_audio else None,
            )

            project.status = ProjectStatus.AUDIO_GENERATED
            self.file_manager.save_project(project)

            logger.info(f"Audio synthesized: {audio_path}")

            # Step 5: Create video
            logger.info("Step 4/5: Creating video...")

            video_path = self.file_manager.get_video_path(project)

            # 字幕データを準備（実際の音声長に基づくタイミングを使用）
            if updated_subtitles:
                # 音声合成で更新された字幕タイミングを使用
                subtitles = updated_subtitles
                logger.info(f"[INFO] 実際の音声長に基づく字幕タイミングを使用します")
            else:
                # フォールバック: 元のスクリプトのタイミングを使用
                subtitles = []
                if script:
                    current_time = 0.0
                    for section in script.sections:
                        if section.subtitles:
                            for subtitle in section.subtitles:
                                subtitles.append({
                                    "text": subtitle.text,
                                    "start_time": current_time + subtitle.start_time,
                                    "duration": subtitle.duration,
                                })
                        current_time += section.duration_seconds
                logger.info(f"[INFO] 元のスクリプトのタイミングを使用します")

            total_subtitles = len(subtitles) if subtitles else 0
            if total_subtitles > 0:
                logger.info(f"[INFO] 字幕数: {total_subtitles}フレーズ")

            await self.video_creator.create_video(
                image_path=image_path,
                audio_path=audio_path,
                output_path=video_path,
                subtitles=subtitles if subtitles else None,
            )

            project.video_path = video_path
            project.status = ProjectStatus.VIDEO_GENERATED
            self.file_manager.save_project(project)

            logger.info(f"Video created: {video_path}")

            # Step 6: Generate thumbnail (optional, can be skipped if generating manually)
            if settings.use_thumbnail_generation and not settings.skip_thumbnail_generation:
                logger.info("Step 5/6: Generating thumbnail...")

                thumbnail_path = self.file_manager.get_thumbnail_path(project)

                await self.thumbnail_generator.generate_thumbnail(
                    person_name=config.person_name,
                    topic=config.topic,
                    output_path=thumbnail_path,
                    style="professional",
                )

                project.thumbnail_path = thumbnail_path
                self.file_manager.save_project(project)

                logger.info(f"Thumbnail generated: {thumbnail_path}")
            else:
                logger.info("Step 5/6: Skipping thumbnail generation (not enabled)")

            # Step 7: Upload to YouTube (optional)
            if config.upload_to_youtube:
                logger.info("Step 6/6: Uploading to YouTube...")

                # Prepare metadata
                video_metadata = VideoMetadata(
                    title=f"{config.person_name}の哲学 - {config.topic}",
                    description=self._generate_video_description(script, config),
                    tags=[
                        config.person_name,
                        "哲学",
                        "教養",
                        "YouTube",
                        "AI時代",
                    ],
                    privacy_status=config.youtube_privacy,
                )

                video_id = await self.youtube_uploader.upload_video(
                    video_path=video_path, metadata=video_metadata
                )

                project.youtube_video_id = video_id
                project.video_metadata = video_metadata
                project.status = ProjectStatus.UPLOADED
                self.file_manager.save_project(project)

                logger.info(
                    f"Video uploaded to YouTube: https://www.youtube.com/watch?v={video_id}"
                )
            else:
                logger.info("Step 6/6: Skipping YouTube upload (not enabled)")

            logger.info(f"Video generation completed successfully: {video_path}")

            return project, video_path

        except Exception as e:
            # Mark project as failed
            project.status = ProjectStatus.FAILED
            self.file_manager.save_project(project)

            logger.error(f"Video generation failed: {e}")
            raise RuntimeError(f"Video generation failed: {e}") from e

    async def generate_video_from_script(
        self, project: Project, script: VideoScript, config: GenerationConfig
    ) -> tuple[Project, Path]:
        """
        Generate video from an existing script (skip script generation).

        Args:
            project: Project instance with script already created
            script: VideoScript instance
            config: Generation configuration

        Returns:
            Tuple of (Project, video_path)
        """
        logger.info(
            f"Starting video generation from script: project_id='{project.project_id}'"
        )

        try:
            # Save script if not already saved
            if not project.script:
                script_text = script.total_narration
                self.file_manager.save_script(project, script_text)
                project.script = script
                self.file_manager.save_project(project)

            script_text = script.total_narration
            logger.info(f"Using existing script: {len(script_text)} characters")

            # Step 1: Generate images (optional)
            image_path = self.file_manager.get_image_path(
                project, f"{config.person_name}.png"
            )

            if settings.skip_image_generation:
                logger.info("Step 1/5: Skipping image generation (using existing images)")
                if not image_path.exists():
                    logger.warning(f"Image not found at {image_path}. Please add image manually.")
            elif image_path.exists():
                # 既存の画像がある場合はスキップ
                logger.info(f"Step 1/5: Image already exists, skipping generation: {image_path}")
                logger.info(f"[INFO] 既存の画像を使用します: {image_path}")
            else:
                logger.info("Step 1/5: Generating images...")
                logger.info(f"[INFO] 画像生成を開始します: {config.person_name}")

                person_description = f"Professional portrait of {config.person_name}"

                await self.image_generator.generate_person_slide(
                    person_name=config.person_name,
                    person_description=person_description,
                    output_path=image_path,
                )

                logger.info(f"[OK] 画像生成が完了しました: {image_path}")

            project.status = ProjectStatus.IMAGES_GENERATED
            self.file_manager.save_project(project)

            # Step 2: Synthesize voice
            logger.info("=" * 60)
            logger.info("Step 2/5: 音声合成を開始します...")
            logger.info("=" * 60)

            # VoiceVoxが起動しているか確認し、起動していなければ自動起動
            if not await self.voice_synthesizer.check_connection():
                logger.info("[INFO] VoiceVoxが起動していません。自動起動を試みます...")
                if voicevox_launcher.start():
                    # 少し待ってから再度確認
                    import asyncio
                    await asyncio.sleep(3)
                    if not await self.voice_synthesizer.check_connection():
                        raise RuntimeError(
                            "VoiceVox failed to start. Please start VoiceVox manually."
                        )
                    logger.info("[OK] VoiceVoxが起動しました")
                else:
                    raise RuntimeError(
                        "VoiceVox is not running and could not be started automatically. "
                        "Please start VoiceVox manually."
                    )
            else:
                logger.info("[OK] VoiceVoxに接続できました")

            audio_path = self.file_manager.get_audio_path(project, "narration.wav")

            # 字幕データを準備（字幕ごとに1フレーズずつ音声を生成）
            subtitles_for_audio = []
            if script:
                for section in script.sections:
                    if section.subtitles:
                        for subtitle in section.subtitles:
                            subtitles_for_audio.append({
                                "text": subtitle.text,
                                "start_time": subtitle.start_time,
                                "duration": subtitle.duration,
                            })

            total_subtitles = len(subtitles_for_audio) if subtitles_for_audio else 0
            if total_subtitles > 0:
                logger.info(f"[INFO] 字幕数: {total_subtitles}フレーズ")
                logger.info(f"[INFO] 音声合成には時間がかかります。しばらくお待ちください...")

            audio_path_result, updated_subtitles = await self.voice_synthesizer.synthesize_script(
                script_text=script_text,
                output_path=audio_path,
                speaker_id=config.voicevox_speaker_id,
                subtitles=subtitles_for_audio if subtitles_for_audio else None,
            )

            project.status = ProjectStatus.AUDIO_GENERATED
            self.file_manager.save_project(project)

            logger.info(f"[OK] 音声合成が完了しました: {audio_path}")

            # Step 3: Create video
            logger.info("=" * 60)
            logger.info("Step 3/5: 動画生成を開始します...")
            logger.info("=" * 60)

            video_path = self.file_manager.get_video_path(project)

            # 字幕データを準備（実際の音声長に基づくタイミングを使用）
            if updated_subtitles:
                # 音声合成で更新された字幕タイミングを使用
                subtitles = updated_subtitles
                logger.info(f"[INFO] 実際の音声長に基づく字幕タイミングを使用します")
            else:
                # フォールバック: 元のスクリプトのタイミングを使用
                subtitles = []
                if script:
                    current_time = 0.0
                    for section in script.sections:
                        if section.subtitles:
                            for subtitle in section.subtitles:
                                subtitles.append({
                                    "text": subtitle.text,
                                    "start_time": current_time + subtitle.start_time,
                                    "duration": subtitle.duration,
                                })
                        current_time += section.duration_seconds
                logger.info(f"[INFO] 元のスクリプトのタイミングを使用します")

            total_subtitles = len(subtitles) if subtitles else 0
            if total_subtitles > 0:
                logger.info(f"[INFO] 字幕数: {total_subtitles}フレーズ")
            logger.info(f"[INFO] 画像: {image_path}")
            logger.info(f"[INFO] 音声: {audio_path}")
            logger.info(f"[INFO] 動画生成には時間がかかります。しばらくお待ちください...")

            await self.video_creator.create_video(
                image_path=image_path,
                audio_path=audio_path,
                output_path=video_path,
                subtitles=subtitles if subtitles else None,
            )

            project.video_path = video_path
            project.status = ProjectStatus.VIDEO_GENERATED
            self.file_manager.save_project(project)

            logger.info(f"[OK] 動画生成が完了しました: {video_path}")

            # Step 4: Generate thumbnail (optional)
            if settings.use_thumbnail_generation:
                logger.info("Step 4/5: Generating thumbnail...")

                thumbnail_path = self.file_manager.get_thumbnail_path(project)

                await self.thumbnail_generator.generate_thumbnail(
                    person_name=config.person_name,
                    topic=config.topic,
                    output_path=thumbnail_path,
                    style="professional",
                )

                project.thumbnail_path = thumbnail_path
                self.file_manager.save_project(project)

                logger.info(f"Thumbnail generated: {thumbnail_path}")
            else:
                logger.info("Step 4/5: Skipping thumbnail generation (not enabled)")

            # Step 5: Upload to YouTube (optional)
            if config.upload_to_youtube:
                logger.info("Step 5/5: Uploading to YouTube...")

                video_metadata = VideoMetadata(
                    title=f"{config.person_name}の教え - {config.topic}",
                    description=self._generate_video_description(script, config),
                    tags=[
                        config.person_name,
                        "教養",
                        "ビジネス",
                        "YouTube",
                        "AI生成",
                    ],
                    privacy_status=config.youtube_privacy,
                )

                video_id = await self.youtube_uploader.upload_video(
                    video_path=video_path, metadata=video_metadata
                )

                project.youtube_video_id = video_id
                project.video_metadata = video_metadata
                project.status = ProjectStatus.UPLOADED
                self.file_manager.save_project(project)

                logger.info(
                    f"Video uploaded to YouTube: https://www.youtube.com/watch?v={video_id}"
                )
            else:
                logger.info("Step 5/5: Skipping YouTube upload (not enabled)")

            logger.info(f"Video generation completed successfully: {video_path}")

            return project, video_path

        except Exception as e:
            project.status = ProjectStatus.FAILED
            self.file_manager.save_project(project)

            logger.error(f"Video generation failed: {e}")
            raise RuntimeError(f"Video generation failed: {e}") from e

    async def check_voicevox_connection(self) -> bool:
        """
        Check if VOICEVOX API is available.
        If not running, try to start it automatically.

        Returns:
            True if available, False otherwise
        """
        if await self.voice_synthesizer.check_connection():
            return True

        # VoiceVoxが起動していない場合、自動起動を試みる
        logger.info("VoiceVox is not running. Attempting to start automatically...")
        if voicevox_launcher.start():
            # 少し待ってから再度確認
            import asyncio
            await asyncio.sleep(2)
            return await self.voice_synthesizer.check_connection()

        return False

    @staticmethod
    def _generate_video_description(script, config: GenerationConfig) -> str:
        """Generate YouTube video description from script."""
        description = f"""
{config.person_name}の哲学を深く掘り下げる動画です。

【テーマ】
{config.topic}

【目次】
"""

        # Add chapter markers
        current_time = 0
        for section in script.sections:
            minutes = int(current_time // 60)
            seconds = int(current_time % 60)
            description += f"{minutes:02d}:{seconds:02d} - {section.title}\n"
            current_time += section.duration_seconds

        description += """
【チャンネルについて】
このチャンネルでは、偉人の言葉や哲学を分かりやすく解説しています。
AI時代を生き抜くための知恵を、あなたにお届けします。

チャンネル登録・高評価お願いします！

#教養 #YouTube #哲学 #AI時代
"""

        return description.strip()


# Global orchestrator instance
orchestrator = VideoGenerationOrchestrator()
