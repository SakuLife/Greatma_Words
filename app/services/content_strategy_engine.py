"""
コンテンツ戦略エンジン。
全分析データを統合し、LLMで次回動画の戦略を生成する。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import google.generativeai as genai

from app.config import settings
from app.models.analytics_models import ChannelDeepAnalysis, CompetitorAnalysis
from app.services.channel_deep_analyzer import ChannelDeepAnalyzer
from app.services.competitor_researcher import CompetitorResearcher
from app.services.dynamic_script_builder import (
    HOOK_STRATEGIES,
    STRUCTURE_TEMPLATES,
    DynamicScriptBuilder,
)
from app.services.sheets_manager import SheetsManager
from app.utils.logger import logger


class ContentStrategyEngine:
    """全データを統合してコンテンツ戦略を生成するエンジン"""

    def __init__(self):
        self.deep_analyzer = ChannelDeepAnalyzer()
        self.competitor_researcher = CompetitorResearcher()
        self.script_builder = DynamicScriptBuilder()
        self.sheets = SheetsManager() if settings.google_sheets_id else None
        self.gemini_enabled = False

        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.gemini_enabled = True

    async def generate_weekly_strategy(
        self, analysis_days: int = 90
    ) -> dict:
        """
        週次コンテンツ戦略を生成

        Args:
            analysis_days: 分析対象日数

        Returns:
            戦略データ辞書
        """
        logger.info("=" * 60)
        logger.info("コンテンツ戦略生成開始")
        logger.info("=" * 60)

        # 1. チャンネル包括分析
        logger.info("Step 1: チャンネル包括分析")
        channel_analysis = await self.deep_analyzer.run_full_analysis(days=analysis_days)

        # 2. 競合調査
        logger.info("Step 2: 競合調査")
        try:
            competitor_analysis = await self.competitor_researcher.research_niche(
                max_queries=3
            )
            channel_analysis.competitor_analysis = competitor_analysis
        except Exception as e:
            logger.warning(f"競合調査スキップ: {e}")
            competitor_analysis = None

        # 3. LLMで戦略生成
        logger.info("Step 3: LLMで戦略生成")
        strategy = await self._generate_strategy_with_llm(
            channel_analysis, competitor_analysis
        )

        # 4. 投稿スケジュール算出
        upload_schedule = self._calculate_upload_schedule(channel_analysis)
        strategy["upload_schedule"] = upload_schedule

        # 5. チャンネルヘルス
        strategy["channel_health"] = self._assess_channel_health(channel_analysis)

        # 6. 日付追加
        strategy["date"] = datetime.now().strftime("%Y-%m-%d")

        # 7. Sheets に書き込み
        await self._save_to_sheets(channel_analysis, competitor_analysis, strategy)

        logger.info("=" * 60)
        logger.info("コンテンツ戦略生成完了")
        logger.info("=" * 60)

        return strategy

    async def _generate_strategy_with_llm(
        self,
        channel_analysis: ChannelDeepAnalysis,
        competitor_analysis: CompetitorAnalysis | None,
    ) -> dict:
        """LLMを使って戦略を生成"""
        if not self.gemini_enabled:
            logger.warning("Gemini API未設定のため、デフォルト戦略を返します")
            return self._default_strategy()

        # 分析レポートを構築
        channel_report = self.deep_analyzer.format_for_llm(channel_analysis)
        competitor_report = ""
        if competitor_analysis:
            competitor_report = self.competitor_researcher.format_for_llm(
                competitor_analysis
            )

        # 利用可能なフック戦略と構成パターンの一覧
        hook_list = "\n".join(
            f"- {k}: {v['name']}（{v['description']}）"
            for k, v in HOOK_STRATEGIES.items()
        )
        structure_list = "\n".join(
            f"- {k}: {v['name']}（{v['description']}）"
            for k, v in STRUCTURE_TEMPLATES.items()
        )

        prompt = f"""あなたはYouTubeチャンネル「偉人たちが導く道しるべ」のコンテンツストラテジストです。
以下のデータ分析に基づいて、次回の動画戦略を提案してください。

{channel_report}

{competitor_report}

## 利用可能なフック戦略
{hook_list}

## 利用可能な構成パターン
{structure_list}

## 出力形式（JSON）
以下のJSON形式で3つの動画提案を出力してください:

