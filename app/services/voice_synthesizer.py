"""
Voice synthesis service using VOICEVOX API.
"""

import asyncio
import re
from pathlib import Path
import tempfile

import aiohttp
from pydub import AudioSegment

from app.config import settings
from app.utils.logger import logger

# 英語→カタカナ変換辞書（VOICEVOXが正しく読み上げるため）
ENGLISH_TO_KATAKANA = {
    # よくある英語表記
    "Todo": "トゥードゥー",
    "TODO": "トゥードゥー",
    "todo": "トゥードゥー",
    "Google": "グーグル",
    "GOOGLE": "グーグル",
    "AI": "エーアイ",
    "Facebook": "フェイスブック",
    "Amazon": "アマゾン",
    "Tesla": "テスラ",
    "Apple": "アップル",
    "Microsoft": "マイクロソフト",
    "Windows": "ウィンドウズ",
    "iPhone": "アイフォン",
    "iPad": "アイパッド",
    "Mac": "マック",
    "PayPal": "ペイパル",
    "Netflix": "ネットフリックス",
    "YouTube": "ユーチューブ",
    "Twitter": "ツイッター",
    "Instagram": "インスタグラム",
    "LinkedIn": "リンクトイン",
    "Uber": "ウーバー",
    "Airbnb": "エアビーアンドビー",
    "SpaceX": "スペースエックス",
    "OpenAI": "オープンエーアイ",
    "ChatGPT": "チャットジーピーティー",
    "GPT": "ジーピーティー",
    # ビジネス用語
    "CEO": "シーイーオー",
    "CTO": "シーティーオー",
    "CFO": "シーエフオー",
    "COO": "シーオーオー",
    "MBA": "エムビーエー",
    "ROI": "アールオーアイ",
    "KPI": "ケーピーアイ",
    "PDCA": "ピーディーシーエー",
    "OKR": "オーケーアール",
    "M&A": "エムアンドエー",
    "IPO": "アイピーオー",
    "VC": "ブイシー",
    "IT": "アイティー",
    "DX": "ディーエックス",
    "SaaS": "サース",
    "PaaS": "パース",
    "IaaS": "イアース",
    "B2B": "ビートゥービー",
    "B2C": "ビートゥーシー",
    "API": "エーピーアイ",
    # 書籍・概念
    "Zero to One": "ゼロ・トゥ・ワン",
    "Lean Startup": "リーン・スタートアップ",
    "Startup": "スタートアップ",
    "startup": "スタートアップ",
    "Innovation": "イノベーション",
    "innovation": "イノベーション",
    "Disruption": "ディスラプション",
    "disruption": "ディスラプション",
    # 人名（よく出る人物）
    "Elon Musk": "イーロン・マスク",
    "Jeff Bezos": "ジェフ・ベゾス",
    "Peter Thiel": "ピーター・ティール",
    "Steve Jobs": "スティーブ・ジョブズ",
    "Bill Gates": "ビル・ゲイツ",
    "Mark Zuckerberg": "マーク・ザッカーバーグ",
    "Warren Buffett": "ウォーレン・バフェット",
    "Charlie Munger": "チャーリー・マンガー",
    "Larry Page": "ラリー・ペイジ",
    "Sergey Brin": "セルゲイ・ブリン",
    "Tim Cook": "ティム・クック",
    "Satya Nadella": "サティア・ナデラ",
    "Jack Ma": "ジャック・マー",
    "Sam Altman": "サム・アルトマン",
}

