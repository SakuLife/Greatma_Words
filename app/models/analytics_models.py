"""
包括的チャンネル分析用データモデル。
YouTube Analytics API v2 / Data API v3から取得したデータを構造化する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


# ==========================================
# トラフィックソース分析
# ==========================================

@dataclass
class TrafficSourceData:
    """トラフィックソース別の視聴データ"""

    source_type: str  # SUGGESTED, SEARCH, EXTERNAL, NOTIFICATION, etc.
    views: int
    watch_time_minutes: float  # 総再生時間（分）
    percentage: float = 0.0  # 全体に占める割合（%）


# ==========================================
# デモグラフィック分析
# ==========================================

@dataclass
class DemographicData:
    """年齢・性別別の視聴者データ"""

    age_group: str  # age13-17, age18-24, age25-34, age35-44, age45-54, age55-64, age65-
    gender: str  # male, female, user_specified
    views: int
    percentage: float = 0.0


@dataclass
class DemographicSummary:
    """デモグラフィックの集約サマリー"""

    details: list[DemographicData] = field(default_factory=list)

    @property
    def top_age_group(self) -> str:
        """最も多い年齢層"""
        if not self.details:
            return "不明"
        age_views: dict[str, int] = {}
        for d in self.details:
            age_views[d.age_group] = age_views.get(d.age_group, 0) + d.views
        return max(age_views, key=age_views.get) if age_views else "不明"

    @property
    def gender_ratio(self) -> dict[str, float]:
        """性別比率"""
        total = sum(d.views for d in self.details)
        if total == 0:
            return {}
        gender_views: dict[str, int] = {}
        for d in self.details:
            gender_views[d.gender] = gender_views.get(d.gender, 0) + d.views
        return {g: v / total * 100 for g, v in gender_views.items()}


# ==========================================
# デバイス分析
# ==========================================

@dataclass
class DeviceData:
    """デバイス別の視聴データ"""

    device_type: str  # MOBILE, DESKTOP, TV, TABLET, GAME_CONSOLE, etc.
    views: int
    watch_time_minutes: float
    percentage: float = 0.0


# ==========================================
# 曜日別パフォーマンス
# ==========================================

@dataclass
class DayOfWeekPerformance:
    """曜日別のパフォーマンスデータ"""

    day_of_week: int  # 0=月曜, 6=日曜
    day_name: str  # 月, 火, 水, ...
    avg_views: float
    avg_watch_time_minutes: float
    total_uploads: int  # この曜日のアップロード数
    avg_initial_views_48h: float = 0.0  # 初動48時間の平均再生数


# ==========================================
# 動画ごとの登録者影響
# ==========================================

@dataclass
class VideoSubscriberImpact:
    """動画ごとの登録者獲得・離脱データ"""

    video_id: str
    title: str
    subscribers_gained: int
    subscribers_lost: int
    views: int
    estimated_minutes_watched: float = 0.0

    @property
    def net_subscribers(self) -> int:
        return self.subscribers_gained - self.subscribers_lost

    @property
    def subscriber_per_view(self) -> float:
        """1再生あたりの登録者獲得率"""
        if self.views == 0:
            return 0.0
        return self.subscribers_gained / self.views


# ==========================================
# アップロード時間分析
# ==========================================

@dataclass
class UploadTimeAnalysis:
    """アップロード時間と初動パフォーマンスの相関分析結果"""

    best_day_of_week: int  # 0=月曜, 6=日曜
    best_day_name: str
    best_hour_jst: int  # JST時間 (0-23)
    confidence: float  # 信頼度 (0-1, サンプル数ベース)
    day_performances: list[DayOfWeekPerformance] = field(default_factory=list)
    recommended_publish_time: str = ""  # "水曜日 17:00 JST" のような形式

    @property
    def publish_at_description(self) -> str:
        """推奨公開時間の説明"""
        if self.recommended_publish_time:
            return self.recommended_publish_time
        return f"{self.best_day_name}曜日 {self.best_hour_jst}:00 JST"


# ==========================================
# 競合分析
# ==========================================

@dataclass
class CompetitorVideo:
    """競合の動画データ"""

    video_id: str
    title: str
    channel_title: str
    channel_id: str
    view_count: int
    like_count: int
    published_at: str
    duration: str
    tags: list[str] = field(default_factory=list)
    description: str = ""

    @property
    def engagement_rate(self) -> float:
        if self.view_count == 0:
            return 0.0
        return (self.like_count / self.view_count) * 100


@dataclass
class CompetitorAnalysis:
    """競合調査の統合結果"""

    search_queries: list[str] = field(default_factory=list)
    videos: list[CompetitorVideo] = field(default_factory=list)
    trending_persons: list[dict] = field(default_factory=list)  # [{person, count, avg_views}]
    trending_topics: list[dict] = field(default_factory=list)  # [{topic, count, avg_views}]
    gap_opportunities: list[dict] = field(default_factory=list)  # [{person, reason, estimated_demand}]
    analyzed_at: str = ""

    @property
    def total_videos_analyzed(self) -> int:
        return len(self.videos)


# ==========================================
# チャンネル包括分析（統合結果）
# ==========================================

@dataclass
class ChannelDeepAnalysis:
    """全分析結果の統合データ"""

    # 基本情報
    channel_id: str = ""
    channel_title: str = ""
    analysis_date: str = ""
    analysis_period_days: int = 90

    # チャンネル基本統計
    subscriber_count: int = 0
    total_views: int = 0
    total_videos: int = 0

    # 詳細分析データ
    traffic_sources: list[TrafficSourceData] = field(default_factory=list)
    demographics: DemographicSummary = field(default_factory=DemographicSummary)
    devices: list[DeviceData] = field(default_factory=list)
    subscriber_impact: list[VideoSubscriberImpact] = field(default_factory=list)
    upload_time_analysis: UploadTimeAnalysis | None = None

    # 競合分析（Phase 2で追加）
    competitor_analysis: CompetitorAnalysis | None = None

    @property
    def top_traffic_source(self) -> str:
        """最大のトラフィックソース"""
        if not self.traffic_sources:
            return "不明"
        return max(self.traffic_sources, key=lambda x: x.views).source_type

    @property
    def top_subscriber_videos(self) -> list[VideoSubscriberImpact]:
        """登録者獲得数が多い動画トップ10"""
        return sorted(
            self.subscriber_impact,
            key=lambda x: x.subscribers_gained,
            reverse=True,
        )[:10]

    @property
    def primary_device(self) -> str:
        """主要デバイス"""
        if not self.devices:
            return "不明"
        return max(self.devices, key=lambda x: x.views).device_type
