"""
Test script for thumbnail text overlay only (without image generation).
Uses an existing image or creates a test image to verify the new YouTube-style design.

新デザインの特徴:
- 大きな太字テキスト（黄色/オレンジ）
- 影効果と太い縁取り
- インパクトのあるレイアウト
"""

from pathlib import Path
from PIL import Image, ImageDraw
from app.services.thumbnail_generator import ThumbnailGenerator
from app.utils.logger import logger


def create_test_background(output_path: Path, width: int = 1280, height: int = 720) -> None:
    """
    Create a test background image (dark gradient with simulated portrait area).

    テスト用の暗い背景画像を作成
    """
    # 暗いグラデーション背景を作成
    img = Image.new("RGB", (width, height), (10, 10, 20))
    draw = ImageDraw.Draw(img)

    # 右側に人物の位置を示す円（シミュレーション）
    person_x = int(width * 0.7)
    person_y = int(height * 0.4)
    radius = 150

    # グラデーション効果（簡易版）
    for i in range(height):
        gray = int(20 + (i / height) * 15)
        draw.line([(0, i), (width, i)], fill=(gray, gray, gray + 10))

    # 人物の位置を示す（明るいエリア）
    for r in range(radius, 0, -1):
        alpha = int(50 * (1 - r / radius))
        draw.ellipse(
            [person_x - r, person_y - r, person_x + r, person_y + r],
            fill=(50 + alpha, 50 + alpha, 60 + alpha),
        )

    img.save(output_path, quality=95)
    print(f"テスト背景画像を作成: {output_path}")


def test_text_overlay():
    """Test the new YouTube-style text overlay design."""
    print("\n" + "=" * 60)
    print("[TEST] YouTube サムネイル テキストオーバーレイ テスト")
    print("=" * 60)

    # テストデータ（複数パターン）
    test_cases = [
        {
            "person_name": "ウォーレン・バフェット",
            "topic": "投資の極意",
            "catchphrase": "リスクは自分が何をやっているかよく分からない時に起こる",
        },
        {
            "person_name": "スティーブ・ジョブズ",
            "topic": "イノベーション",
            "catchphrase": "Stay hungry, Stay foolish",
        },
        {
            "person_name": "イーロン・マスク",
            "topic": "未来を創る力",
            "catchphrase": "失敗を恐れるな、挑戦しないことを恐れろ",
        },
    ]

    # テスト出力先
    output_dir = Path("data/test_outputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 既存の画像を探す
    existing_projects = list(Path("data/projects").glob("*/images/*.png"))

    for i, test_case in enumerate(test_cases):
        print(f"\n--- テストケース {i + 1}: {test_case['person_name']} ---")

        test_output = output_dir / f"test_thumbnail_{i + 1}.jpg"

        try:
            # 画像ソースを決定
            if existing_projects and i < len(existing_projects):
                # 既存の画像を使用
                source_image = existing_projects[i % len(existing_projects)]
                print(f"使用する画像: {source_image}")
                img = Image.open(source_image)
                img = img.convert("RGB")
                img = img.resize((1280, 720), Image.Resampling.LANCZOS)
            else:
                # テスト用背景を作成
                print("テスト用背景画像を生成...")
                img = Image.new("RGB", (1280, 720), (15, 15, 25))

            # 一時的に保存
            temp_path = output_dir / f"temp_thumbnail_{i + 1}.jpg"
            img.save(temp_path, quality=95)

            # ThumbnailGeneratorのテキストオーバーレイ機能を使用
            thumbnail_gen = ThumbnailGenerator()
            thumbnail_gen._add_text_overlay(
                image_path=temp_path,
                person_name=test_case["person_name"],
                topic=test_case["topic"],
                quote=test_case["catchphrase"],
            )

            # 最終出力先に移動
            temp_path.rename(test_output)

            print(f"[OK] 成功!")
            print(f"   保存先: {test_output}")
            print(f"   キャッチコピー: {test_case['catchphrase'][:30]}...")
            print(f"   名前: {test_case['person_name']}")

            # ファイルサイズ確認
            if test_output.exists():
                file_size = test_output.stat().st_size / 1024  # KB
                print(f"   ファイルサイズ: {file_size:.1f} KB")

        except Exception as e:
            logger.error(f"テキストオーバーレイ失敗: {e}")
            print(f"[NG] 失敗: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("[OUTPUT] 出力先: data/test_outputs/")
    print("[INFO] 生成されたサムネイルを確認してください")
    print("=" * 60)


def test_full_thumbnail_generation():
    """
    Test full thumbnail generation with API (requires API key).

    フルサムネイル生成テスト（API必要）
    """
    import asyncio

    print("\n" + "=" * 60)
    print("[TEST] フル サムネイル生成テスト（API使用）")
    print("=" * 60)

    from app.config import settings

    if not settings.kieai_api_key and not settings.nanobanana_api_key:
        print("[WARN] APIキーが設定されていません。")
        print("   KIEAI_API_KEY または NANOBANANA_API_KEY を .env に設定してください。")
        return

    # テストデータ
    person_name = "ウォーレン・バフェット"
    topic = "投資の黄金法則"
    quote = "他人が貪欲な時に恐れ、他人が恐れている時に貪欲になれ"

    # 出力先
    output_dir = Path("data/test_outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "test_full_thumbnail.jpg"

    async def run_test():
        thumbnail_gen = ThumbnailGenerator()
        try:
            result = await thumbnail_gen.generate_thumbnail(
                person_name=person_name,
                topic=topic,
                output_path=output_path,
                style="dramatic",
                quote=quote,
            )
            print(f"[OK] サムネイル生成成功: {result}")
        except Exception as e:
            print(f"[NG] サムネイル生成失敗: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(run_test())


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        test_full_thumbnail_generation()
    else:
        test_text_overlay()
        print("\n[HINT] --full オプションでAPI使用のフル生成テストができます")
