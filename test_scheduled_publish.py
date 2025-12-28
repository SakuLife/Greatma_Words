"""Test scheduled publishing functionality."""

from datetime import datetime, timedelta, timezone

from app.services.video_workflow import calculate_next_publish_time
from app.utils.logger import logger


def test_calculate_next_publish_time():
    """Test the calculate_next_publish_time function."""
    logger.info("=" * 60)
    logger.info("Testing Scheduled Publish Time Calculation")
    logger.info("=" * 60)

    # JST is UTC+9
    JST = timezone(timedelta(hours=9))

    # Get current time
    now_utc = datetime.now(timezone.utc)
    now_jst = now_utc.astimezone(JST)

    logger.info(f"\nCurrent time:")
    logger.info(f"  UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"  JST: {now_jst.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Calculate next 18:00 JST publish time
    logger.info(f"\nCalculating next 18:00 JST publish time...")
    next_publish = calculate_next_publish_time(target_hour=18)

    # Convert to JST for display
    next_publish_jst = next_publish.astimezone(JST)

    logger.info(f"\n✅ Next publish time:")
    logger.info(f"  UTC: {next_publish.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"  JST: {next_publish_jst.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Verify it's in the future
    if next_publish > now_utc:
        logger.info(f"\n✅ Publish time is in the future")
        time_diff = next_publish - now_utc
        hours = time_diff.total_seconds() / 3600
        logger.info(f"   Time until publish: {hours:.1f} hours")
    else:
        logger.error(f"\n❌ ERROR: Publish time is in the past!")
        return False

    # Verify it's at 18:00 JST (09:00 UTC)
    if next_publish_jst.hour == 18:
        logger.info(f"✅ Publish time is at 18:00 JST")
    else:
        logger.error(f"❌ ERROR: Publish time is NOT at 18:00 JST (got {next_publish_jst.hour}:00)")
        return False

    # Verify it's 09:00 UTC
    if next_publish.hour == 9:
        logger.info(f"✅ Publish time is at 09:00 UTC")
    else:
        logger.error(f"❌ ERROR: Publish time is NOT at 09:00 UTC (got {next_publish.hour}:00)")
        return False

    # Test ISO 8601 format for YouTube API
    publish_iso = next_publish.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    logger.info(f"\nYouTube API format (ISO 8601):")
    logger.info(f"  {publish_iso}")

    logger.info(f"\n{'=' * 60}")
    logger.info("✅ All tests passed!")
    logger.info(f"{'=' * 60}")

    return True


if __name__ == "__main__":
    success = test_calculate_next_publish_time()
    if not success:
        exit(1)