# 漢字読み修正辞書（VOICEVOXが誤読しやすい語）
# ビジネス・哲学・教養系コンテンツで頻出する語を中心に収録
# 新しい誤読を発見したらここに追加する
KANJI_READINGS: dict[str, str] = {
    # === 連濁（れんだく）の誤読 ===
    "逆張り": "ぎゃくばり",
    "順張り": "じゅんばり",
    "後付け": "あとづけ",
    "裏付け": "うらづけ",
    "位置付け": "いちづけ",
    "意味付け": "いみづけ",
    "関連付け": "かんれんづけ",
    "動機付け": "どうきづけ",
    "値付け": "ねづけ",
    "格付け": "かくづけ",
    "箔付け": "はくづけ",
    # === 複数の読みがある語（正しい読みに統一） ===
    "相殺": "そうさい",
    "代替": "だいたい",
    "重複": "ちょうふく",
    "早急": "さっきゅう",
    "他人事": "ひとごと",
    "一段落": "いちだんらく",
    "依存": "いぞん",
    "既存": "きそん",
    "遵守": "じゅんしゅ",
    "出生": "しゅっしょう",
    "施策": "しさく",
    "続柄": "つづきがら",
    "脆弱": "ぜいじゃく",
    "汎用": "はんよう",
    "貼付": "ちょうふ",
    "凡例": "はんれい",
    "完遂": "かんすい",
    "帰趨": "きすう",
    # === 哲学・教養系で頻出 ===
    "所以": "ゆえん",
    "畢竟": "ひっきょう",
    "蓋し": "けだし",
    "即ち": "すなわち",
    "所謂": "いわゆる",
    "概ね": "おおむね",
    "凡そ": "およそ",
    "殆ど": "ほとんど",
    "敢えて": "あえて",
    "強ち": "あながち",
    "一入": "ひとしお",
    "漸く": "ようやく",
    "然るべき": "しかるべき",
    "真摯": "しんし",
    "矜持": "きょうじ",
    "瑣末": "さまつ",
    "些末": "さまつ",
    "齟齬": "そご",
    "邂逅": "かいこう",
    "逡巡": "しゅんじゅん",
    # === 人名の誤読防止 ===
    "藤田田": "ふじたでん",
    "御手洗": "みたらい",
    "五十嵐": "いがらし",
    "長谷川": "はせがわ",
    "服部": "はっとり",
    "東海林": "しょうじ",
    # === 投資・ビジネス用語 ===
    "指値": "さしね",
    "老舗": "しにせ",
    "月極": "つきぎめ",
    "相場": "そうば",
    "手仕舞い": "てじまい",
    "値嵩": "ねがさ",
    "含み損": "ふくみぞん",
    "含み益": "ふくみえき",
    "損切り": "そんぎり",
    "利確": "りかく",
    "仕手": "して",
    "建値": "たてね",
    "御利益": "ごりやく",
}


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

            # Increase volume by 1.2x (about 1.58 dB)
            combined_audio_segment = combined_audio_segment.apply_gain(1.58)

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

            # Increase volume by 1.2x (about 1.58 dB)
            combined_audio_segment = combined_audio_segment.apply_gain(1.58)

            # Export combined audio
            output_path.parent.mkdir(parents=True, exist_ok=True)
            combined_audio_segment.export(str(output_path), format="wav")

            duration_seconds = len(combined_audio_segment) / 1000.0
            logger.info(f"[OK] 音声結合完了: {duration_seconds:.1f}秒 ({duration_seconds/60:.1f}分)")

            return output_path, None

        return output_path, None

    def _fix_kanji_readings(self, text: str) -> str:
        """
        VOICEVOXが誤読しやすい漢字をひらがなに置換する。
        字幕テキストには影響せず、音声合成時のみ適用される。

        Args:
            text: 変換前のテキスト

        Returns:
            読み修正後のテキスト
        """
        result = text

        # 長い文字列から順に置換（部分一致の誤置換を防ぐ）
        for kanji, reading in sorted(
            KANJI_READINGS.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if kanji in result:
                result = result.replace(kanji, reading)
                logger.debug(f"読み修正: {kanji} → {reading}")

        return result

    def _convert_english_to_katakana(self, text: str) -> str:
        """
        英語表記をカタカナに変換する。
        VOICEVOXがアルファベットを一文字ずつ読み上げる問題を回避する。

        Args:
            text: 変換前のテキスト

        Returns:
            カタカナ変換後のテキスト
        """
        result = text

        # 辞書に基づいて変換（長い文字列から順に置換）
        for english, katakana in sorted(
            ENGLISH_TO_KATAKANA.items(), key=lambda x: len(x[0]), reverse=True
        ):
            result = result.replace(english, katakana)

        # 残った英単語をログで警告（デバッグ用）
        remaining_english = re.findall(r'[A-Za-z]{2,}', result)
        if remaining_english:
            unique_words = list(set(remaining_english))[:5]  # 最大5つまで
            logger.debug(f"未変換の英語: {', '.join(unique_words)}")

        return result

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
        # 漢字読み修正 → 英語→カタカナ変換
        text = self._fix_kanji_readings(text)
        text = self._convert_english_to_katakana(text)

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

                # ポーズ長の調整（「・」等の間が長すぎる問題対策）
                query_data = self._adjust_pause_length(query_data)

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

    @staticmethod
    def _adjust_pause_length(
        query_data: dict,
        max_pause: float = 0.25,
    ) -> dict:
        """
        VOICEVOXのポーズ長を調整する。
        「・」や句読点で生じる長すぎるポーズを短縮する。

        Args:
            query_data: audio_query APIのレスポンス
            max_pause: 最大ポーズ長（秒）。デフォルト0.25秒。

        Returns:
            調整済みのquery_data
        """
        for phrase in query_data.get("accent_phrases", []):
            pause = phrase.get("pause_mora")
            if pause and pause.get("vowel_length", 0) > max_pause:
                original = pause["vowel_length"]
                pause["vowel_length"] = max_pause
                logger.debug(
                    f"ポーズ長調整: {original:.3f}秒 → {max_pause:.3f}秒"
                )
        return query_data

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
