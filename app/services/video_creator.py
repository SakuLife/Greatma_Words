"""
Video creation service using MoviePy.
"""

import re
import tempfile
import textwrap
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)

from app.config import settings
from app.utils.logger import logger


class VideoCreator:
    """Creates videos from images and audio."""

    def __init__(self):
        """Initialize video creator."""
        self.fps = settings.video_fps
        self.resolution = (settings.video_width, settings.video_height)

    def _smart_line_break(self, text: str, max_chars: int = 30) -> list[str]:
        """
        助詞や句読点で賢く改行する。

        Args:
            text: 改行するテキスト
            max_chars: 1行の最大文字数（目安）

        Returns:
            改行されたテキストのリスト
        """
        # テキストが短い場合はそのまま返す
        if len(text) <= max_chars:
            return [text]

        # 助詞や句読点のリスト（改行に適した位置、優先順位順）
        high_priority_breaks = ['。', '、', '！', '？']
        medium_priority_breaks = ['は', 'が', 'を', 'に', 'で', 'と', 'や', 'も']
        low_priority_breaks = ['の', 'へ', 'から', 'まで', 'より', 'など', 'こそ', 'だけ', 'ほど']

        # 2行に分割する場合の理想的な分割位置を探す
        ideal_pos = len(text) // 2
        min_pos = max(10, ideal_pos - 10)  # 理想位置の±10文字の範囲で探す
        max_pos = min(len(text) - 5, ideal_pos + 10)

        # 優先順位順に改行位置を探す
        def find_best_break(break_chars):
            best_pos = -1
            best_distance = float('inf')
            for i in range(min_pos, max_pos):
                if text[i] in break_chars:
                    distance = abs(i - ideal_pos)
                    if distance < best_distance:
                        best_distance = distance
                        best_pos = i + 1  # 助詞・句読点の後で改行
            return best_pos

        # 優先順位の高い順に探す
        best_pos = find_best_break(high_priority_breaks)
        if best_pos == -1:
            best_pos = find_best_break(medium_priority_breaks)
        if best_pos == -1:
            best_pos = find_best_break(low_priority_breaks)

        # 適切な位置が見つからなければ、max_charsで改行
        if best_pos == -1:
            return textwrap.wrap(text, width=max_chars)

        # 2行に分割
        line1 = text[:best_pos].strip()
        line2 = text[best_pos:].strip()

        # 2行目も長い場合は再帰的に処理
        if len(line2) > max_chars:
            line2_parts = self._smart_line_break(line2, max_chars)
            return [line1] + line2_parts

        return [line1, line2] if line2 else [line1]

    async def create_video(
        self,
        image_path: Path,
        audio_path: Path,
        output_path: Path,
        subtitles: list[dict] | None = None,
    ) -> Path:
        """
        Create a video from a single image and audio file with subtitles.

        Args:
            image_path: Path to the image file
            audio_path: Path to the audio file
            output_path: Where to save the video
            subtitles: List of subtitle dicts with 'text', 'start_time', 'duration'

        Returns:
            Path to created video file

        Raises:
            RuntimeError: If video creation fails
        """
        logger.info(f"[INFO] 動画生成を開始します")
        logger.info(f"  画像: {image_path}")
        logger.info(f"  音声: {audio_path}")

        # Check if image exists
        if not image_path.exists():
            raise RuntimeError(f"Image file not found: {image_path}")

        try:
            # Load audio to get duration
            logger.info("[INFO] 音声ファイルを読み込み中...")
            audio_clip = AudioFileClip(str(audio_path))
            duration = audio_clip.duration

            logger.info(f"[INFO] 音声の長さ: {duration:.2f}秒 ({duration/60:.1f}分)")

            # Resize image before creating clip to avoid Pillow compatibility issues
            # Open and resize image using PIL
            logger.info("[INFO] 画像を読み込み・リサイズ中...")
            with Image.open(image_path) as img:
                logger.debug(f"Original image size: {img.size}")
                img_resized = img.resize(self.resolution, Image.Resampling.LANCZOS)
                # Save to temporary file
                temp_image_path = image_path.parent / f"temp_{image_path.name}"
                img_resized.save(temp_image_path, quality=95)

            # Create image clip with same duration as audio
            logger.info("[INFO] 画像クリップを作成中...")
            image_clip = ImageClip(str(temp_image_path), duration=duration)
            image_clip = image_clip.set_fps(self.fps)
            logger.info(f"[INFO] 画像クリップ作成完了: {self.resolution[0]}x{self.resolution[1]}, {self.fps}fps")

            # Add subtitles if provided
            clips = [image_clip]

            if subtitles:
                logger.info(f"[INFO] 字幕を追加中... ({len(subtitles)}フレーズ)")
                subtitle_clips = self._create_subtitle_clips(subtitles, duration)
                clips.extend(subtitle_clips)
                logger.info(f"[OK] 字幕クリップ作成完了: {len(subtitle_clips)}個")

            # Composite all clips
            logger.info("[INFO] 動画を合成中...")
            if len(clips) > 1:
                # CompositeVideoClipにサイズを明示的に指定
                video_clip = CompositeVideoClip(clips, size=self.resolution)
                logger.info(f"[INFO] 合成クリップ数: {len(clips)} (背景1 + 字幕{len(clips)-1})")
            else:
                video_clip = image_clip

            # Set audio
            logger.info("[INFO] 音声を設定中...")
            video_clip = video_clip.set_audio(audio_clip)

            # Write video file
            output_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"[INFO] 動画ファイルを書き出し中... (これには時間がかかります)")
            logger.info(f"  出力先: {output_path}")
            logger.info(f"  動画の長さ: {duration:.1f}秒 ({duration/60:.1f}分)")
            logger.info(f"  進捗状況を表示します...")

            # カスタムロガーで進捗を表示
            class ProgressLogger:
                """ffmpegの出力をパースして進捗を表示するロガー"""
                def __init__(self, total_duration: float):
                    self.total_duration = total_duration
                    self.last_progress = 0
                    # ffmpegの出力パターン: time=HH:MM:SS.mm または time=00:00:12.34
                    self.time_pattern = re.compile(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})')
                    self.start_time = None

                def message(self, msg: str):
                    """ffmpegの出力メッセージを処理"""
                    # time=HH:MM:SS.mm の形式を探す
                    match = self.time_pattern.search(msg)
                    if match:
                        hours, minutes, seconds, centiseconds = map(int, match.groups())
                        current_time = hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0

                        if self.total_duration > 0:
                            progress = min(100, (current_time / self.total_duration) * 100)
                            # 5%ごとに表示（最後の10%は1%ごと）
                            should_log = False
                            if progress >= 90:
                                # 最後の10%は1%ごと
                                should_log = progress >= self.last_progress + 1
                            else:
                                # それ以外は5%ごと
                                should_log = progress >= self.last_progress + 5

                            if should_log:
                                elapsed_min = current_time / 60.0
                                total_min = self.total_duration / 60.0
                                remaining_min = max(0, (total_min - elapsed_min))
                                logger.info(
                                    f"[進捗] {progress:.1f}% "
                                    f"({elapsed_min:.1f}分 / {total_min:.1f}分) "
                                    f"残り約{remaining_min:.1f}分"
                                )
                                self.last_progress = int(progress)

                def error(self, msg: str):
                    """エラーメッセージを処理（無視）"""
                    pass

            # 開始時刻を記録
            import time
            start_time = time.time()

            # 進捗表示は一旦無効化（MoviePyのlogger要件が複雑なため）
            # 動画生成には時間がかかりますが、完了までお待ちください
            logger.info("[INFO] 動画書き出しには数分かかります。完了までお待ちください...")

            video_clip.write_videofile(
                str(output_path),
                fps=self.fps,
                codec="libx264",
                audio_codec="aac",
                bitrate=settings.video_bitrate,
                preset="medium",
                threads=4,
                logger=None,  # 進捗表示は一旦無効化
                verbose=False,  # デフォルトの冗長な出力は抑制
            )

            # 完了時刻を記録
            elapsed_time = time.time() - start_time
            logger.info(f"[INFO] 動画書き出し完了 (所要時間: {elapsed_time/60:.1f}分)")

            # Clean up
            logger.info("[INFO] リソースを解放中...")
            video_clip.close()
            audio_clip.close()
            image_clip.close()
            if subtitles:
                for clip in subtitle_clips:
                    clip.close()

            # Remove temporary image file
            if temp_image_path.exists():
                temp_image_path.unlink()

            # ファイルサイズを確認
            file_size_mb = output_path.stat().st_size / 1024 / 1024
            logger.info("=" * 60)
            logger.info(f"[OK] 動画生成が完了しました！")
            logger.info(f"  ファイル: {output_path}")
            logger.info(f"  サイズ: {file_size_mb:.1f} MB")
            logger.info(f"  長さ: {duration:.1f}秒 ({duration/60:.1f}分)")
            logger.info("=" * 60)
            return output_path

        except Exception as e:
            logger.error(f"Failed to create video: {e}")
            raise RuntimeError(f"Video creation failed: {e}") from e

    def _create_subtitle_clips(
        self, subtitles: list[dict], video_duration: float
    ) -> list[ImageClip]:
        """
        Create subtitle text clips from subtitle data using PIL (ImageMagick不要).

        Args:
            subtitles: List of subtitle dicts with 'text', 'start_time', 'duration'
            video_duration: Total video duration in seconds

        Returns:
            List of ImageClip objects
        """
        subtitle_clips = []

        # 日本語フォントを探す
        import platform
        import os
        font_path = None

        if platform.system() == "Windows":
            font_paths = [
                "C:/Windows/Fonts/meiryo.ttc",  # メイリオ
                "C:/Windows/Fonts/msgothic.ttc",  # MSゴシック
                "C:/Windows/Fonts/msmincho.ttc",  # MS明朝
            ]
            for fp in font_paths:
                if os.path.exists(fp):
                    font_path = fp
                    break
        elif platform.system() == "Darwin":  # macOS
            font_paths = [
                "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
                "/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc",
            ]
            for fp in font_paths:
                if os.path.exists(fp):
                    font_path = fp
                    break
        else:  # Linux (GitHub Actions ubuntu-latest)
            font_paths = [
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            ]
            for fp in font_paths:
                if os.path.exists(fp):
                    font_path = fp
                    break

        if font_path:
            logger.debug(f"字幕用日本語フォントを使用: {font_path}")

        # 一時ディレクトリを作成
        temp_dir = Path(tempfile.gettempdir()) / "greatman_words_subtitles"
        temp_dir.mkdir(parents=True, exist_ok=True)

        for i, subtitle in enumerate(subtitles):
            text = subtitle.get("text", "")
            start_time = subtitle.get("start_time", 0.0)
            duration = subtitle.get("duration", 3.0)

            # 開始時間と終了時間を計算
            end_time = min(start_time + duration, video_duration)

            if start_time >= video_duration or text.strip() == "":
                continue

            try:
                # PILで字幕画像を作成
                subtitle_img_pil = self._create_subtitle_image_pil(text, font_path)

                # 一時ファイルに保存（PNG形式で透過を保持）
                temp_subtitle_path = temp_dir / f"subtitle_{i:04d}.png"
                subtitle_img_pil.save(temp_subtitle_path, "PNG")

                # ImageClipとして作成（ファイルパスから読み込む）
                subtitle_clip = ImageClip(str(temp_subtitle_path), duration=end_time - start_time)
                subtitle_clip = subtitle_clip.set_position(("center", "bottom")).set_start(start_time)
                subtitle_clip = subtitle_clip.set_fps(self.fps)

                subtitle_clips.append(subtitle_clip)
                logger.debug(
                    f"Subtitle: '{text[:30]}...' at {start_time:.2f}s for {duration:.2f}s"
                )

            except Exception as e:
                logger.warning(f"Failed to create subtitle for '{text[:30]}...': {e}")
                import traceback
                logger.debug(traceback.format_exc())
                continue

        logger.info(f"[INFO] 字幕クリップ作成: {len(subtitle_clips)}個 (一時ファイル: {temp_dir})")
        return subtitle_clips

    def _create_subtitle_image_pil(self, text: str, font_path: str | None = None) -> Image.Image:
        """
        PILを使って字幕画像を作成（ImageMagick不要）.

        Args:
            text: 表示するテキスト
            font_path: フォントパス（Noneの場合はデフォルト）

        Returns:
            PIL Image (RGBA)
        """
        # 字幕エリアのサイズ（動画の解像度に合わせる）
        subtitle_width = self.resolution[0] - 200  # 左右に100pxずつ余白
        subtitle_height = 200  # 字幕の高さを少し大きく

        # 透明背景の画像を作成
        img = Image.new("RGBA", (subtitle_width, subtitle_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # フォントを読み込む
        import platform
        import os
        font_size = 90  # フォントサイズを大きく（視認性向上）
        font = None

        if platform.system() == "Windows":
            # 日本語フォント候補（太字を優先）
            font_candidates = [
                "C:/Windows/Fonts/meiryob.ttc",  # メイリオ Bold（太字優先）
                "C:/Windows/Fonts/YuGothB.ttc",  # 游ゴシック Bold
                "C:/Windows/Fonts/msgothic.ttc",  # MSゴシック
                "C:/Windows/Fonts/meiryo.ttc",  # メイリオ
                "C:/Windows/Fonts/YuGothM.ttc",  # 游ゴシック Medium
            ]
            for fp in font_candidates:
                if os.path.exists(fp):
                    try:
                        font = ImageFont.truetype(fp, font_size)
                        logger.debug(f"字幕用フォント: {fp} (サイズ: {font_size})")
                        break
                    except (OSError, IOError) as e:
                        logger.debug(f"フォント読み込み失敗: {fp} - {e}")
                        continue
        elif platform.system() == "Darwin":  # macOS
            font_candidates = [
                "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",  # Bold
                "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
                "/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc",
            ]
            for fp in font_candidates:
                if os.path.exists(fp):
                    try:
                        font = ImageFont.truetype(fp, font_size)
                        logger.debug(f"字幕用フォント: {fp} (サイズ: {font_size})")
                        break
                    except (OSError, IOError) as e:
                        logger.debug(f"フォント読み込み失敗: {fp} - {e}")
                        continue
        else:  # Linux (GitHub Actions ubuntu-latest)
            font_candidates = [
                ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 0),  # Japanese (index 0)
                ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 0),
                ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
                ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0),
            ]
            for fp, index in font_candidates:
                if os.path.exists(fp):
                    try:
                        font = ImageFont.truetype(fp, font_size, index=index)
                        logger.info(f"字幕用フォント: {fp} (index={index}, サイズ: {font_size})")
                        break
                    except (OSError, IOError) as e:
                        logger.debug(f"フォント読み込み失敗: {fp} - {e}")
                        continue

        if font is None:
            logger.error("⚠️ 字幕用日本語フォントが見つかりません！デフォルトフォントを使用します。")
            logger.error(f"⚠️ Platform: {platform.system()}, 文字化けが発生する可能性があります。")
            font = ImageFont.load_default()
        else:
            logger.info(f"✅ 字幕フォント読み込み成功 (サイズ: {font_size})")

        # テキストを折り返し（助詞・句読点で賢く改行）
        max_chars_per_line = 30
        lines = self._smart_line_break(text, max_chars=max_chars_per_line)

        # テキストの色設定
        text_color = (255, 255, 255, 255)  # 白色（RGBA）
        outline_color = (0, 0, 0, 255)  # 黒色（アウトライン、RGBA）
        outline_width = 4  # アウトラインを太く（太字効果）

        # 行間を計算
        line_height = font_size + 15
        total_text_height = len(lines) * line_height
        start_y = (subtitle_height - total_text_height) // 2

        # 各行を描画
        for i, line in enumerate(lines):
            y = start_y + i * line_height
            x = subtitle_width // 2

            # アウトラインを描画（縁取り）
            for adj_x in range(-outline_width, outline_width + 1):
                for adj_y in range(-outline_width, outline_width + 1):
                    if adj_x != 0 or adj_y != 0:
                        draw.text(
                            (x + adj_x, y + adj_y),
                            line,
                            font=font,
                            fill=outline_color,
                            anchor="mm",  # middle-middle
                        )

            # メインテキストを描画
            draw.text(
                (x, y),
                line,
                font=font,
                fill=text_color,
                anchor="mm",  # middle-middle
            )

        return img

    async def create_multi_scene_video(
        self,
        scenes: list[tuple[Path, float]],
        audio_path: Path,
        output_path: Path,
    ) -> Path:
        """
        Create a video with multiple scenes (images with durations).

        Args:
            scenes: List of (image_path, duration_seconds) tuples
            audio_path: Path to the audio file
            output_path: Where to save the video

        Returns:
            Path to created video file

        Raises:
            RuntimeError: If video creation fails
        """
        logger.info(f"Creating multi-scene video with {len(scenes)} scenes")

        try:
            # Create clips for each scene
            video_clips = []

            for i, (image_path, duration) in enumerate(scenes):
                logger.debug(f"Processing scene {i + 1}: {image_path} ({duration}s)")

                # Resize image before creating clip
                with Image.open(image_path) as img:
                    img_resized = img.resize(self.resolution, Image.Resampling.LANCZOS)
                    temp_image_path = image_path.parent / f"temp_scene_{i}_{image_path.name}"
                    img_resized.save(temp_image_path, quality=95)

                image_clip = ImageClip(str(temp_image_path), duration=duration)
                image_clip = image_clip.set_fps(self.fps)

                video_clips.append(image_clip)

            # Concatenate all scenes
            final_video = concatenate_videoclips(video_clips, method="compose")

            # Load and set audio
            audio_clip = AudioFileClip(str(audio_path))
            final_video = final_video.set_audio(audio_clip)

            # Adjust video duration to match audio if needed
            if final_video.duration < audio_clip.duration:
                logger.warning(
                    f"Video duration ({final_video.duration}s) shorter than audio "
                    f"({audio_clip.duration}s). Extending last scene."
                )
                # Extend the last scene
                final_video = final_video.set_duration(audio_clip.duration)
            elif final_video.duration > audio_clip.duration:
                logger.warning(
                    f"Video duration ({final_video.duration}s) longer than audio "
                    f"({audio_clip.duration}s). Trimming video."
                )
                final_video = final_video.subclip(0, audio_clip.duration)

            # Write video file
            output_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Writing video to {output_path}")

            final_video.write_videofile(
                str(output_path),
                fps=self.fps,
                codec="libx264",
                audio_codec="aac",
                bitrate=settings.video_bitrate,
                preset="medium",
                threads=4,
                logger=None,
            )

            # Clean up
            final_video.close()
            audio_clip.close()
            for clip in video_clips:
                clip.close()

            logger.info(f"Multi-scene video created successfully: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to create multi-scene video: {e}")
            raise RuntimeError(f"Multi-scene video creation failed: {e}") from e

    async def add_background_music(
        self,
        video_path: Path,
        music_path: Path,
        output_path: Path,
        music_volume: float = 0.1,
    ) -> Path:
        """
        Add background music to a video.

        Args:
            video_path: Path to the video file
            music_path: Path to the background music file
            output_path: Where to save the new video
            music_volume: Volume of background music (0.0 to 1.0)

        Returns:
            Path to video with background music

        Raises:
            RuntimeError: If operation fails
        """
        logger.info(f"Adding background music to {video_path}")

        try:
            from moviepy.editor import VideoFileClip, CompositeAudioClip

            # Load video
            video = VideoFileClip(str(video_path))

            # Load background music
            music = AudioFileClip(str(music_path))

            # Adjust music volume and loop if necessary
            music = music.volumex(music_volume)

            if music.duration < video.duration:
                # Loop the music
                loops_needed = int(video.duration / music.duration) + 1
                music = music.loop(n=loops_needed)

            music = music.set_duration(video.duration)

            # Combine original audio with background music
            if video.audio:
                final_audio = CompositeAudioClip([video.audio, music])
            else:
                final_audio = music

            video = video.set_audio(final_audio)

            # Write output
            output_path.parent.mkdir(parents=True, exist_ok=True)

            video.write_videofile(
                str(output_path),
                fps=self.fps,
                codec="libx264",
                audio_codec="aac",
                bitrate=settings.video_bitrate,
                preset="medium",
                threads=4,
                logger=None,
            )

            # Clean up
            video.close()
            music.close()

            logger.info(f"Video with background music saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to add background music: {e}")
            raise RuntimeError(f"Background music addition failed: {e}") from e
