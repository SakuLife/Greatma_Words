"""
サムネイルA/Bテスト管理サービス

動画のサムネイルを2パターン生成し、定期的に切り替えて
CTR（クリック率）を比較し、最適なサムネイルを自動選択する
"""

import json
import tempfile
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.drive_manager import DriveManager
from app.services.sheets_manager import SheetsManager
from app.services.thumbnail_copywriter import ThumbnailCopywriter
from app.services.thumbnail_generator import ThumbnailGenerator
from app.services.youtube_analytics import YouTubeAnalytics
from app.services.youtube_uploader import YouTubeUploader
from app.utils.logger import logger


class ABTestStatus(str, Enum):
    """A/Bテストのステータス"""

    VARIANT_A = "variant_a"  # バリアントA表示中
    VARIANT_B = "variant_b"  # バリアントB表示中
    COMPLETED = "completed"  # テスト完了（勝者決定済み）


class ThumbnailABTestManager:
    """サムネイルA/Bテストを管理"""

    def __init__(self):
        """Initialize A/B test manager."""
        self.sheets = SheetsManager()
        self.analytics = YouTubeAnalytics()
        self.uploader = YouTubeUploader()
        self.thumbnail_generator = ThumbnailGenerator()
        self.copywriter = ThumbnailCopywriter()
        self.drive = DriveManager()
        self._authenticated = False

    async def authenticate(self) -> None:
        """全サービスの認証"""
        if self._authenticated:
            return
        await self.analytics.authenticate()
        await self.uploader.authenticate()
        await self.sheets.authenticate()
        await self.drive.authenticate()
        self._authenticated = True

    async def register_new_test(
        self,
        video_id: str,
        video_title: str,
        person_name: str,
        topic: str,
        original_thumbnail_path: Path,
    ) -> dict:
        """
        新しいA/Bテストを登録

        オリジナルサムネイル = バリアントA
        異なるコピー・スタイルでバリアントBを生成

        Args:
            video_id: YouTube動画ID
            video_title: 動画タイトル
            person_name: 人物名
            topic: テーマ
            original_thumbnail_path: オリジナルサムネイルのパス

        Returns:
            テスト情報のdict
        """
        await self.authenticate()

        logger.info(f"A/Bテスト登録: {video_title} ({video_id})")

        # バリアントBのコピーを生成（異なるアプローチを明示）
        variant_b_copy = await self._generate_alternative_copy(
            person_name, topic
        )

        # バリアントBのサムネイルを生成
        variant_b_path = original_thumbnail_path.parent / "thumbnail_variant_b.jpg"
        await self.thumbnail_generator.generate_thumbnail(
            person_name=person_name,
            topic=topic,
            output_path=variant_b_path,
            style="dramatic",  # オリジナルとは異なるスタイル
            thumbnail_copy=variant_b_copy,
        )

        # バリアントBをGoogle Driveにアップロード（永続化）
        variant_b_drive_url = ""
        try:
            file_info = await self.drive.upload_file(
                variant_b_path,
                file_name=f"ab_test_{video_id}_variant_b.jpg",
            )
            variant_b_drive_url = file_info.get("url", "")
            logger.info(f"バリアントBをDriveにアップロード: {variant_b_drive_url}")
        except Exception as e:
            logger.warning(f"Drive アップロード失敗（ローカルパスで続行）: {e}")
            variant_b_drive_url = str(variant_b_path)

        now = datetime.now().strftime("%Y-%m-%d")
        test_data = {
            "video_id": video_id,
            "video_title": video_title,
            "status": ABTestStatus.VARIANT_A.value,
            "current_variant": "A",
            "variant_a_copy": topic,  # オリジナルのコピー情報
            "variant_a_style": "professional",
            "variant_a_impressions": 0,
            "variant_a_ctr": 0,
            "variant_a_days": 0,
            "variant_b_copy": variant_b_copy.get("main_copy", ""),
            "variant_b_style": "dramatic",
            "variant_b_drive_url": variant_b_drive_url,
            "variant_b_impressions": 0,
            "variant_b_ctr": 0,
            "variant_b_days": 0,
            "winner": "",
            "created_at": now,
            "last_rotated_at": now,
            "completed_at": "",
            "rotation_count": 0,
        }

        # Sheetsに保存
        existing = await self.sheets.read_ab_test_state()
        existing.append(test_data)
        await self._save_all_tests(existing)

        logger.info(f"A/Bテスト登録完了: {video_id}")
        return test_data

    async def run_weekly_cycle(self) -> dict:
        """
        週次のA/Bテストサイクルを実行

        1. アクティブなテストを読み込む
        2. CTRデータを取得して記録
        3. 十分なデータがあればテストを評価・完了
        4. ローテーション実行

        Returns:
            実行結果のサマリー
        """
        await self.authenticate()

        logger.info("=" * 60)
        logger.info("A/Bテスト週次サイクル開始")
        logger.info("=" * 60)

        tests = await self._load_active_tests()
        if not tests:
            logger.info("アクティブなA/Bテストなし")
            return {"active_tests": 0, "rotated": 0, "completed": 0}

        rotated = 0
        completed = 0
        end_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

        for test in tests:
            video_id = test.get("video_id", "")
            if not video_id:
                continue

            # CTRデータを取得
            last_rotated = test.get("last_rotated_at", test.get("created_at", ""))
            start_date = last_rotated

            try:
                ctr_data = await self.analytics.get_video_ctr(
                    video_id, start_date, end_date
                )
            except Exception as e:
                logger.warning(f"CTR取得失敗 ({video_id}): {e}")
                continue

            # 現在のバリアントのデータを更新
            if ctr_data:
                total_impressions = sum(c.impressions for c in ctr_data)
                avg_ctr = (
                    sum(c.ctr * c.impressions for c in ctr_data) / total_impressions
                    if total_impressions > 0
                    else 0
                )
                days = len(ctr_data)

                current = test.get("current_variant", "A")
                prefix = "variant_a" if current == "A" else "variant_b"
                test[f"{prefix}_impressions"] = int(test.get(f"{prefix}_impressions", 0)) + total_impressions
                # 加重平均CTRを計算
                old_imp = int(test.get(f"{prefix}_impressions", 0)) - total_impressions
                old_ctr = float(test.get(f"{prefix}_ctr", 0))
                if old_imp + total_impressions > 0:
                    test[f"{prefix}_ctr"] = round(
                        (old_ctr * old_imp + avg_ctr * total_impressions) / (old_imp + total_impressions),
                        2,
                    )
                test[f"{prefix}_days"] = int(test.get(f"{prefix}_days", 0)) + days

            # テスト評価（両方のデータが揃っている場合）
            a_imp = int(test.get("variant_a_impressions", 0))
            b_imp = int(test.get("variant_b_impressions", 0))
            rotation_count = int(test.get("rotation_count", 0))

            if (
                a_imp >= settings.ab_test_min_impressions
                and b_imp >= settings.ab_test_min_impressions
            ):
                # 両方十分なデータがある → 勝者判定
                a_ctr = float(test.get("variant_a_ctr", 0))
                b_ctr = float(test.get("variant_b_ctr", 0))
                diff = abs(a_ctr - b_ctr)

                if diff >= settings.ab_test_min_ctr_diff:
                    winner = "A" if a_ctr > b_ctr else "B"
                    await self._finalize_test(test, winner)
                    completed += 1
                    continue
                elif rotation_count >= settings.ab_test_max_rotations:
                    # 最大ローテーション数に達しても差がない → ベストで判定
                    winner = "A" if a_ctr >= b_ctr else "B"
                    await self._finalize_test(test, winner)
                    completed += 1
                    continue

            elif rotation_count >= settings.ab_test_max_rotations:
                # 最大ローテーション数超過 → ベストデータで判定
                a_ctr = float(test.get("variant_a_ctr", 0))
                b_ctr = float(test.get("variant_b_ctr", 0))
                winner = "A" if a_ctr >= b_ctr else "B"
                await self._finalize_test(test, winner)
                completed += 1
                continue

            # ローテーション実行
            try:
                await self._rotate_thumbnail(test)
                rotated += 1
            except Exception as e:
                logger.error(f"サムネイル切替失敗 ({video_id}): {e}")

        # 全テスト結果を保存
        all_tests = await self.sheets.read_ab_test_state()
        # アクティブなテストの更新結果をマージ
        test_map = {t.get("video_id"): t for t in tests}
        for i, t in enumerate(all_tests):
            vid = t.get("動画ID", t.get("video_id", ""))
            if vid in test_map:
                all_tests[i] = test_map[vid]
        await self._save_all_tests(all_tests)

        summary = {
            "active_tests": len(tests),
            "rotated": rotated,
            "completed": completed,
        }

        logger.info(f"A/Bテストサイクル完了: {summary}")
        return summary

    async def _generate_alternative_copy(
        self, person_name: str, topic: str
    ) -> dict:
        """バリアントB用の異なるキャッチコピーを生成"""
        try:
            # AIでコピー生成（同じ入力でも毎回異なるコピーが生成される）
            copy = await self.copywriter.generate_thumbnail_copy(
                person_name=person_name,
                topic=topic,
                script_summary=f"A/Bテスト用バリアントB: {topic}について新しい視点で",
            )
            return copy
        except Exception as e:
            logger.warning(f"バリアントBコピー生成失敗: {e}")
            return {
                "main_copy": "真実を話そう",
                "sub_copy": "誰も言わない",
                "keywords": [topic[:8]],
            }

    async def _rotate_thumbnail(self, test: dict) -> None:
        """サムネイルを切り替える"""
        video_id = test.get("video_id", "")
        current = test.get("current_variant", "A")
        new_variant = "B" if current == "A" else "A"

        if new_variant == "B":
            # バリアントBに切り替え → Driveからダウンロードしてアップロード
            drive_url = test.get("variant_b_drive_url", "")
            if drive_url and drive_url.startswith("http"):
                # DriveからダウンロードしてYouTubeに設定
                # Drive URLからファイルIDを抽出してダウンロード
                tmp_path = Path(tempfile.gettempdir()) / f"ab_test_{video_id}_b.jpg"
                try:
                    await self.drive.download_file(drive_url, tmp_path)
                    await self.uploader.set_thumbnail(video_id, tmp_path)
                except Exception:
                    # ダウンロード方式が使えない場合、ローカルパスを試行
                    local_path = Path(drive_url)
                    if local_path.exists():
                        await self.uploader.set_thumbnail(video_id, local_path)
                    else:
                        raise
            else:
                # ローカルパスの場合
                local_path = Path(drive_url)
                if local_path.exists():
                    await self.uploader.set_thumbnail(video_id, local_path)
                else:
                    logger.warning(f"バリアントBのファイルが見つかりません: {drive_url}")
                    return
        else:
            # バリアントAに戻す場合はYouTubeに元の画像がない
            # → 現状はバリアントBのまま継続（元画像の復元は困難）
            logger.info(f"バリアントAへの切り替えはスキップ（元画像復元不可）: {video_id}")

        test["current_variant"] = new_variant
        test["last_rotated_at"] = datetime.now().strftime("%Y-%m-%d")
        test["rotation_count"] = int(test.get("rotation_count", 0)) + 1

        logger.info(
            f"サムネイル切替: {video_id} → バリアント{new_variant} "
            f"(ローテーション{test['rotation_count']}回目)"
        )

    async def _finalize_test(self, test: dict, winner: str) -> None:
        """テストを完了し、勝者のサムネイルを設定"""
        video_id = test.get("video_id", "")

        test["status"] = ABTestStatus.COMPLETED.value
        test["winner"] = winner
        test["completed_at"] = datetime.now().strftime("%Y-%m-%d")

        a_ctr = float(test.get("variant_a_ctr", 0))
        b_ctr = float(test.get("variant_b_ctr", 0))

        logger.info(
            f"A/Bテスト完了: {video_id} → 勝者: バリアント{winner} "
            f"(A={a_ctr:.2f}% vs B={b_ctr:.2f}%)"
        )

        # 勝者が現在と違うバリアントならサムネイルを切り替え
        current = test.get("current_variant", "A")
        if winner != current:
            try:
                if winner == "B":
                    await self._rotate_thumbnail(test)
                # winner == "A" で current == "B" の場合、
                # 元のサムネイルの復元は困難なためログ警告のみ
                else:
                    logger.warning(
                        f"勝者はバリアントAだが現在Bを表示中。"
                        f"手動でオリジナルサムネイルを再設定してください: {video_id}"
                    )
            except Exception as e:
                logger.error(f"勝者サムネイル設定失敗 ({video_id}): {e}")

    async def _load_active_tests(self) -> list[dict]:
        """アクティブなテストを読み込む"""
        all_tests = await self.sheets.read_ab_test_state()
        active = []
        for t in all_tests:
            status = t.get("ステータス", t.get("status", ""))
            if status in (ABTestStatus.VARIANT_A.value, ABTestStatus.VARIANT_B.value):
                # Sheetsのカラム名からプログラム用キーに変換
                active.append(self._normalize_test_dict(t))
        return active

    def _normalize_test_dict(self, raw: dict) -> dict:
        """Sheetsの日本語カラム名をプログラム用キーに変換"""
        key_map = {
            "動画ID": "video_id",
            "動画タイトル": "video_title",
            "ステータス": "status",
            "現在のバリアント": "current_variant",
            "Aコピー": "variant_a_copy",
            "Aスタイル": "variant_a_style",
            "Aインプレッション": "variant_a_impressions",
            "A CTR(%)": "variant_a_ctr",
            "A表示日数": "variant_a_days",
            "Bコピー": "variant_b_copy",
            "Bスタイル": "variant_b_style",
            "Bインプレッション": "variant_b_impressions",
            "B CTR(%)": "variant_b_ctr",
            "B表示日数": "variant_b_days",
            "勝者": "winner",
            "作成日": "created_at",
            "最終切替日": "last_rotated_at",
            "完了日": "completed_at",
        }

        normalized = {}
        for k, v in raw.items():
            new_key = key_map.get(k, k)
            normalized[new_key] = v

        return normalized

    async def _save_all_tests(self, tests: list[dict]) -> None:
        """全テスト結果をSheetsに保存"""
        # プログラム用キーに統一してから保存
        formatted = []
        for t in tests:
            nt = self._normalize_test_dict(t)
            formatted.append(nt)
        await self.sheets.write_ab_test_results(formatted)
