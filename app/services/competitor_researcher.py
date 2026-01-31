"""
競合・ニッチ調査サービス。
YouTube Data API v3のsearchを使い、同ジャンルの人気動画・人物・トピックを分析する。
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta

from app.models.analytics_models import CompetitorAnalysis, CompetitorVideo
from app.services.youtube_analytics import YouTubeAnalytics
from app.utils.logger import logger

# ニッチ検索クエリ（ローテーション用）
SEARCH_QUERIES = [
    "偉人 哲学 解説",
    "名言 人生 ビジネス",
    "自己啓発 成功者 教訓",
    "経営者 思考法 ビジネス",
    "偉人 名言 まとめ",
    "歴史 偉人 エピソード",
]


class CompetitorResearcher:
    """競合チャンネル・動画の調査と分析"""

    def __init__(self):
        self.analytics = YouTubeAnalytics()

    async def research_niche(
        self,
        max_queries: int = 3,
        own_channel_id: str | None = None,
        own_person_names: list[str] | None = None,
    ) -> CompetitorAnalysis:
        """
        ニッチ市場の競合調査を実行

        Args:
            max_queries: 検索クエリ数（APIクォータ節約）
            own_channel_id: 自チャンネルID（除外用）
            own_person_names: 自チャンネルで扱った人物名リスト

        Returns:
            CompetitorAnalysis 調査結果
        """
        logger.info("=" * 60)
        logger.info("競合・ニッチ調査開始")
        logger.info("=" * 60)

        await self.analytics.authenticate()

        # 自チャンネルIDを取得（除外用）
        if not own_channel_id:
            try:
                own_channel_id = await self.analytics.get_my_channel_id()
            except Exception:
                own_channel_id = None

        # 自チャンネルの人物リストを取得
        if own_person_names is None:
            own_person_names = await self._get_own_person_names()

        # 3ヶ月以内の動画に限定
        published_after = (datetime.now() - timedelta(days=90)).strftime(
            "%Y-%m-%dT00:00:00Z"
        )

        # クエリをローテーション
        queries_to_use = SEARCH_QUERIES[:max_queries]
        all_videos: list[CompetitorVideo] = []

        for query in queries_to_use:
            try:
                videos = await self.analytics.search_niche_videos(
                    query=query,
                    max_results=25,
                    order="viewCount",
                    published_after=published_after,
                )
                # 自チャンネルの動画を除外
                if own_channel_id:
                    videos = [v for v in videos if v.channel_id != own_channel_id]
                all_videos.extend(videos)
            except Exception as e:
                logger.warning(f"検索失敗 ('{query}'): {e}")

        logger.info(f"競合動画取得: 合計{len(all_videos)}件")

        # 重複除去（video_idベース）
        seen_ids: set[str] = set()
        unique_videos: list[CompetitorVideo] = []
        for v in all_videos:
            if v.video_id not in seen_ids:
                seen_ids.add(v.video_id)
                unique_videos.append(v)

        logger.info(f"重複除去後: {len(unique_videos)}件")

        # 分析
        trending_persons = self._extract_trending_persons(unique_videos)
        trending_topics = self._extract_trending_topics(unique_videos)
        gap_opportunities = self._identify_gaps(
            trending_persons, own_person_names or []
        )

        result = CompetitorAnalysis(
            search_queries=queries_to_use,
            videos=unique_videos,
            trending_persons=trending_persons,
            trending_topics=trending_topics,
            gap_opportunities=gap_opportunities,
            analyzed_at=datetime.now().strftime("%Y-%m-%d"),
        )

        logger.info(f"競合で人気の人物: {len(trending_persons)}人")
        logger.info(f"ギャップ機会: {len(gap_opportunities)}件")

        return result

    def _extract_trending_persons(
        self, videos: list[CompetitorVideo]
    ) -> list[dict]:
        """
        競合動画のタイトルから人気の人物を抽出

        Args:
            videos: 競合動画リスト

        Returns:
            人物ごとの出現回数と平均再生数
        """
        person_data: dict[str, list[int]] = {}

        for video in videos:
            persons = self._extract_person_from_title(video.title)
            for person in persons:
                if person not in person_data:
                    person_data[person] = []
                person_data[person].append(video.view_count)

        results = []
        for person, views_list in person_data.items():
            if len(views_list) >= 1:  # 1回以上出現
                results.append({
                    "person": person,
                    "count": len(views_list),
                    "avg_views": sum(views_list) / len(views_list),
                    "total_views": sum(views_list),
                })

        # 出現回数 × 平均再生数でソート
        results.sort(key=lambda x: x["count"] * x["avg_views"], reverse=True)

        for r in results[:10]:
            logger.info(
                f"  競合人物: {r['person']} - {r['count']}本, "
                f"平均{r['avg_views']:,.0f}再生"
            )

        return results[:20]

    def _extract_trending_topics(
        self, videos: list[CompetitorVideo]
    ) -> list[dict]:
        """
        競合動画のタイトルからトレンドトピックを抽出

        Args:
            videos: 競合動画リスト

        Returns:
            トピックごとの出現回数と平均再生数
        """
        topic_keywords = [
            "哲学", "名言", "思考", "戦略", "成功", "リーダーシップ",
            "経営", "人生", "ビジネス", "教訓", "投資", "マネジメント",
            "自己啓発", "モチベーション", "習慣", "心理学", "歴史",
            "AI", "時代", "未来", "天才", "伝説", "革命",
        ]

        topic_data: dict[str, list[int]] = {}

        for video in videos:
            title = video.title + " " + video.description[:100]
            for keyword in topic_keywords:
                if keyword in title:
                    if keyword not in topic_data:
                        topic_data[keyword] = []
                    topic_data[keyword].append(video.view_count)

        results = []
        for topic, views_list in topic_data.items():
            results.append({
                "topic": topic,
                "count": len(views_list),
                "avg_views": sum(views_list) / len(views_list) if views_list else 0,
            })

        results.sort(key=lambda x: x["count"], reverse=True)
        return results[:15]

    def _identify_gaps(
        self,
        competitor_persons: list[dict],
        own_person_names: list[str],
    ) -> list[dict]:
        """
        競合で人気だが自チャンネルでカバーしていない人物を特定

        Args:
            competitor_persons: 競合で人気の人物リスト
            own_person_names: 自チャンネルで扱った人物名リスト

        Returns:
            ギャップ機会のリスト
        """
        own_set = set(own_person_names)
        gaps = []

        for person_data in competitor_persons:
            person = person_data["person"]
            # 自チャンネルで扱っていない（部分一致でチェック）
            is_covered = any(
                own_name in person or person in own_name
                for own_name in own_set
            )

            if not is_covered and person_data["count"] >= 2:
                demand = "高" if person_data["avg_views"] > 10000 else "中"
                gaps.append({
                    "person": person,
                    "reason": f"競合{person_data['count']}本, 平均{person_data['avg_views']:,.0f}再生",
                    "estimated_demand": demand,
                    "competitor_count": person_data["count"],
                    "competitor_avg_views": person_data["avg_views"],
                })

        gaps.sort(key=lambda x: x.get("competitor_avg_views", 0), reverse=True)
        return gaps[:10]

    @staticmethod
    def _extract_person_from_title(title: str) -> list[str]:
        """
        タイトルから人物名を抽出する

        Args:
            title: 動画タイトル

        Returns:
            抽出された人物名リスト
        """
        persons = []

        # パターン1: 「〇〇の」で始まるタイトル
        match = re.match(r"^(.+?)の(?:哲学|名言|教え|思考|言葉|成功|戦略)", title)
        if match:
            persons.append(match.group(1).strip())

        # パターン2: 「・」で区切られたタイトルの先頭
        if "・" in title:
            first_part = title.split("・")[0].strip()
            # 短すぎるものはスキップ
            if 2 <= len(first_part) <= 15:
                persons.append(first_part)

        # パターン3: 【】内の人物名
        brackets = re.findall(r"【(.+?)】", title)
        for b in brackets:
            if 2 <= len(b) <= 15 and not any(c in b for c in ["解説", "まとめ", "名言"]):
                persons.append(b)

        # パターン4: カタカナの人名（3文字以上）
        katakana_names = re.findall(
            r"[ァ-ヴー]{2,}[・][ァ-ヴー]{2,}", title
        )
        persons.extend(katakana_names)

        # 重複除去
        seen: set[str] = set()
        unique: list[str] = []
        for p in persons:
            if p not in seen:
                seen.add(p)
                unique.append(p)

        return unique

    async def _get_own_person_names(self) -> list[str]:
        """自チャンネルの動画から扱った人物名を取得"""
        try:
            channel_id = await self.analytics.get_my_channel_id()
            videos = await self.analytics.get_all_videos(channel_id, max_results=100)

            persons = []
            for v in videos:
                extracted = self._extract_person_from_title(v.title)
                persons.extend(extracted)

            unique_persons = list(set(persons))
            logger.info(f"自チャンネルの人物リスト: {len(unique_persons)}人")
            return unique_persons

        except Exception as e:
            logger.warning(f"自チャンネル人物リスト取得失敗: {e}")
            return []

    def format_for_llm(self, analysis: CompetitorAnalysis) -> str:
        """
        競合分析結果をLLMプロンプト用にフォーマット

        Args:
            analysis: 競合分析結果

        Returns:
            LLM向けフォーマット済みテキスト
        """
        sections = []
        sections.append("# 競合・ニッチ調査レポート")
        sections.append(f"調査日: {analysis.analyzed_at}")
        sections.append(f"検索クエリ: {', '.join(analysis.search_queries)}")
        sections.append(f"分析動画数: {analysis.total_videos_analyzed}件")

        if analysis.trending_persons:
            sections.append("\n## 競合で人気の人物")
            for p in analysis.trending_persons[:10]:
                sections.append(
                    f"- {p['person']}: {p['count']}本, "
                    f"平均{p['avg_views']:,.0f}再生"
                )

        if analysis.trending_topics:
            sections.append("\n## トレンドトピック")
            for t in analysis.trending_topics[:10]:
                sections.append(
                    f"- {t['topic']}: {t['count']}本, "
                    f"平均{t['avg_views']:,.0f}再生"
                )

        if analysis.gap_opportunities:
            sections.append("\n## ギャップ機会（自チャンネル未カバー×競合で人気）")
            for g in analysis.gap_opportunities:
                sections.append(
                    f"- {g['person']}: {g['reason']} "
                    f"(推定需要: {g['estimated_demand']})"
                )

        return "\n".join(sections)
