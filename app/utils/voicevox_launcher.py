"""
VoiceVox launcher utility.
Automatically starts VoiceVox if not running.
"""

import subprocess
import time
from pathlib import Path

import requests

from app.config import settings
from app.utils.logger import logger


class VoiceVoxLauncher:
    """Manages VoiceVox process lifecycle."""

    def __init__(self):
        """Initialize VoiceVox launcher."""
        # VoiceVoxのパスを探す
        self.voicevox_path = self._find_voicevox_executable()
        self.process = None

    def _find_voicevox_executable(self) -> Path | None:
        """Find VoiceVox executable in common locations."""
        # 親階層2つ上のApp/VOICEVOXを探す
        current_dir = Path(__file__).resolve()
        # greatman_words/app/utils/voicevox_launcher.py
        # → greatman_words/
        # → AutoSystem/PythonSystem/
        # → AutoSystem/
        # → D:/
        project_root = current_dir.parent.parent.parent
        possible_paths = [
            # 親階層2つ上のApp/VOICEVOX
            project_root.parent.parent / "App" / "VOICEVOX" / "VOICEVOX.exe",
            # D:/App/VOICEVOX/VOICEVOX.exe
            Path("D:/App/VOICEVOX/VOICEVOX.exe"),
            # その他の一般的な場所
            Path("C:/Program Files/VOICEVOX/VOICEVOX.exe"),
            Path("C:/Program Files (x86)/VOICEVOX/VOICEVOX.exe"),
        ]

        for path in possible_paths:
            if path.exists():
                logger.info(f"Found VoiceVox at: {path}")
                return path

        logger.warning("VoiceVox executable not found in common locations")
        return None

    def is_running(self) -> bool:
        """Check if VoiceVox is already running."""
        try:
            response = requests.get(
                f"{settings.voicevox_api_url}/version", timeout=2
            )
            return response.status_code == 200
        except Exception:
            return False

    def start(self, wait_timeout: int = 30) -> bool:
        """
        Start VoiceVox if not already running.

        Args:
            wait_timeout: Maximum time to wait for VoiceVox to start (seconds)

        Returns:
            True if VoiceVox is running, False otherwise
        """
        # 既に起動しているか確認
        if self.is_running():
            logger.info("VoiceVox is already running")
            return True

        # 実行ファイルが見つからない場合
        if not self.voicevox_path:
            logger.error(
                "VoiceVox executable not found. Please start VoiceVox manually."
            )
            return False

        logger.info(f"Starting VoiceVox from: {self.voicevox_path}")

        try:
            # VoiceVoxを起動（バックグラウンドで）
            self.process = subprocess.Popen(
                [str(self.voicevox_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )

            # VoiceVoxが起動するまで待機
            logger.info("Waiting for VoiceVox to start...")
            for i in range(wait_timeout):
                time.sleep(1)
                if self.is_running():
                    logger.info(f"VoiceVox started successfully (took {i+1} seconds)")
                    return True

            logger.warning(
                f"VoiceVox did not start within {wait_timeout} seconds"
            )
            return False

        except Exception as e:
            logger.error(f"Failed to start VoiceVox: {e}")
            return False

    def stop(self) -> None:
        """Stop VoiceVox if we started it."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                logger.info("VoiceVox stopped")
            except Exception as e:
                logger.warning(f"Error stopping VoiceVox: {e}")
                try:
                    self.process.kill()
                except Exception:
                    pass
            finally:
                self.process = None


# Global launcher instance
launcher = VoiceVoxLauncher()