```json
{{
  "next_video_suggestions": [
    {{
      "person": "人物名（カタカナ表記）",
      "topic": "具体的なテーマ",
      "hook_strategy": "フック戦略キー（question/contrarian/story/statistic/quote）",
      "structure": "構成パターンキー（three_pillars/problem_solution/chronological/debate/deep_dive）",
      "differentiation": "競合との差別化ポイント",
      "title_suggestion": "YouTube動画タイトル案（40文字以内）",
      "hashtags": "ハッシュタグ5-7個（#付き、スペース区切り）",
      "reason": "この提案の根拠（分析データを引用）"
    }}
  ]
}}
```

## 重要な指示
- 最近の動画で扱った人物は避けること（登録者獲得分析の動画を参照）
- 競合のギャップ機会を積極的に活用すること
- 視聴者のデモグラフィックに合ったテーマを選ぶこと
- 各提案は異なるフック戦略・構成パターンを使うこと
- トラフィックソースの傾向に合ったタイトルを提案すること
- JSONのみを出力してください"""

        try:
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.8,
                    "response_mime_type": "application/json",
                },
            )

            import json
            content = response.text.strip()
            # コードブロック除去
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            strategy = json.loads(content)
            logger.info(f"LLM戦略生成成功: {len(strategy.get('next_video_suggestions', []))}提案")
            return strategy

        except Exception as e:
            logger.error(f"LLM戦略生成失敗: {e}")
            return self._default_strategy()

    def _calculate_upload_schedule(
        self, analysis: ChannelDeepAnalysis
    ) -> dict:
        """最適な投稿スケジュールを算出"""
        if not analysis.upload_time_analysis:
            return {
                "best_day": "水曜日",
                "best_hour_jst": 17,
                "publish_at": "",
                "confidence": "低（データ不足）",
            }

        uta = analysis.upload_time_analysis
        day_names_full = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

        # 次の最適曜日を計算
        today = datetime.now()
        days_ahead = uta.best_day_of_week - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_date = today + timedelta(days=days_ahead)
        publish_at = next_date.replace(
            hour=uta.best_hour_jst, minute=0, second=0, microsecond=0
        )
        # JSTをUTCに変換 (-9h)
        publish_at_utc = publish_at - timedelta(hours=9)

        return {
            "best_day": day_names_full[uta.best_day_of_week],
            "best_hour_jst": uta.best_hour_jst,
            "publish_at": publish_at_utc.strftime("%Y-%m-%dT%H:%M:%S.0Z"),
            "publish_at_jst": publish_at.strftime("%Y-%m-%d %H:%M JST"),
            "confidence": f"{uta.confidence:.0%}",
        }

    def _assess_channel_health(
        self, analysis: ChannelDeepAnalysis
    ) -> dict:
        """チャンネルの健全性を評価"""
        health: dict = {}

        # トラフィックミックス
        if analysis.traffic_sources:
            health["traffic_mix"] = {
                ts.source_type: f"{ts.percentage}%"
                for ts in analysis.traffic_sources[:5]
            }

        # 主要デバイス
        health["primary_device"] = analysis.primary_device

        # 登録者獲得効率
        if analysis.subscriber_impact:
            total_gained = sum(v.subscribers_gained for v in analysis.subscriber_impact)
            total_views = sum(v.views for v in analysis.subscriber_impact)
            if total_views > 0:
                health["subscriber_conversion_rate"] = f"{total_gained / total_views * 100:.3f}%"

        return health

    def _default_strategy(self) -> dict:
        """LLMが使えない場合のデフォルト戦略"""
        return {
            "next_video_suggestions": [
                {
                    "person": "ピーター・ドラッカー",
                    "topic": "マネジメントの本質",
                    "hook_strategy": "question",
                    "structure": "three_pillars",
                    "differentiation": "データ不足のためデフォルト提案",
                    "title_suggestion": "ドラッカーが教える・マネジメントの3つの真実",
                    "hashtags": "#ドラッカー #マネジメント #経営哲学 #ビジネス #偉人の言葉",
                    "reason": "LLM戦略生成不可のためフォールバック",
                }
            ]
        }

    async def _save_to_sheets(
        self,
        channel_analysis: ChannelDeepAnalysis,
        competitor_analysis: CompetitorAnalysis | None,
        strategy: dict,
    ) -> None:
        """分析結果と戦略をSheetsに保存"""
        if not self.sheets:
            return

        try:
            await self.sheets.authenticate()

            # チャンネル詳細分析
            deep_data = {
                "analysis_date": channel_analysis.analysis_date,
                "analysis_period_days": channel_analysis.analysis_period_days,
                "subscriber_count": channel_analysis.subscriber_count,
                "total_views": channel_analysis.total_views,
                "total_videos": channel_analysis.total_videos,
                "top_traffic_source": channel_analysis.top_traffic_source,
                "traffic_sources": [
                    {"source_type": ts.source_type, "percentage": ts.percentage}
                    for ts in channel_analysis.traffic_sources[:5]
                ],
                "top_age_group": (
                    channel_analysis.demographics.top_age_group
                    if channel_analysis.demographics
                    else ""
                ),
                "gender_ratio": str(
                    channel_analysis.demographics.gender_ratio
                    if channel_analysis.demographics
                    else ""
                ),
                "primary_device": channel_analysis.primary_device,
                "devices": [
                    {"device_type": d.device_type, "percentage": d.percentage}
                    for d in channel_analysis.devices[:5]
                ],
                "top_subscriber_videos": [
                    {
                        "title": v.title,
                        "subscribers_gained": v.subscribers_gained,
                    }
                    for v in channel_analysis.top_subscriber_videos[:3]
                ],
                "recommended_publish_time": (
                    channel_analysis.upload_time_analysis.publish_at_description
                    if channel_analysis.upload_time_analysis
                    else ""
                ),
                "upload_time_confidence": (
                    f"{channel_analysis.upload_time_analysis.confidence:.0%}"
                    if channel_analysis.upload_time_analysis
                    else ""
                ),
            }
            await self.sheets.write_deep_analysis(deep_data)

            # 投稿時間分析
            if channel_analysis.upload_time_analysis:
                uta = channel_analysis.upload_time_analysis
                day_perfs = [
                    {
                        "day_name": dp.day_name,
                        "total_uploads": dp.total_uploads,
                        "avg_initial_views_48h": dp.avg_initial_views_48h,
                    }
                    for dp in uta.day_performances
                ]
                await self.sheets.write_upload_time_analysis(
                    day_perfs, uta.publish_at_description, uta.confidence
                )

            # 競合分析
            if competitor_analysis:
                comp_data = {
                    "analyzed_at": competitor_analysis.analyzed_at,
                    "search_queries": competitor_analysis.search_queries,
                    "videos": [
                        {
                            "title": v.title,
                            "channel_title": v.channel_title,
                            "view_count": v.view_count,
                            "like_count": v.like_count,
                            "engagement_rate": v.engagement_rate,
                        }
                        for v in competitor_analysis.videos[:20]
                    ],
                    "gap_opportunities": competitor_analysis.gap_opportunities,
                }
                await self.sheets.write_competitor_analysis(comp_data)

            # コンテンツ戦略
            await self.sheets.write_content_strategy(strategy)

            logger.info("全分析結果をSheetsに保存完了")

        except Exception as e:
            logger.error(f"Sheets保存に失敗: {e}")

    def generate_dynamic_hashtags(
        self,
        person_name: str,
        topic: str,
        competitor_tags: list[str] | None = None,
    ) -> list[str]:
        """
        動的にハッシュタグを生成

        Args:
            person_name: 人物名
            topic: テーマ
            competitor_tags: 競合で使われているタグ

        Returns:
            ハッシュタグリスト
        """
        tags = [
            f"#{person_name}",
            f"#{topic}",
            "#偉人の言葉",
        ]

        # トピック関連タグ
        topic_tag_map = {
            "経営": ["#経営哲学", "#ビジネス"],
            "哲学": ["#人生哲学", "#教養"],
            "投資": ["#投資哲学", "#マネー"],
            "リーダー": ["#リーダーシップ", "#マネジメント"],
            "AI": ["#AI時代", "#テクノロジー"],
            "成功": ["#成功法則", "#自己啓発"],
        }

        for keyword, keyword_tags in topic_tag_map.items():
            if keyword in topic or keyword in person_name:
                tags.extend(keyword_tags)

        # 競合タグから有用なものを追加
        if competitor_tags:
            for tag in competitor_tags[:3]:
                if tag not in tags and len(tag) < 20:
                    tags.append(tag if tag.startswith("#") else f"#{tag}")

        # 重複除去して7個以内に
        seen: set[str] = set()
        unique_tags: list[str] = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)

        return unique_tags[:7]
