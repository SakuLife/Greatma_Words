"""
Google Sheets認証トークン生成スクリプト

このスクリプトは以下を実行します：
1. ブラウザでGoogle OAuth認証フローを開始
2. 有効なrefresh tokenを含むトークンファイルを生成
3. GitHub Secretsに設定するためのbase64エンコード値を出力

使い方:
    python generate_sheets_token.py
"""

import asyncio
import base64
import os
from pathlib import Path

from app.services.sheets_manager import SheetsManager
from app.utils.logger import logger


async def generate_token():
    """Generate Google Sheets token for CI/CD use."""
    print("\n" + "=" * 70)
    print("Google Sheets Token Generator")
    print("=" * 70)
    print("\nThis script will:")
    print("1. Open browser for Google OAuth authentication")
    print("2. Generate sheets_token.json with valid refresh token")
    print("3. Output base64-encoded value for GitHub Secrets")
    print("\n" + "=" * 70)

    # Check client_secrets.json exists
    from app.config import settings

    if not os.path.exists(settings.google_client_secrets_file):
        print(f"\n❌ ERROR: {settings.google_client_secrets_file} not found")
        print("\nPlease follow these steps:")
        print("1. Go to Google Cloud Console")
        print("2. Create OAuth 2.0 Client (Desktop App)")
        print("3. Download JSON and save as client_secrets.json")
        print("\nSee docs/integration-setup.md for details")
        return

    token_file = "sheets_token.json"

    # Remove existing token to force re-authentication
    if os.path.exists(token_file):
        print(f"\n⚠️  Existing {token_file} found")
        confirm = input("Delete and regenerate? (y/n): ").strip().lower()
        if confirm == "y":
            os.remove(token_file)
            print(f"✅ Deleted {token_file}")
        else:
            print("Cancelled")
            return

    print("\n" + "-" * 70)
    print("Step 1: Authenticating with Google Sheets API")
    print("-" * 70)
    print("\nBrowser will open for OAuth consent...")
    print("Please:")
    print("  1. Select your Google account")
    print("  2. Click 'Allow' to grant permissions")
    print("  3. Close browser when you see 'authentication successful'")

    try:
        # Authenticate
        sheets = SheetsManager()
        await sheets.authenticate(token_file=token_file)

        print("\n✅ Authentication successful!")

        # Verify token file exists
        if not os.path.exists(token_file):
            print(f"\n❌ ERROR: {token_file} was not created")
            return

        # Read token file
        with open(token_file, "r") as f:
            token_content = f.read()

        print(f"\n✅ Token file created: {token_file}")
        print(f"   Size: {len(token_content)} bytes")

        # Test the token
        print("\n" + "-" * 70)
        print("Step 2: Testing token")
        print("-" * 70)

        try:
            stats = await sheets.get_video_stats()
            print(f"✅ Token works! Found {stats.get('total_videos', 0)} videos in Sheets")
        except Exception as e:
            print(f"⚠️  Warning: Token test failed: {e}")
            print("   But token file was created - it should still work")

        # Generate base64 encoded value for GitHub Secrets
        print("\n" + "-" * 70)
        print("Step 3: GitHub Secrets Setup")
        print("-" * 70)

        token_b64 = base64.b64encode(token_content.encode()).decode()

        print("\n✅ Base64-encoded token generated")
        print("\nTo update GitHub Secrets:")
        print("1. Go to: https://github.com/YOUR_USERNAME/YOUR_REPO/settings/secrets/actions")
        print("2. Click 'New repository secret' (or edit existing)")
        print("3. Name: GOOGLE_TOKEN_JSON_B64")
        print("4. Value: Copy the text below")
        print("\n" + "=" * 70)
        print("COPY THIS VALUE:")
        print("=" * 70)
        print(token_b64)
        print("=" * 70)

        # Save to file for reference
        output_file = "sheets_token_b64.txt"
        with open(output_file, "w") as f:
            f.write(token_b64)

        print(f"\n✅ Also saved to: {output_file}")
        print("\n⚠️  IMPORTANT: Do NOT commit this file to git!")
        print("   Add it to .gitignore if needed")

        print("\n" + "=" * 70)
        print("✅ SUCCESS - Token generation complete!")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Copy the base64 value above")
        print("2. Update GitHub Secret: GOOGLE_TOKEN_JSON_B64")
        print("3. Re-run the workflow")
        print("\n")

    except Exception as e:
        logger.error(f"Failed to generate token: {e}")
        import traceback

        traceback.print_exc()
        print("\n❌ FAILED")
        print(f"   Error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(generate_token())
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
    except Exception as e:
        print(f"\nError: {e}")
