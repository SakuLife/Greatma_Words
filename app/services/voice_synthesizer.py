"""
Voice synthesis service using VOICEVOX API.
"""

import asyncio
from pathlib import Path
import tempfile

import aiohttp
from pydub import AudioSegment

from app.config import settings
from app.utils.logger import logger


class VoiceSynthesizer:
    """Synthesizes speech using VOICEVOX API."""

    def __init__(self):
        """Initialize voice synthesizer."""
        self.api_url = settings.voicevox_api_url
        self.speaker_id = settings.voicevox_speaker_id

    async def synthesize_script(
        self,
        script_text: str,
        output_path: Path,
        speaker_id: int | None = None,
        subtitles: list[dict] | None = None,
    ) -> tuple[Path, list[dict] | None]:
        """
        Synthesize speech from script text.
        If subtitles are provided, synthesize each subtitle line separately for better sync.

        Args:
            script_text: Text to synthesize (fallback if subtitles not provided)
            output_path: Where to save the audio file
            speaker_id: VOICEVOX speaker ID (defaults to config setting)
            subtitles: List of subtitle dicts with 'text' field (optional)

        Returns:
            Path to generated audio file

        Raises:
            RuntimeError: If synthesis fails
        """
        speaker_id = speaker_id or self.speaker_id

        # If subtitles provided, synthesize each subtitle line separately
        if subtitles:
            logger.info(
                f"Synthesizing speech from {len(subtitles)} subtitle lines, speaker={speaker_id}"
            )

            audio_chunks = []
            total = len(subtitles)
            for i, subtitle in enumerate(subtitles):
                text = subtitle.get("text", "").strip()
                if not text:
                    continue

                # 進捗表示（10フレーズごと、または最後）
                if (i + 1) % 10 == 0 or (i + 1) == total:
                    logger.info(f"音声合成進捗: {i + 1}/{total} フレーズ完了 ({((i+1)/total*100):.1f}%)")
                else:
                    logger.debug(f"Processing subtitle {i + 1}/{total}: {text[:30]}...")

                audio_data = await self._synthesize_chunk(text, speaker_id)
                audio_chunks.append(audio_data)

                # 少し待機（API負荷軽減）
                await asyncio.sleep(0.1)

            # Combine audio chunks using pydub for proper WAV merging
            # Also track actual timing for subtitle synchronization
            logger.info("[INFO] 音声チャンクを結合中...")
            combined_audio_segment = AudioSegment.empty()
            updated_subtitles = []
            current_time = 0.0
            subtitle_index = 0

            for i, audio_data in enumerate(audio_chunks):
                # Save each chunk to temporary file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_file.write(audio_data)
                    temp_path = Path(temp_file.name)

                try:
                    # Load as AudioSegment and append
                    segment = AudioSegment.from_wav(str(temp_path))
                    segment_duration_ms = len(segment)
                    segment_duration_sec = segment_duration_ms / 1000.0

                    combined_audio_segment += segment
                    logger.debug(f"チャンク {i + 1}/{len(audio_chunks)} を結合しました ({segment_duration_sec:.2f}秒)")

                    # Update subtitle timing based on actual audio duration
                    if subtitle_index < len(subtitles):
                        subtitle = subtitles[subtitle_index].copy()
                        subtitle["start_time"] = current_time
                        subtitle["duration"] = segment_duration_sec
                        updated_subtitles.append(subtitle)
                        current_time += segment_duration_sec
                        subtitle_index += 1

                finally:
                    # Clean up temp file
                    if temp_path.exists():
                        temp_path.unlink()

            # Export combined audio
            output_path.parent.mkdir(parents=True, exist_ok=True)
            combined_audio_segment.export(str(output_path), format="wav")

            duration_seconds = len(combined_audio_segment) / 1000.0
            logger.info(f"[OK] 音声結合完了: {duration_seconds:.1f}秒 ({duration_seconds/60:.1f}分)")
            logger.info(f"[INFO] 字幕タイミングを実際の音声長に合わせて調整しました")

            return output_path, updated_subtitles

        else:
            # Fallback to original method
            logger.info(
                f"Synthesizing speech: {len(script_text)} chars, speaker={speaker_id}"
            )

            # Split text into chunks if too long
            chunks = self._split_text(script_text, max_length=500)
            logger.debug(f"Split into {len(chunks)} chunks")

            # Synthesize each chunk
            audio_chunks = []
            for i, chunk in enumerate(chunks):
                logger.debug(f"Processing chunk {i + 1}/{len(chunks)}")
                audio_data = await self._synthesize_chunk(chunk, speaker_id)
                audio_chunks.append(audio_data)

            # Combine audio chunks using pydub
            logger.info("[INFO] 音声チャンクを結合中...")
            combined_audio_segment = AudioSegment.empty()

            for i, audio_data in enumerate(audio_chunks):
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_file.write(audio_data)
                    temp_path = Path(temp_file.name)

                try:
                    segment = AudioSegment.from_wav(str(temp_path))
                    combined_audio_segment += segment
                finally:
                    if temp_path.exists():
                        temp_path.unlink()

            # Export combined audio
            output_path.parent.mkdir(parents=True, exist_ok=True)
            combined_audio_segment.export(str(output_path), format="wav")

            duration_seconds = len(combined_audio_segment) / 1000.0
            logger.info(f"[OK] 音声結合完了: {duration_seconds:.1f}秒 ({duration_seconds/60:.1f}分)")

            return output_path, None

        return output_path, None

    async def _synthesize_chunk(self, text: str, speaker_id: int) -> bytes:
        """
        Synthesize a single text chunk.

        Args:
            text: Text to synthesize
            speaker_id: VOICEVOX speaker ID

        Returns:
            Audio data as bytes

        Raises:
            RuntimeError: If synthesis fails
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Generate audio query
                query_url = f"{self.api_url}/audio_query"
                params = {"text": text, "speaker": speaker_id}

                async with session.post(query_url, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(
                            f"Audio query failed: {response.status} - {error_text}"
                        )
                    query_data = await response.json()

                # Step 2: Synthesize audio
                synthesis_url = f"{self.api_url}/synthesis"
                params = {"speaker": speaker_id}

                async with session.post(
                    synthesis_url, params=params, json=query_data
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(
                            f"Synthesis failed: {response.status} - {error_text}"
                        )
                    audio_data = await response.read()

                return audio_data

        except aiohttp.ClientError as e:
            logger.error(f"VOICEVOX API connection error: {e}")
            raise RuntimeError(
                f"Failed to connect to VOICEVOX API at {self.api_url}: {e}"
            ) from e
        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            raise RuntimeError(f"Failed to synthesize audio: {e}") from e

    async def check_connection(self) -> bool:
        """
        Check if VOICEVOX API is accessible.

        Returns:
            True if API is accessible, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                version_url = f"{self.api_url}/version"
                async with session.get(version_url, timeout=5) as response:
                    if response.status == 200:
                        version = await response.text()
                        logger.info(f"VOICEVOX API version: {version}")
                        return True
                    else:
                        logger.warning(
                            f"VOICEVOX API returned status {response.status}"
                        )
                        return False
        except Exception as e:
            logger.error(f"Failed to connect to VOICEVOX API: {e}")
            return False

    @staticmethod
    def _split_text(text: str, max_length: int = 500) -> list[str]:
        """
        Split text into chunks for synthesis.

        Args:
            text: Text to split
            max_length: Maximum characters per chunk

        Returns:
            List of text chunks
        """
        # Split by sentences first
        sentences = text.replace("\n\n", "\n").split("\n")

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # If adding this sentence would exceed max_length, save current chunk
            if current_chunk and len(current_chunk) + len(sentence) + 1 > max_length:
                chunks.append(current_chunk)
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += "\n" + sentence
                else:
                    current_chunk = sentence

        # Add remaining chunk
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    async def get_available_speakers(self) -> list[dict]:
        """
        Get list of available speakers from VOICEVOX.

        Returns:
            List of speaker information dicts

        Raises:
            RuntimeError: If request fails
        """
        try:
            async with aiohttp.ClientSession() as session:
                speakers_url = f"{self.api_url}/speakers"
                async with session.get(speakers_url) as response:
                    if response.status != 200:
                        raise RuntimeError(f"Failed to get speakers: {response.status}")
                    speakers = await response.json()
                    return speakers
        except Exception as e:
            logger.error(f"Failed to get speakers: {e}")
            raise RuntimeError(f"Failed to get available speakers: {e}") from e
