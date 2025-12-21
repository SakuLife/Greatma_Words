"""
Integration test script for YouTube, Google Drive, Google Sheets, and Discord.
Tests each service individually to verify setup.
"""

import asyncio
from pathlib import Path

from app.config import settings
from app.services.discord_notifier import DiscordNotifier
from app.services.drive_manager import DriveManager
from app.services.sheets_manager import SheetsManager
from app.services.youtube_uploader import YouTubeUploader
from app.utils.logger import logger


async def test_discord() -> bool:
    """Test Discord webhook connection."""
    print("\n" + "=" * 60)
    print("Testing Discord Webhook...")
    print("=" * 60)

    if not settings.discord_webhook_url:
        print("❌ Discord webhook URL not configured in .env")
        return False

    try:
        notifier = DiscordNotifier()
        success = await notifier.send_message(
            content="✅ Discord連携テスト成功！\n\nGreatMan Words Generatorからの通知です。",
            title="🎉 接続確認",
            color=0x00FF00,  # Green
        )

        if success:
            print("✅ Discord notification sent successfully!")
            print(f"   Check your Discord channel for the message.")
            return True
        else:
            print("❌ Failed to send Discord notification")
            return False

    except Exception as e:
        print(f"❌ Discord test failed: {e}")
        return False


async def test_google_drive() -> bool:
    """Test Google Drive upload."""
    print("\n" + "=" * 60)
    print("Testing Google Drive API...")
    print("=" * 60)

    if not settings.google_drive_folder_id:
        print("❌ Google Drive folder ID not configured in .env")
        return False

    try:
        manager = DriveManager()

        # Authenticate
        print("🔐 Authenticating with Google Drive...")
        await manager.authenticate()
        print("✅ Authentication successful!")

        # Create test file
        test_file = Path("test_upload.txt")
        test_file.write_text(
            "This is a test file from GreatMan Words Generator.\n"
            "If you see this, the Google Drive integration is working!"
        )

        # Upload
        print("📤 Uploading test file...")
        result = await manager.upload_file(
            test_file,
            file_name="GreatMan_Words_Test.txt",
        )

        print("✅ File uploaded successfully!")
        print(f"   File ID: {result['id']}")
        print(f"   URL: {result['url']}")
        print(f"   Size: {result['size']} bytes")

        # Clean up
        test_file.unlink()

        return True

    except Exception as e:
        print(f"❌ Google Drive test failed: {e}")
        if Path("test_upload.txt").exists():
            Path("test_upload.txt").unlink()
        return False


async def test_google_sheets() -> bool:
    """Test Google Sheets logging."""
    print("\n" + "=" * 60)
    print("Testing Google Sheets API...")
    print("=" * 60)

    if not settings.google_sheets_id:
        print("❌ Google Sheets ID not configured in .env")
        return False

    try:
        manager = SheetsManager()

        # Authenticate
        print("🔐 Authenticating with Google Sheets...")
        await manager.authenticate()
        print("✅ Authentication successful!")

        # Log test entry
        print("📝 Writing test log entry...")
        success = await manager.log_video_production(
            person_name="テスト太郎",
            theme="統合テスト",
            video_duration=120.0,  # 2 minutes
            generation_time=60.0,  # 1 minute
            youtube_url="https://youtube.com/test",
            drive_url="https://drive.google.com/test",
            project_path="./test/project",
        )

        if success:
            print("✅ Test log entry written successfully!")
            print(f"   Check your Google Sheet:")
            print(
                f"   https://docs.google.com/spreadsheets/d/{settings.google_sheets_id}"
            )
            return True
        else:
            print("❌ Failed to write test log entry")
            return False

    except Exception as e:
        print(f"❌ Google Sheets test failed: {e}")
        return False


async def test_youtube() -> bool:
    """Test YouTube API authentication (no upload)."""
    print("\n" + "=" * 60)
    print("Testing YouTube API Authentication...")
    print("=" * 60)

    if not settings.youtube_client_secrets_file:
        print("❌ YouTube client secrets file not configured")
        return False

    try:
        uploader = YouTubeUploader()

        # Authenticate only
        print("🔐 Authenticating with YouTube...")
        await uploader.authenticate()
        print("✅ YouTube authentication successful!")
        print("   (No video uploaded - this is just an auth test)")

        return True

    except Exception as e:
        print(f"❌ YouTube test failed: {e}")
        return False


async def test_all_integrations():
    """Run all integration tests."""
    print("\n" + "🚀" * 30)
    print("GreatMan Words Generator - Integration Tests")
    print("🚀" * 30)

    results = {}

    # Test Discord
    results["Discord"] = await test_discord()
    await asyncio.sleep(1)

    # Test Google Drive
    results["Google Drive"] = await test_google_drive()
    await asyncio.sleep(1)

    # Test Google Sheets
    results["Google Sheets"] = await test_google_sheets()
    await asyncio.sleep(1)

    # Test YouTube
    results["YouTube"] = await test_youtube()

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for service, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{service:20s}: {status}")

    all_passed = all(results.values())

    print("=" * 60)

    if all_passed:
        print("\n🎉 すべてのテストが成功しました！")
        print("   すべての連携が正しく設定されています。")
    else:
        print("\n⚠️  一部のテストが失敗しました。")
        print("   失敗したサービスの設定を確認してください。")
        print("   詳細は docs/integration-setup.md を参照してください。")

    return all_passed


if __name__ == "__main__":
    try:
        asyncio.run(test_all_integrations())
    except KeyboardInterrupt:
        print("\n\n⚠️  テストが中断されました")
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        print(f"\n❌ テスト実行エラー: {e}")
