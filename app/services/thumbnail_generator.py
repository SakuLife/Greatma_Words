"""
Thumbnail generation service using AI APIs.
Supports Nanobanana Pro, DALL-E, and Stable Diffusion.
"""

import io
from pathlib import Path

import requests
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

from app.config import settings
from app.utils.logger import logger
from app.utils.person_titles import get_person_title


class ThumbnailGenerator:
    """Generates YouTube thumbnails featuring person portraits."""

    def __init__(self):
        """Initialize thumbnail generator."""
        self.openai_client = None
        self.nanobanana_api_key = settings.nanobanana_api_key
        self.nanobanana_api_url = settings.nanobanana_api_url

        if settings.openai_api_key:
            self.openai_client = OpenAI(api_key=settings.openai_api_key)

    async def generate_thumbnail(
        self,
        person_name: str,
        topic: str,
        output_path: Path,
        style: str = "professional",
    ) -> Path:
        """
        Generate a YouTube thumbnail featuring the person.

        Args:
            person_name: Name of the person
            topic: Video topic/theme
            output_path: Where to save the thumbnail
            style: Thumbnail style (professional, dramatic, modern, etc.)

        Returns:
            Path to generated thumbnail file

        Raises:
            RuntimeError: If thumbnail generation fails
        """
        logger.info(f"Generating thumbnail for '{person_name}' - '{topic}'")

        provider = settings.thumbnail_provider

        if provider == "nanobanana":
            thumbnail_path = await self._generate_with_nanobanana(
                person_name, topic, output_path, style
            )
        elif provider == "dalle":
            thumbnail_path = await self._generate_with_dalle(
                person_name, topic, output_path, style
            )
        elif provider == "stable-diffusion":
            thumbnail_path = await self._generate_with_stable_diffusion(
                person_name, topic, output_path, style
            )
        else:
            raise ValueError(f"Unsupported thumbnail provider: {provider}")

        logger.info(f"Thumbnail saved to {thumbnail_path}")
        return thumbnail_path

    async def _generate_with_nanobanana(
        self, person_name: str, topic: str, output_path: Path, style: str
    ) -> Path:
        """Generate thumbnail using Nanobanana Pro API."""
        if not self.nanobanana_api_key:
            logger.warning(
                "Nanobanana API key not configured, falling back to DALL-E"
            )
            return await self._generate_with_dalle(person_name, topic, output_path, style)

        try:
            # Nanobanana Pro用のプロンプト作成
            prompt = self._create_thumbnail_prompt(person_name, topic, style)

            # Nanobanana Pro API呼び出し
            # 注意: 実際のAPI仕様に合わせて調整が必要
            headers = {
                "Authorization": f"Bearer {self.nanobanana_api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "prompt": prompt,
                "width": 1280,
                "height": 720,  # YouTubeサムネイルサイズ
                "style": style,
                "quality": "high",
            }

            response = requests.post(
                f"{self.nanobanana_api_url}/generate",
                json=payload,
                headers=headers,
                timeout=60,
            )
            response.raise_for_status()

            result = response.json()

            # 画像URLを取得（API仕様に応じて調整）
            image_url = result.get("image_url") or result.get("url")

            if not image_url:
                raise ValueError("No image URL in API response")

            # 画像をダウンロード
            img_response = requests.get(image_url, timeout=30)
            img_response.raise_for_status()

            # 保存
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(img_response.content)

            # テキストオーバーレイを追加（必要に応じて）
            self._add_text_overlay(output_path, person_name, topic)

            return output_path

        except Exception as e:
            logger.error(f"Nanobanana generation failed: {e}")
            logger.info("Falling back to DALL-E")
            return await self._generate_with_dalle(person_name, topic, output_path, style)

    async def _generate_with_dalle(
        self, person_name: str, topic: str, output_path: Path, style: str
    ) -> Path:
        """Generate thumbnail using DALL-E 3."""
        if not self.openai_client:
            raise ValueError("OpenAI API key not configured")

        try:
            prompt = self._create_thumbnail_prompt(person_name, topic, style)

            logger.debug(f"DALL-E thumbnail prompt: {prompt}")

            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",  # DALL-E 3の最大サイズ
                quality="hd",
                n=1,
            )

            image_url = response.data[0].url
            logger.debug(f"DALL-E thumbnail URL: {image_url}")

            # ダウンロード
            img_response = requests.get(image_url, timeout=30)
            img_response.raise_for_status()

            # 画像を開いてリサイズ（YouTubeサムネイルサイズ: 1280x720）
            img = Image.open(io.BytesIO(img_response.content))
            img = img.resize((1280, 720), Image.Resampling.LANCZOS)

            # 保存
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, quality=95)

            # テキストオーバーレイを追加
            self._add_text_overlay(output_path, person_name, topic)

            return output_path

        except Exception as e:
            logger.error(f"DALL-E thumbnail generation failed: {e}")
            raise RuntimeError(f"Failed to generate thumbnail: {e}") from e

    async def _generate_with_stable_diffusion(
        self, person_name: str, topic: str, output_path: Path, style: str
    ) -> Path:
        """Generate thumbnail using Stable Diffusion API."""
        # Stable Diffusion API実装（Replicate等を使用）
        # 実装は後で追加可能
        logger.warning("Stable Diffusion not yet implemented, using DALL-E")
        return await self._generate_with_dalle(person_name, topic, output_path, style)

    def _create_thumbnail_prompt(
        self, person_name: str, topic: str, style: str
    ) -> str:
        """Create a prompt for thumbnail generation (参考画像スタイル: 人物は右側)."""
        style_descriptions = {
            "professional": "professional, business-like, clean, modern",
            "dramatic": "dramatic lighting, cinematic, impactful",
            "modern": "modern, sleek, contemporary design",
            "classic": "classic, timeless, elegant",
        }

        style_desc = style_descriptions.get(style, style_descriptions["professional"])

        # 参考画像スタイル: 人物は右側、左側はテキスト用のスペース
        prompt = (
            f"Professional YouTube thumbnail featuring {person_name}. "
            f"Topic: {topic}. "
            f"Style: {style_desc}, high quality, eye-catching, "
            f"portrait of {person_name} prominently displayed on the right side of the frame, "
            f"dramatic lighting with strong contrast (bright on one side, shadow on the other), "
            f"dark background on the left side (space for text overlay), "
            f"clean professional photography style, "
            f"1280x720 aspect ratio, "
            f"suitable for educational business content."
        )

        return prompt

    def _add_text_overlay(
        self, image_path: Path, person_name: str, topic: str
    ) -> None:
        """Add text overlay to thumbnail (参考画像スタイル: 左側に肩書と名前)."""
        try:
            img = Image.open(image_path)
            draw = ImageDraw.Draw(img)

            # フォントの設定（日本語対応）
            import platform
            title_font = None
            subtitle_font = None
            topic_font = None

            if platform.system() == "Windows":
                # Windows: 日本語フォントを試す
                font_paths = [
                    "C:/Windows/Fonts/meiryo.ttc",  # メイリオ
                    "C:/Windows/Fonts/msgothic.ttc",  # MSゴシック
                    "C:/Windows/Fonts/msmincho.ttc",  # MS明朝
                    "C:/Windows/Fonts/yu Gothic.ttc",  # 游ゴシック
                ]
                for font_path in font_paths:
                    try:
                        title_font = ImageFont.truetype(font_path, 48)
                        subtitle_font = ImageFont.truetype(font_path, 32)
                        topic_font = ImageFont.truetype(font_path, 36)
                        logger.debug(f"日本語フォントを使用: {font_path}")
                        break
                    except (OSError, IOError):
                        continue
            elif platform.system() == "Darwin":  # macOS
                font_paths = [
                    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
                    "/System/Library/Fonts/AppleGothic.ttf",
                ]
                for font_path in font_paths:
                    try:
                        title_font = ImageFont.truetype(font_path, 48)
                        subtitle_font = ImageFont.truetype(font_path, 32)
                        topic_font = ImageFont.truetype(font_path, 36)
                        logger.debug(f"日本語フォントを使用: {font_path}")
                        break
                    except (OSError, IOError):
                        continue

            # フォントが見つからない場合はデフォルトを使用
            if title_font is None or subtitle_font is None or topic_font is None:
                logger.warning("日本語フォントが見つかりません。デフォルトフォントを使用します。")
                title_font = ImageFont.load_default()
                subtitle_font = ImageFont.load_default()
                topic_font = ImageFont.load_default()

            # テキストの位置と色
            width, height = img.size
            text_color = (255, 255, 255)  # 白色
            outline_color = (0, 0, 0)  # 黒色（アウトライン）

            # 肩書を取得
            person_title = get_person_title(person_name)
            if not person_title:
                person_title = person_name  # フォールバック

            # 左側に肩書と名前を配置（参考画像スタイル）
            left_margin = 50
            title_y = height // 2 - 60  # 中央より少し上

            # 肩書を上に（小さいフォント）
            self._draw_text_with_outline(
                draw,
                person_title,
                left_margin,
                title_y,
                subtitle_font,
                text_color,
                outline_color,
                anchor="lm",  # left-middle
            )

            # 人物名を下に（大きいフォント）
            name_y = title_y + 50
            self._draw_text_with_outline(
                draw,
                person_name,
                left_margin,
                name_y,
                title_font,
                text_color,
                outline_color,
                anchor="lm",  # left-middle
            )

            # トピックを下部中央に（オプション）
            short_topic = topic[:40] + "..." if len(topic) > 40 else topic
            topic_y = height - 80
            self._draw_text_with_outline(
                draw,
                short_topic,
                width // 2,
                topic_y,
                topic_font,
                text_color,
                outline_color,
            )

            img.save(image_path, quality=95)

        except Exception as e:
            logger.warning(f"Failed to add text overlay: {e}")

    @staticmethod
    def _draw_text_with_outline(
        draw: ImageDraw.Draw,
        text: str,
        x: int,
        y: int,
        font: ImageFont.FreeTypeFont,
        fill: tuple,
        outline: tuple,
        outline_width: int = 2,
        anchor: str = "mm",
    ) -> None:
        """Draw text with outline for better visibility."""
        # アウトラインを描画
        for adj in range(-outline_width, outline_width + 1):
            for adj2 in range(-outline_width, outline_width + 1):
                draw.text(
                    (x + adj, y + adj2),
                    text,
                    font=font,
                    fill=outline,
                    anchor=anchor,
                )
        # メインテキストを描画
        draw.text((x, y), text, font=font, fill=fill, anchor=anchor)
