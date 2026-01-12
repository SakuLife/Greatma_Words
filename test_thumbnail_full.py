"""
フルフローテスト: キャッチコピー生成 → サムネイル生成

1. AIでサムネ用キャッチコピーを生成
2. そのコピーを使ってnanobanana proでサムネイル生成
"""

import asyncio
from pathlib import Path

from app.config import settings
from app.services.thumbnail_copywriter import ThumbnailCopywriter
from app.services.thumbnail_generator import ThumbnailGenerator
from app.utils.logger import logger


async def test_full_thumbnail_flow():
    """フルフローテスト"""
    print("\n" + "=" * 60)
    print("[TEST] サムネイル生成フルフローテスト")
    print("=" * 60)

    # テストデータ
    person_name = "ウォーレン・バフェット"
    topic = "投資の黄金法則"
    quote = "他人が貪欲な時に恐れ、他人が恐れている時に貪欲になれ"

    # 出力先
    output_dir = Path("data/test_outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "test_thumbnail_with_text.jpg"

    # ========================================
    # Step 1: キャッチコピー生成
    # ========================================
    print("\n[Step 1] AIでキャッチコピー生成中...")

    copywriter = ThumbnailCopywriter()
    thumbnail_copy = await copywriter.generate_thumbnail_copy(
        person_name=person_name,
        topic=topic,
        quote=quote,
    )

    print(f"  メインコピー: {thumbnail_copy['main_copy']}")
    print(f"  サブコピー: {thumbnail_copy['sub_copy']}")
    print(f"  キーワード: {thumbnail_copy.get('keywords', [])}")

    # ========================================
    # Step 2: サムネイル生成（nanobanana pro）
    # ========================================
    print("\n[Step 2] nanobanana proでサムネイル生成中...")
    print(f"  モデル: {settings.nanobanana_pro_model}")

    generator = ThumbnailGenerator()
    result = await generator.generate_thumbnail(
        person_name=person_name,
        topic=topic,
        output_path=output_path,
        style="dramatic",
        quote=quote,
        thumbnail_copy=thumbnail_copy,
    )

    print(f"\n[OK] サムネイル生成完了!")
    print(f"  保存先: {result}")

    if result.exists():
        file_size = result.stat().st_size / 1024
        print(f"  ファイルサイズ: {file_size:.1f} KB")

    print("\n" + "=" * 60)
    print("[INFO] data/test_outputs/test_thumbnail_with_text.jpg を確認してください")
    print("=" * 60)


if __name__ == "__main__":
    # APIキー確認
    if not settings.kieai_api_key and not settings.nanobanana_api_key:
        print("[ERROR] KIEAI_API_KEY が設定されていません")
        exit(1)

    if not settings.gemini_api_key:
        print("[WARN] GEMINI_API_KEY が設定されていません（フォールバック使用）")

    asyncio.run(test_full_thumbnail_flow())
