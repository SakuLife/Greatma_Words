"""
Thumbnail generation service using AI APIs.
Supports Nanobanana Pro, DALL-E, and Stable Diffusion.

YouTubeサムネイル用に最適化:
- 大きな太字テキストでインパクトを出す
- 黄色・オレンジなどのアクセントカラー
- 人物は右側、左側にキャッチコピー
- 視認性の高いデザイン
"""

import io
from pathlib import Path

import requests
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from app.config import settings
from app.utils.logger import logger
from app.utils.person_titles import get_person_title, get_person_appearance


class ThumbnailGenerator:
    """Generates YouTube thumbnails featuring person portraits with eye-catching design."""

    # サムネイル用カラーパレット
    COLORS = {
        "yellow": (255, 215, 0),      # ゴールド（メインキャッチ用）
        "orange": (255, 140, 0),       # オレンジ（アクセント）
        "white": (255, 255, 255),      # 白（名前用）
        "black": (0, 0, 0),            # 黒（縁取り）
        "red": (255, 50, 50),          # 赤（強調用）
        "shadow": (30, 30, 30),        # 影（グレー）
    }

    def __init__(self):
        """Initialize thumbnail generator."""
        self.openai_client = None
        # KIEAI APIキーを使用（nanobanana_api_keyが設定されていない場合）
        self.nanobanana_api_key = settings.nanobanana_api_key or settings.kieai_api_key
        self.nanobanana_api_url = settings.nanobanana_api_url
        # nanobanana proモデルを使用（サムネイル用に高品質）
        self.thumbnail_model = settings.nanobanana_pro_model

        if settings.openai_api_key:
            self.openai_client = OpenAI(api_key=settings.openai_api_key)

    async def generate_thumbnail(
        self,
        person_name: str,
        topic: str,
        output_path: Path,
        style: str = "professional",
        quote: str | None = None,
        thumbnail_copy: dict | None = None,
        reference_image_urls: list[str] | None = None,
    ) -> Path:
        """
        Generate a YouTube thumbnail featuring the person with text.

        Args:
            person_name: Name of the person
            topic: Video topic/theme
            output_path: Where to save the thumbnail
            style: Thumbnail style (professional, dramatic, modern, etc.)
            quote: Catchphrase or famous quote to display (optional)
            thumbnail_copy: AI生成されたキャッチコピー {
                "main_copy": "メインコピー",
                "sub_copy": "サブコピー",
                "keywords": ["キーワード"]
            }
            reference_image_urls: 参照画像のURLリスト（img2img用）

        Returns:
            Path to generated thumbnail file

        Raises:
            RuntimeError: If thumbnail generation fails
        """
        logger.info(f"Generating thumbnail for '{person_name}' - '{topic}'")

        provider = settings.thumbnail_provider

        if provider == "nanobanana":
            thumbnail_path = await self._generate_with_nanobanana(
                person_name, topic, output_path, style, quote, thumbnail_copy, reference_image_urls
            )
        elif provider == "dalle":
            thumbnail_path = await self._generate_with_dalle(
                person_name, topic, output_path, style, quote
            )
        elif provider == "stable-diffusion":
            thumbnail_path = await self._generate_with_stable_diffusion(
                person_name, topic, output_path, style, quote
            )
        else:
            raise ValueError(f"Unsupported thumbnail provider: {provider}")

        logger.info(f"Thumbnail saved to {thumbnail_path}")
        return thumbnail_path

    # リトライ設定
    RETRY_WAIT_SECONDS = 180  # リトライ前の待機時間（3分）
    MAX_RETRIES = 1  # リトライ回数（1回まで）

    async def _generate_with_nanobanana(
        self, person_name: str, topic: str, output_path: Path, style: str,
        quote: str | None = None, thumbnail_copy: dict | None = None,
        reference_image_urls: list[str] | None = None
    ) -> Path:
        """Generate thumbnail using KIE AI API (nano-banana-pro model) with text."""
        if not self.nanobanana_api_key:
            logger.warning(
                "KIE AI API key not configured, falling back to DALL-E"
            )
            return await self._generate_with_dalle(person_name, topic, output_path, style, quote)

        last_error: Exception | None = None
        current_ref_urls = reference_image_urls
        for retry in range(self.MAX_RETRIES + 1):
            if retry > 0:
                # 参照画像関連エラーの場合、参照画像なしでリトライ
                error_str = str(last_error) if last_error else ""
                is_ref_image_error = any(kw in error_str for kw in [
                    "403", "Forbidden", "image_input", "file type not supported",
                ])
                if is_ref_image_error:
                    logger.info(
                        f"参照画像関連エラー → 参照画像なしで再生成します: {error_str[:100]}"
                    )
                    current_ref_urls = None
                else:
                    logger.info(
                        f"サムネイル生成リトライ {retry}/{self.MAX_RETRIES}: "
                        f"{self.RETRY_WAIT_SECONDS}秒待機後に再実行します..."
                    )
                    import time as _time
                    _time.sleep(self.RETRY_WAIT_SECONDS)

            try:
                return await self._generate_nanobanana_once(
                    person_name, topic, output_path, style, quote, thumbnail_copy, current_ref_urls
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    f"サムネイル生成失敗（試行{retry + 1}/{self.MAX_RETRIES + 1}）: {e}"
                )

        raise RuntimeError(
            f"Thumbnail generation failed with KIE AI after {self.MAX_RETRIES + 1} attempts: {last_error}"
        ) from last_error

    async def _generate_nanobanana_once(
        self, person_name: str, topic: str, output_path: Path, style: str,
        quote: str | None = None, thumbnail_copy: dict | None = None,
        reference_image_urls: list[str] | None = None
    ) -> Path:
        """KIE AI APIでサムネイルを1回生成する（リトライなし）。"""
        import time

        # 肩書を取得
        person_title = get_person_title(person_name) or ""

        # プロンプト作成（文字入り画像生成用）
        prompt = self._create_thumbnail_prompt_with_text(
            person_name, person_title, topic, style, thumbnail_copy, reference_image_urls
        )
        logger.info(f"KIE AI thumbnail prompt: {prompt}")

        # KIE AI API: タスク作成
        headers = {
            "Authorization": f"Bearer {self.nanobanana_api_key}",
            "Content-Type": "application/json",
        }

        # KIE AI API仕様に合わせたペイロード
        # nanobanana pro: 高品質サムネイル用（後でPythonで文字追加）
        input_params = {
            "prompt": prompt,
            "aspect_ratio": "16:9",  # YouTubeサムネイル
            "resolution": "2K",  # 高解像度
            "output_format": "png",
        }

        # 参照画像がある場合は image_input パラメータを追加（配列形式）
        # base64 data URIはKIE AIが非対応のためフィルタリング
        if reference_image_urls:
            valid_urls = [url for url in reference_image_urls if not url.startswith("data:")]
            if valid_urls:
                input_params["image_input"] = valid_urls[:8]  # 最大8枚
                logger.info(f"[IMG2IMG] サムネイル用参照画像を使用: {len(valid_urls)}枚")
            if len(valid_urls) < len(reference_image_urls):
                logger.info(f"[INFO] base64画像{len(reference_image_urls) - len(valid_urls)}枚はKIE AI非対応のためスキップ")

        payload = {
            "model": self.thumbnail_model,  # google/nano-banana-pro
            "input": input_params,
        }
        logger.info(f"Using thumbnail model: {self.thumbnail_model}")

        # タスク作成
        response = requests.post(
            f"{self.nanobanana_api_url}/jobs/createTask",
            json=payload,
            headers=headers,
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()

        logger.info(f"KIE AI createTask response: {result}")

        # APIエラーチェック（code: 500等）
        api_code = result.get("code")
        if api_code and api_code != 200:
            error_msg = result.get("msg", "Unknown API error")
            raise ValueError(f"KIE AI API error (code={api_code}): {error_msg}")

        # KIE AI response format: {"code": 200, "data": {"taskId": "..."}}
        data = result.get("data") or {}
        task_id = (
            data.get("taskId")
            or data.get("task_id")
            or data.get("id")
            or result.get("id")
            or result.get("task_id")
            or result.get("taskId")
        )
        if not task_id:
            raise ValueError(f"No task ID in response: {result}")

        logger.info(f"KIE AI task created: {task_id}")

        # ポーリングでタスク完了を待つ
        max_attempts = 60  # 最大60回（約5分）
        for attempt in range(max_attempts):
            time.sleep(5)  # 5秒待機

            status_response = requests.get(
                f"{self.nanobanana_api_url}/jobs/recordInfo?taskId={task_id}",
                headers=headers,
                timeout=30,
            )
            status_response.raise_for_status()
            status_result = status_response.json()

            # KIE AI uses "state" not "status"
            state = status_result.get("data", {}).get("state")
            logger.info(f"Task {task_id} state: {state} (attempt {attempt + 1}/{max_attempts})")
            if attempt == 0:  # 最初の1回だけ全レスポンスをログ
                logger.info(f"KIE AI status response: {status_result}")

            if state == "success":
                # KIE AI: resultJsonをパースしてresultUrlsを取得
                import json

                result_json_str = status_result.get("data", {}).get("resultJson")
                if result_json_str:
                    try:
                        result_json = json.loads(result_json_str)
                        result_urls = result_json.get("resultUrls", [])
                        image_url = result_urls[0] if result_urls else None
                        logger.info(f"Parsed resultJson, got image_url: {image_url}")
                    except (json.JSONDecodeError, IndexError, TypeError) as e:
                        logger.error(f"Failed to parse resultJson: {e}")
                        image_url = None
                else:
                    # フォールバック: 他のフォーマットも試す
                    image_url = (
                        status_result.get("result", {}).get("url")
                        or status_result.get("output", {}).get("url")
                        or status_result.get("data", {}).get("result", {}).get("url")
                        or status_result.get("data", {}).get("output", {}).get("url")
                        or status_result.get("image_url")
                        or status_result.get("url")
                    )

                if not image_url:
                    raise ValueError(f"No image URL in completed task: {status_result}")

                logger.info(f"KIE AI image URL: {image_url}")

                # 画像をダウンロード
                logger.info(f"Downloading thumbnail image from: {image_url}")
                img_response = requests.get(image_url, timeout=60)
                logger.info(f"Download response status: {img_response.status_code}, size: {len(img_response.content)} bytes")
                img_response.raise_for_status()

                # 画像を開いてYouTubeサムネイルサイズにリサイズ
                img = Image.open(io.BytesIO(img_response.content))

                # RGBAをRGBに変換（JPEG保存用）
                if img.mode == "RGBA":
                    background = Image.new("RGB", img.size, (0, 0, 0))
                    background.paste(img, mask=img.split()[3])
                    img = background

                # 1280x720にリサイズ
                img = img.resize((1280, 720), Image.Resampling.LANCZOS)

                # 保存
                output_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(output_path, quality=95)

                logger.info(f"Thumbnail saved: {output_path}")
                return output_path

            elif state == "fail" or state == "failed" or state == "error":
                error_msg = (
                    status_result.get("data", {}).get("failMsg")
                    or status_result.get("error")
                    or status_result.get("message")
                    or "Unknown error"
                )
                raise ValueError(f"Task failed: {error_msg}")

        raise TimeoutError(f"Task {task_id} did not complete within {max_attempts * 5} seconds")

    async def _generate_with_dalle(
        self, person_name: str, topic: str, output_path: Path, style: str, quote: str | None = None
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
            self._add_text_overlay(output_path, person_name, topic, quote)

            return output_path

        except Exception as e:
            logger.error(f"DALL-E thumbnail generation failed: {e}")
            raise RuntimeError(f"Failed to generate thumbnail: {e}") from e

    async def _generate_with_stable_diffusion(
        self, person_name: str, topic: str, output_path: Path, style: str, quote: str | None = None
    ) -> Path:
        """Generate thumbnail using Stable Diffusion API."""
        # Stable Diffusion API実装（Replicate等を使用）
        # 実装は後で追加可能
        logger.warning("Stable Diffusion not yet implemented, using DALL-E")
        return await self._generate_with_dalle(person_name, topic, output_path, style, quote)

    def _create_thumbnail_prompt_with_text(
        self,
        person_name: str,
        person_title: str,
        topic: str,
        style: str,
        thumbnail_copy: dict | None = None,
        reference_image_urls: list[str] | None = None,
    ) -> str:
        """
        Create a prompt for thumbnail generation WITH TEXT.

        nanobanana proに文字入り画像を生成させるプロンプト
        """
        # キャッチコピーを取得
        if thumbnail_copy:
            main_copy = thumbnail_copy.get("main_copy", "")
            sub_copy = thumbnail_copy.get("sub_copy", "")
        else:
            main_copy = ""
            sub_copy = ""

        # フォールバック: main_copyが空の場合はトピックから生成
        if not main_copy:
            main_copy = topic[:8] if topic else person_name
        if not sub_copy:
            sub_copy = topic[:15] if topic else ""

        # 外見描写は常に使用（参照画像がある場合も顔特徴の参考指示を追加）
        appearance = get_person_appearance(person_name)
        if reference_image_urls:
            person_description = (
                f"PERSON: {appearance}, front-facing portrait, looking directly at camera, facing forward.\n"
                f"REFERENCE IMAGES: Use ONLY for facial identity of {person_name}. "
                f"Copy the face and facial features from reference. "
                f"CRITICAL: Completely IGNORE the background, setting, environment, pose, "
                f"and clothing from reference images. "
                f"ALWAYS generate with solid dark black studio background.\n"
                f"NEGATIVE: No side view, no profile, no turned head, no looking away, "
                f"no outdoor background, no natural scenery from references."
            )
        else:
            person_description = (
                f"PERSON: {appearance}, front-facing portrait, looking directly at camera, facing forward.\n"
                f"NEGATIVE: No side view, no profile, no turned head, no looking away."
            )

        # プロンプト構築
        prompt = f"""YouTube thumbnail design.

TEXT ON IMAGE (MUST INCLUDE):
- Large bold yellow Japanese text "{main_copy}" on the upper left
- White Japanese text "{sub_copy}" below the main text
- White bold text "{person_name}" at the bottom left
- Small orange text "{person_title}" below the name

LAYOUT:
- Person portrait on the RIGHT side (50-60% of frame)
- Text area on the LEFT side with dark background
- 16:9 aspect ratio

STYLE:
- Professional YouTube thumbnail style
- Dramatic lighting on the person
- Dark/black gradient background on left for text visibility
- Eye-catching, click-worthy design
- High contrast between text and background

{person_description}

IMPORTANT: The Japanese text must be clearly readable and prominent."""

        return prompt

    def _add_text_overlay(
        self, image_path: Path, person_name: str, topic: str, quote: str | None = None
    ) -> None:
        """
        Add eye-catching text overlay to thumbnail.

        YouTubeサムネイル最適化デザイン:
        - 大きな太字テキスト（黄色/オレンジ）でインパクト
        - 複数行に分けてキャッチーな配置
        - 太い黒縁取りで視認性向上
        - 影効果で立体感
        """
        try:
            img = Image.open(image_path)

            # RGBAをRGBに変換（JPEG保存用）
            if img.mode == "RGBA":
                background = Image.new("RGB", img.size, (0, 0, 0))
                background.paste(img, mask=img.split()[3])
                img = background

            # YouTubeサムネイル標準サイズにリサイズ
            thumbnail_width = 1280
            thumbnail_height = 720
            img = img.resize((thumbnail_width, thumbnail_height), Image.Resampling.LANCZOS)

            draw = ImageDraw.Draw(img)
            width, height = img.size

            # フォントを読み込み
            fonts = self._load_fonts()

            # 肩書を取得
            person_title = get_person_title(person_name)
            if not person_title:
                person_title = ""

            # キャッチコピーを作成（名言 or トピック）
            catchphrase = quote if quote else topic

            # テキストを適切な長さに分割（インパクト重視で短く）
            lines = self._split_catchphrase(catchphrase, max_chars_per_line=12)

            # ============================================
            # レイアウト: 左側にテキスト配置
            # ============================================
            left_margin = 50
            current_y = 80

            # 【上部】キャッチコピー（黄色、大きな太字）
            for i, line in enumerate(lines[:3]):  # 最大3行
                # 1行目は特に大きく、黄色
                if i == 0:
                    font = fonts["catchphrase_large"]
                    color = self.COLORS["yellow"]
                else:
                    font = fonts["catchphrase_medium"]
                    color = self.COLORS["white"]

                self._draw_text_with_shadow(
                    draw, line, left_margin, current_y, font, color,
                    outline_width=6, shadow_offset=4
                )
                current_y += self._get_font_height(font) + 10

            # 【下部】人物名（白、大きな太字）+ 肩書
            name_y = height - 180
            self._draw_text_with_shadow(
                draw, person_name, left_margin, name_y,
                fonts["name"], self.COLORS["white"],
                outline_width=5, shadow_offset=3
            )

            # 肩書（小さめ、オレンジ）
            if person_title:
                title_y = name_y + self._get_font_height(fonts["name"]) + 5
                self._draw_text_with_shadow(
                    draw, person_title, left_margin, title_y,
                    fonts["title"], self.COLORS["orange"],
                    outline_width=3, shadow_offset=2
                )

            img.save(image_path, quality=95)
            logger.info(f"✅ サムネイル完成: {person_name} - {catchphrase[:20]}...")

        except Exception as e:
            logger.warning(f"Failed to add text overlay: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    def _load_fonts(self) -> dict:
        """
        Load fonts for thumbnail text overlay.

        Returns:
            Dictionary of font objects for different text elements
        """
        import platform
        import os

        fonts = {}

        # フォントサイズ設定（YouTubeサムネイル用に大きく）
        sizes = {
            "catchphrase_large": 85,   # メインキャッチ（1行目）
            "catchphrase_medium": 70,  # キャッチ（2-3行目）
            "name": 75,                 # 人物名
            "title": 35,                # 肩書
        }

        # プラットフォーム別フォントパス
        if platform.system() == "Windows":
            font_paths = [
                "C:/Windows/Fonts/YuGothB.ttc",   # 游ゴシック Bold
                "C:/Windows/Fonts/meiryob.ttc",  # メイリオ Bold
                "C:/Windows/Fonts/msgothic.ttc", # MSゴシック
                "C:/Windows/Fonts/meiryo.ttc",   # メイリオ
            ]
        elif platform.system() == "Darwin":
            font_paths = [
                "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
                "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
            ]
        else:  # Linux
            font_paths = [
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            ]

        # フォントを読み込み
        selected_font_path = None
        for font_path in font_paths:
            if os.path.exists(font_path):
                selected_font_path = font_path
                break

        if selected_font_path:
            try:
                for key, size in sizes.items():
                    if platform.system() == "Linux":
                        fonts[key] = ImageFont.truetype(selected_font_path, size, index=0)
                    else:
                        fonts[key] = ImageFont.truetype(selected_font_path, size)
                logger.info(f"✅ フォント読み込み成功: {selected_font_path}")
            except Exception as e:
                logger.warning(f"フォント読み込みエラー: {e}")
                fonts = self._get_default_fonts(sizes)
        else:
            logger.warning("⚠️ 日本語フォントが見つかりません")
            fonts = self._get_default_fonts(sizes)

        return fonts

    def _get_default_fonts(self, sizes: dict) -> dict:
        """Get default fonts when Japanese fonts are not available."""
        fonts = {}
        for key in sizes:
            fonts[key] = ImageFont.load_default()
        return fonts

    def _get_font_height(self, font: ImageFont.FreeTypeFont) -> int:
        """Get the height of a font."""
        try:
            bbox = font.getbbox("あ")
            return bbox[3] - bbox[1]
        except Exception:
            return 50  # デフォルト高さ

    def _split_catchphrase(self, text: str, max_chars_per_line: int = 12) -> list[str]:
        """
        Split catchphrase into multiple lines for impact.

        短い行に分割してインパクトを出す
        """
        if not text:
            return []

        # 句読点で分割を試みる
        delimiters = ["。", "！", "？", "、", "…", " "]
        lines = []
        current = ""

        for char in text:
            current += char
            if char in delimiters or len(current) >= max_chars_per_line:
                if current.strip():
                    lines.append(current.strip())
                current = ""

        if current.strip():
            lines.append(current.strip())

        return lines[:4]  # 最大4行

    def _draw_text_with_shadow(
        self,
        draw: ImageDraw.Draw,
        text: str,
        x: int,
        y: int,
        font: ImageFont.FreeTypeFont,
        fill: tuple,
        outline_width: int = 4,
        shadow_offset: int = 3,
    ) -> None:
        """
        Draw text with shadow and thick outline for YouTube thumbnail style.

        影 → 太い縁取り → メインテキスト の順で描画
        """
        outline_color = self.COLORS["black"]
        shadow_color = self.COLORS["shadow"]

        # 1. 影を描画（右下にオフセット）
        for adj in range(-2, 3):
            for adj2 in range(-2, 3):
                draw.text(
                    (x + shadow_offset + adj, y + shadow_offset + adj2),
                    text,
                    font=font,
                    fill=shadow_color,
                )

        # 2. 太い縁取りを描画
        for adj in range(-outline_width, outline_width + 1):
            for adj2 in range(-outline_width, outline_width + 1):
                if adj != 0 or adj2 != 0:
                    draw.text(
                        (x + adj, y + adj2),
                        text,
                        font=font,
                        fill=outline_color,
                    )

        # 3. メインテキストを描画
        draw.text((x, y), text, font=font, fill=fill)

