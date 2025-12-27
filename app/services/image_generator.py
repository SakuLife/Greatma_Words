"""
Image generation service using AI APIs and PIL for compositing.
"""

import io
from pathlib import Path

import requests
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

from app.config import settings
from app.utils.logger import logger
from app.utils.person_titles import get_person_title, get_person_quote


class ImageGenerator:
    """Generates images for video slides."""

    def __init__(self):
        """Initialize image generator."""
        self.openai_client = None
        self.kieai_api_key = settings.kieai_api_key
        self.kieai_api_url = settings.kieai_api_url

        if settings.openai_api_key:
            self.openai_client = OpenAI(api_key=settings.openai_api_key)

    async def generate_person_slide(
        self,
        person_name: str,
        person_description: str,
        output_path: Path,
        background_color: str | None = None,
    ) -> Path:
        """
        Generate a slide image featuring a person.

        Args:
            person_name: Name of the person
            person_description: Description for image generation
            output_path: Where to save the generated image
            background_color: Background color hex code

        Returns:
            Path to generated image file

        Raises:
            RuntimeError: If image generation fails
        """
        background_color = background_color or settings.default_background_color

        # 既存の画像がある場合はスキップ
        if output_path.exists():
            logger.info(f"[SKIP] 既存の画像が見つかりました。スキップします: {output_path}")
            return output_path

        logger.info(f"[START] 画像生成を開始します: '{person_name}'")
        logger.info(f"  出力先: {output_path}")

        # Method 1: Generate AI portrait with KIEAI (優先)
        if settings.use_kieai and self.kieai_api_key:
            logger.info("[INFO] KIEAI APIを使用して画像を生成します")
            portrait_path = await self._generate_portrait_with_kieai(
                person_name, person_description
            )
        # Method 2: Generate AI portrait with DALL-E
        elif settings.use_dalle and self.openai_client:
            logger.info("[INFO] DALL-E APIを使用して画像を生成します")
            portrait_path = await self._generate_portrait_with_dalle(
                person_name, person_description
            )
        else:
            # Method 3: Create simple placeholder
            portrait_path = None
            logger.warning("[WARN] 画像生成APIが設定されていません。プレースホルダー画像を使用します")

        # Create slide with text overlay
        slide_path = self._create_slide(
            person_name=person_name,
            person_description=person_description,
            portrait_path=portrait_path,
            output_path=output_path,
            background_color=background_color,
        )

        logger.info(f"Image saved to {slide_path}")
        return slide_path

    async def _generate_portrait_with_kieai(
        self, person_name: str, person_description: str
    ) -> Path:
        """Generate a portrait using KIEAI nanobanana API (非同期ジョブ形式)."""
        try:
            # プロンプト: 背景暗め、顔アップ、文字なし、人物は右半分に配置
            prompt = (
                f"Professional portrait close-up of {person_name}. "
                f"{person_description}. "
                f"Dark background, dramatic lighting, "
                f"face and upper body visible, "
                f"person positioned on the right half of the image, "
                f"left half is empty dark background, "
                f"no text, no letters, no words, "
                f"high quality, realistic portrait photography style, "
                f"suitable for educational content."
            )

            logger.debug(f"KIEAI nanobanana prompt: {prompt}")

            # KIEAI nanobanana API呼び出し（非同期ジョブ形式）
            headers = {
                "Authorization": f"Bearer {self.kieai_api_key}",
                "Content-Type": "application/json",
            }

            # タスクを作成
            payload = {
                "model": settings.kieai_model,  # "google/nano-banana"
                "input": {
                    "prompt": prompt,
                    "output_format": "png",
                    "image_size": "16:9",  # 動画用のアスペクト比
                },
            }

            logger.info("[API] KIEAI nanobanana APIにリクエストを送信します...")
            logger.info(f"[API] プロンプト: {prompt[:100]}...")
            create_response = requests.post(
                f"{self.kieai_api_url}/jobs/createTask",
                json=payload,
                headers=headers,
                timeout=60,
            )
            create_response.raise_for_status()
            create_result = create_response.json()

            # デバッグ: レスポンス全体をログに出力
            logger.debug(f"KIEAI API response: {create_result}")

            # KIEAI APIのレスポンス構造: {'code': 200, 'msg': 'success', 'data': {'taskId': '...'}}
            # dataフィールドからtaskIdを取得
            data = create_result.get("data", {})
            task_id = (
                data.get("taskId")
                or data.get("task_id")
                or create_result.get("taskId")  # フォールバック
                or create_result.get("task_id")
                or create_result.get("id")
                or create_result.get("task")
            )
            if not task_id:
                logger.error(f"KIEAI API response structure: {create_result}")
                raise ValueError(f"No taskId in KIEAI API response. Response: {create_result}")

            logger.info(f"[API] KIEAIタスクが作成されました: {task_id}")
            logger.info(f"[API] タスクの完了を待機します（最大5分）...")

            # タスクの完了を待機（ポーリング）
            import asyncio
            max_wait_time = 300  # 最大5分
            poll_interval = 5  # 5秒ごとに確認
            elapsed_time = 0

            while elapsed_time < max_wait_time:
                await asyncio.sleep(poll_interval)
                elapsed_time += poll_interval

                # タスクの状態を確認
                status_response = requests.get(
                    f"{self.kieai_api_url}/jobs/recordInfo",
                    params={"taskId": task_id},
                    headers={"Authorization": f"Bearer {self.kieai_api_key}"},
                    timeout=30,
                )
                status_response.raise_for_status()
                status_result = status_response.json()

                # KIEAI APIのレスポンス構造を確認（dataフィールド内に情報がある可能性）
                logger.info(f"KIEAI status response: {status_result}")

                # dataフィールドから情報を取得
                data = status_result.get("data", {})
                if not data:
                    data = status_result  # dataがない場合は直接使用

                # ステータスを取得（複数の可能性を確認）
                status = (
                    data.get("status")
                    or data.get("state")
                    or data.get("taskStatus")
                    or status_result.get("status")
                    or status_result.get("state")
                    or status_result.get("taskStatus")
                )

                # codeフィールドも確認（200なら成功）
                code = status_result.get("code")
                if code == 200 and not status:
                    status = "success"

                logger.info(f"Task status: {status}, code: {code}")

                # 処理中状態の判定
                if status in ["waiting", "processing", "pending", "in_progress", "running"]:
                    # まだ処理中なので、ポーリングを続ける
                    logger.debug(f"Task still processing... status={status} ({elapsed_time}s elapsed)")
                    continue

                # 完了状態の判定を拡張
                if status in ["completed", "success", "done", "SUCCESS", "COMPLETED"] or (code == 200 and status == "success"):
                    # 画像URLを取得
                    # KIEAI APIの実際のレスポンス構造:
                    # data.resultJson = '{"resultUrls":["https://..."]}'
                    image_url = None

                    # resultJsonフィールドから画像URLを取得
                    result_json_str = data.get("resultJson") or status_result.get("resultJson")
                    if result_json_str:
                        try:
                            import json
                            result_json = json.loads(result_json_str)
                            result_urls = result_json.get("resultUrls", [])
                            if result_urls and len(result_urls) > 0:
                                image_url = result_urls[0]  # 最初のURLを使用
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.warning(f"Failed to parse resultJson: {e}")

                    # フォールバック: 他の可能性のあるフィールドも確認
                    if not image_url:
                        if isinstance(data, dict):
                            image_url = (
                                data.get("outputUrl")
                                or data.get("output_url")
                                or data.get("imageUrl")
                                or data.get("image_url")
                                or data.get("url")
                                or (data.get("output", {}) if isinstance(data.get("output"), dict) else {}).get("url")
                                or (data.get("result", {}) if isinstance(data.get("result"), dict) else {}).get("url")
                            )

                        if not image_url:
                            image_url = (
                                status_result.get("outputUrl")
                                or status_result.get("output_url")
                                or status_result.get("imageUrl")
                                or status_result.get("image_url")
                                or status_result.get("url")
                            )

                    if image_url:
                        logger.info(f"[API] KIEAI画像URLを取得しました: {image_url}")
                        logger.info("[API] 画像をダウンロード中...")

                        # Download image
                        img_response = requests.get(image_url, timeout=30)
                        img_response.raise_for_status()

                        # Save temporarily
                        temp_path = Path(f"temp_{person_name}.png")
                        with open(temp_path, "wb") as f:
                            f.write(img_response.content)

                        logger.info(f"[OK] 画像をダウンロードして保存しました: {temp_path}")
                        return temp_path
                    else:
                        logger.error(f"No image URL found in response. Full response: {status_result}")
                        raise ValueError(f"No image URL in completed task. Response: {status_result}")

                elif status in ["failed", "error", "FAILED", "ERROR"]:
                    error_msg = (
                        data.get("failMsg")
                        or data.get("error")
                        or status_result.get("failMsg")
                        or status_result.get("error")
                        or status_result.get("message")
                    )
                    raise RuntimeError(f"KIEAI task failed: {error_msg}")

                # 不明な状態
                logger.warning(f"Unknown task status: {status}. Continuing to poll...")

            raise TimeoutError(f"KIEAI task did not complete within {max_wait_time} seconds")

        except Exception as e:
            logger.error(f"KIEAI generation failed: {e}")
            # フォールバック: DALL-Eを試す
            if settings.use_dalle and self.openai_client:
                logger.info("Falling back to DALL-E")
                return await self._generate_portrait_with_dalle(person_name, person_description)
            raise RuntimeError(f"Failed to generate portrait with KIEAI: {e}") from e

    async def _generate_portrait_with_dalle(
        self, person_name: str, person_description: str
    ) -> Path:
        """Generate a portrait using DALL-E 3 (背景暗め、顔アップ、文字なし)."""
        try:
            # プロンプト: 背景暗め、顔アップ、文字なし、人物は右半分に配置
            prompt = (
                f"Professional portrait close-up of {person_name}. "
                f"{person_description}. "
                f"Dark background, dramatic lighting, "
                f"face and upper body visible, "
                f"person positioned on the right half of the image, "
                f"left half is empty dark background, "
                f"no text, no letters, no words, "
                f"high quality, realistic portrait photography style, "
                f"suitable for educational content."
            )

            logger.debug(f"DALL-E prompt: {prompt}")

            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )

            image_url = response.data[0].url
            logger.debug(f"DALL-E image URL: {image_url}")

            # Download image
            img_response = requests.get(image_url, timeout=30)
            img_response.raise_for_status()

            # Save temporarily
            temp_path = Path(f"temp_{person_name}.png")
            with open(temp_path, "wb") as f:
                f.write(img_response.content)

            return temp_path

        except Exception as e:
            logger.error(f"DALL-E generation failed: {e}")
            raise RuntimeError(f"Failed to generate portrait: {e}") from e

    def _create_slide(
        self,
        person_name: str,
        person_description: str,
        portrait_path: Path | None,
        output_path: Path,
        background_color: str,
    ) -> Path:
        """
        Create a slide image with person portrait and text.
        参考画像スタイル: 背景暗め、顔アップ、左側に肩書と名前

        Args:
            person_name: Person's name
            person_description: Person's description
            portrait_path: Path to portrait image (optional)
            output_path: Where to save the slide
            background_color: Background color hex

        Returns:
            Path to created slide
        """
        # ポートレート画像がある場合は、それをベースにする
        if portrait_path and portrait_path.exists():
            # ポートレート画像を開く（コピーを作成）
            image = Image.open(portrait_path).copy()

            # 動画サイズにリサイズ（アスペクト比を維持）
            target_width = settings.video_width
            target_height = settings.video_height

            # アスペクト比を維持してリサイズ
            img_ratio = image.width / image.height
            target_ratio = target_width / target_height

            if img_ratio > target_ratio:
                # 画像が横長 → 幅に合わせる
                new_width = target_width
                new_height = int(target_width / img_ratio)
            else:
                # 画像が縦長 → 高さに合わせる
                new_height = target_height
                new_width = int(target_height * img_ratio)

            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # キャンバスを作成（暗い背景）
            bg_rgb = self._hex_to_rgb(background_color)
            canvas = Image.new("RGB", (target_width, target_height), bg_rgb)

            # 画像を中央に配置（右寄せ）
            paste_x = target_width - new_width
            paste_y = (target_height - new_height) // 2
            canvas.paste(image, (paste_x, paste_y))

            image = canvas
        else:
            # ポートレートがない場合は、暗い背景のキャンバスを作成
            width = settings.video_width
            height = settings.video_height
            bg_rgb = self._hex_to_rgb(background_color)
            image = Image.new("RGB", (width, height), bg_rgb)

        draw = ImageDraw.Draw(image)

        # テキストオーバーレイを追加（左側に肩書と名前）
        self._add_text_overlays(draw, person_name, person_description, image.width, image.height)

        # Save image
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, quality=95)

        # Clean up temp portrait
        if portrait_path and portrait_path.exists() and "temp_" in str(portrait_path):
            portrait_path.unlink()

        return output_path

    def _add_portrait(self, canvas: Image.Image, portrait_path: Path) -> None:
        """Add portrait to the canvas."""
        try:
            portrait = Image.open(portrait_path)

            # Resize portrait to fit nicely
            max_portrait_size = (600, 600)
            portrait.thumbnail(max_portrait_size, Image.Resampling.LANCZOS)

            # Position portrait (left side)
            portrait_x = 100
            portrait_y = (canvas.height - portrait.height) // 2

            # Paste portrait
            if portrait.mode == "RGBA":
                canvas.paste(portrait, (portrait_x, portrait_y), portrait)
            else:
                canvas.paste(portrait, (portrait_x, portrait_y))

        except Exception as e:
            logger.warning(f"Failed to add portrait: {e}")

    def _add_text_overlays(
        self,
        draw: ImageDraw.Draw,
        person_name: str,
        person_description: str,
        width: int,
        height: int,
    ) -> None:
        """Add text overlays to the slide (参考画像スタイル: 左側に肩書と名前)."""
        try:
            # フォントの設定（日本語対応）- cutoutshortの方法を参考
            import platform
            import os
            title_font = None
            subtitle_font = None

            if platform.system() == "Windows":
                # Windows: cutoutshortと同じフォント候補を使用
                font_candidates = [
                    "C:/Windows/Fonts/meiryo.ttc",  # メイリオ（cutoutshortで使用）
                    "C:/Windows/Fonts/msgothic.ttc",  # MSゴシック
                    "C:/Windows/Fonts/YuGothM.ttc",  # 游ゴシック Medium（cutoutshortで使用）
                    "C:/Windows/Fonts/msmincho.ttc",  # MS明朝
                ]
                for font_path in font_candidates:
                    if os.path.exists(font_path):
                        try:
                            title_font = ImageFont.truetype(font_path, 31)  # 肩書: 1.3倍
                            subtitle_font = ImageFont.truetype(font_path, 96)  # 名前: 80%
                            quote_font = ImageFont.truetype(font_path, 31)  # 名言: 1.3倍
                            logger.info(f"[OK] 日本語フォントを使用: {font_path}")
                            break
                        except (OSError, IOError) as e:
                            logger.debug(f"フォント読み込み失敗: {font_path} - {e}")
                            continue
            elif platform.system() == "Darwin":  # macOS
                font_candidates = [
                    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
                    "/System/Library/Fonts/AppleGothic.ttf",
                ]
                for font_path in font_candidates:
                    if os.path.exists(font_path):
                        try:
                            title_font = ImageFont.truetype(font_path, 31)  # 肩書: 1.3倍
                            subtitle_font = ImageFont.truetype(font_path, 96)  # 名前: 80%
                            quote_font = ImageFont.truetype(font_path, 31)  # 名言: 1.3倍
                            logger.info(f"[OK] 日本語フォントを使用: {font_path}")
                            break
                        except (OSError, IOError) as e:
                            logger.debug(f"フォント読み込み失敗: {font_path} - {e}")
                            continue
            else:  # Linux (GitHub Actions ubuntu-latest)
                font_candidates = [
                    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
                    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                ]
                for font_path in font_candidates:
                    if os.path.exists(font_path):
                        try:
                            title_font = ImageFont.truetype(font_path, 31, index=0)  # 肩書: 1.3倍、日本語指定
                            subtitle_font = ImageFont.truetype(font_path, 96, index=0)  # 名前: 80%、日本語指定
                            quote_font = ImageFont.truetype(font_path, 31, index=0)  # 名言: 1.3倍、日本語指定
                            logger.info(f"✅ Linux 日本語フォントを使用: {font_path} (index=0, sizes=31/96/31)")
                            break
                        except (OSError, IOError) as e:
                            logger.debug(f"フォント読み込み失敗: {font_path} - {e}")
                            continue

            # フォントが見つからない場合はデフォルトを使用
            if title_font is None or subtitle_font is None:
                logger.error("⚠️ 日本語フォントが見つかりません！デフォルトフォントを使用します。")
                logger.error(f"⚠️ Platform: {platform.system()}, 画像の文字が文字化けする可能性があります。")
                title_font = ImageFont.load_default()
                subtitle_font = ImageFont.load_default()
                quote_font = ImageFont.load_default()
            else:
                logger.info("✅ 画像用フォント読み込み成功")

            # テキストの色（白）
            text_color = (255, 255, 255)  # 白色
            outline_color = (0, 0, 0)  # 黒色（アウトライン）

            # 肩書と名言を取得
            person_title = get_person_title(person_name)
            person_quote = get_person_quote(person_name)

            logger.info(f"テキストオーバーレイ: 人物='{person_name}', 肩書='{person_title}', 名言='{person_quote}'")

            if not person_title:
                person_title = ""  # 肩書がない場合は表示しない
            if not person_quote:
                person_quote = ""  # 名言がない場合は表示しない

            # 左側に肩書、名前、名言を配置（縦に並べる）
            left_margin = 80
            start_y = height // 4  # 上部1/4の位置から開始（少し上に）

            current_y = start_y

            # 肩書を上に（中サイズフォント）
            if person_title:
                self._draw_text_with_outline(
                    draw,
                    person_title,
                    left_margin,
                    current_y,
                    title_font,  # 肩書用フォント使用
                    text_color,
                    outline_color,
                    outline_width=4,  # アウトライン太く
                    anchor="lt",  # left-top
                )
                current_y += 61  # フォントサイズ31px + 行間30px = 61px

            # 人物名を中央に（大きいフォント）
            self._draw_text_with_outline(
                draw,
                person_name,
                left_margin,
                current_y,
                subtitle_font,  # 名前用フォント使用
                text_color,
                outline_color,
                outline_width=5,  # アウトライン太く
                anchor="lt",  # left-top
            )
            current_y += 126  # フォントサイズ96px + 行間30px = 126px

            # 名言を下に（引用符付き、中サイズフォント）
            if person_quote:
                # 名言を引用符で囲む
                quoted_text = f'「{person_quote}」'
                self._draw_text_with_outline(
                    draw,
                    quoted_text,
                    left_margin,
                    current_y,
                    quote_font,
                    text_color,
                    outline_color,
                    outline_width=3,
                    anchor="lt",  # left-top
                )

        except Exception as e:
            logger.warning(f"Failed to add text overlays: {e}")

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

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    @staticmethod
    def _wrap_text(text: str, max_chars: int) -> str:
        """Wrap text to specified character width."""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 <= max_chars:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = len(word)

        if current_line:
            lines.append(" ".join(current_line))

        return "\n".join(lines)
