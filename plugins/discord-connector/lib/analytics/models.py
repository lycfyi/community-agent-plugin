"""Data models for Discord Community Health Analytics.

Based on data-model.md specification.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


class TrendDirection(Enum):
    """Trend direction indicators."""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class TopicTrend(Enum):
    """Topic trend classification."""
    RISING = "rising"
    STABLE = "stable"
    DECLINING = "declining"
    NEW = "new"


class Sentiment(Enum):
    """Topic sentiment classification."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    NEUTRAL = "neutral"


class RecommendationPriority(Enum):
    """Recommendation priority levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationCategory(Enum):
    """Recommendation categories."""
    ENGAGEMENT = "engagement"
    ACTIVITY = "activity"
    CONTENT = "content"
    MODERATION = "moderation"


@dataclass
class ChannelActivity:
    """Activity breakdown for a single channel."""
    name: str
    messages: int
    percentage: float


@dataclass
class PeakTime:
    """Peak activity time."""
    hour: int
    messages: int


@dataclass
class PeakDay:
    """Peak activity day."""
    day: str
    messages: int


@dataclass
class ActivityMetrics:
    """Quantitative measurements of community activity."""
    total_messages: int
    messages_per_day_average: float
    messages_per_day_min: int
    messages_per_day_max: int
    active_channels: int
    inactive_channels: int
    channel_breakdown: List[ChannelActivity] = field(default_factory=list)
    peak_hours: List[PeakTime] = field(default_factory=list)
    peak_days: List[PeakDay] = field(default_factory=list)


@dataclass
class ReactionStat:
    """Reaction statistics."""
    emoji: str
    count: int


@dataclass
class EngagementMetrics:
    """Measurements of member engagement and interaction."""
    unique_authors: int
    daily_active_members_average: float
    daily_active_members_percentage: float
    messages_per_author_average: float
    messages_per_author_median: float
    reply_rate: float
    avg_response_time_hours: float
    total_reactions: int
    messages_with_reactions: int
    avg_reactions_per_message: float
    top_reactions: List[ReactionStat] = field(default_factory=list)


@dataclass
class TopContributor:
    """Top contributor profile."""
    author_id: str
    author_name: str
    message_count: int
    percentage: float
    engagement_received: int = 0


@dataclass
class ContributorDistribution:
    """Distribution of contributions."""
    top_1_pct: float
    top_10_pct: float
    top_50_pct: float


@dataclass
class ContributorMetrics:
    """Analysis of community contributors."""
    total_unique: int
    top_contributors: List[TopContributor] = field(default_factory=list)
    new_contributors_count: int = 0
    new_contributors_retention_rate: float = 0.0
    distribution: Optional[ContributorDistribution] = None


@dataclass
class TopicCluster:
    """A group of semantically related messages."""
    id: int
    label: str
    keywords: List[str]
    message_count: int
    percentage: float
    channels: List[str] = field(default_factory=list)
    top_contributors: List[TopContributor] = field(default_factory=list)
    sample_messages: List[str] = field(default_factory=list)
    sentiment: Sentiment = Sentiment.NEUTRAL
    trend: TopicTrend = TopicTrend.STABLE


@dataclass
class MetricChange:
    """Change in a metric between periods."""
    metric: str
    current: float
    previous: float
    change_pct: float
    direction: TrendDirection
    significant: bool  # True if abs(change_pct) > 20


@dataclass
class TopicChange:
    """Topic change information."""
    label: str
    previous_count: int = 0
    current_count: int = 0
    change_pct: float = 0.0


@dataclass
class TrendHighlight:
    """Trend highlight information."""
    type: str  # "spike", "decline", "emerging", etc.
    description: str
    impact: str  # "positive", "warning", "neutral"


@dataclass
class TrendData:
    """Historical comparison data for trend detection."""
    comparison_period_current: str
    comparison_period_previous: str
    metric_changes: List[MetricChange] = field(default_factory=list)
    emerging_topics: List[TopicChange] = field(default_factory=list)
    declining_topics: List[TopicChange] = field(default_factory=list)
    stable_topics: List[TopicChange] = field(default_factory=list)
    highlights: List[TrendHighlight] = field(default_factory=list)


@dataclass
class BenchmarkResult:
    """Comparison result for a single metric against benchmarks."""
    metric: str
    value: float
    threshold_healthy: float
    threshold_warning: float
    status: HealthStatus


@dataclass
class BenchmarkComparison:
    """Comparison against predefined health thresholds."""
    source: str  # "default" or "custom"
    comparisons: List[BenchmarkResult] = field(default_factory=list)
    overall_assessment: HealthStatus = HealthStatus.HEALTHY
    score: int = 0  # 0-100


@dataclass
class Recommendation:
    """Actionable suggestion based on analysis."""
    id: int
    priority: RecommendationPriority
    category: RecommendationCategory
    title: str
    description: str
    metric_reference: str
    current_value: float
    target_value: float
    actions: List[str] = field(default_factory=list)


@dataclass
class HealthScores:
    """Aggregate health scores."""
    overall: int  # 0-100
    activity: int
    engagement: int
    responsiveness: int
    diversity: int


@dataclass
class AnalysisPeriod:
    """Analysis period information."""
    start: str  # ISO date string
    end: str    # ISO date string
    days: int


@dataclass
class HealthReport:
    """The main output document containing all analysis results."""
    report_id: str
    server_id: str
    server_name: str
    generated_at: str  # ISO datetime string
    analysis_period: AnalysisPeriod
    message_count: int
    channel_count: int

    health_scores: HealthScores
    activity: ActivityMetrics
    engagement: EngagementMetrics
    contributors: ContributorMetrics

    topics: List[TopicCluster] = field(default_factory=list)
    trends: Optional[TrendData] = None
    benchmarks: Optional[BenchmarkComparison] = None
    recommendations: List[Recommendation] = field(default_factory=list)

    # Metadata for edge cases
    partial_report: bool = False
    partial_reason: Optional[str] = None
    inaccessible_channels: List[str] = field(default_factory=list)
