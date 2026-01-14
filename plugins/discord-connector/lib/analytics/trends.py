"""Trend detection for Discord Community Health Analytics.

Implements week-over-week comparison and significant change detection.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .models import (
    ActivityMetrics,
    EngagementMetrics,
    MetricChange,
    TopicChange,
    TopicCluster,
    TrendData,
    TrendDirection,
    TrendHighlight,
)
from .parser import ParsedMessage
from .metrics import (
    calculate_activity_metrics,
    calculate_engagement_metrics,
)


# Significance threshold (20% change)
SIGNIFICANCE_THRESHOLD = 20.0

# Minimum days for trend analysis
MIN_DAYS_FOR_TRENDS = 14

# Default comparison period (7 days)
COMPARISON_PERIOD_DAYS = 7


def detect_trends(
    messages: List[ParsedMessage],
    analysis_start: datetime,
    analysis_end: datetime,
    current_topics: Optional[List[TopicCluster]] = None,
    comparison_days: int = COMPARISON_PERIOD_DAYS,
) -> Optional[TrendData]:
    """Detect trends by comparing current vs previous period.

    Args:
        messages: All parsed messages.
        analysis_start: Start of analysis period.
        analysis_end: End of analysis period.
        current_topics: Current topic clusters for comparison.
        comparison_days: Number of days in each comparison period.

    Returns:
        TrendData object, or None if insufficient data.
    """
    total_days = (analysis_end - analysis_start).days

    # Need at least 14 days for meaningful trends
    if total_days < MIN_DAYS_FOR_TRENDS:
        return None

    # Define current and previous periods
    current_end = analysis_end
    current_start = current_end - timedelta(days=comparison_days)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=comparison_days)

    # Filter messages by period
    current_messages = [
        m for m in messages
        if current_start <= m.timestamp <= current_end
    ]
    previous_messages = [
        m for m in messages
        if previous_start <= m.timestamp <= previous_end
    ]

    if not current_messages or not previous_messages:
        return None

    # Calculate metrics for each period
    current_activity = calculate_activity_metrics(
        current_messages, current_start, current_end
    )
    previous_activity = calculate_activity_metrics(
        previous_messages, previous_start, previous_end
    )

    current_engagement = calculate_engagement_metrics(
        current_messages, current_start, current_end
    )
    previous_engagement = calculate_engagement_metrics(
        previous_messages, previous_start, previous_end
    )

    # Calculate metric changes
    metric_changes = []

    # Activity metrics
    metric_changes.append(_create_metric_change(
        "message_volume",
        current_activity.total_messages,
        previous_activity.total_messages,
    ))
    metric_changes.append(_create_metric_change(
        "messages_per_day",
        current_activity.messages_per_day_average,
        previous_activity.messages_per_day_average,
    ))
    metric_changes.append(_create_metric_change(
        "active_channels",
        current_activity.active_channels,
        previous_activity.active_channels,
    ))

    # Engagement metrics
    metric_changes.append(_create_metric_change(
        "daily_active_members",
        current_engagement.daily_active_members_average,
        previous_engagement.daily_active_members_average,
    ))
    metric_changes.append(_create_metric_change(
        "unique_authors",
        current_engagement.unique_authors,
        previous_engagement.unique_authors,
    ))
    metric_changes.append(_create_metric_change(
        "reply_rate",
        current_engagement.reply_rate,
        previous_engagement.reply_rate,
    ))
    metric_changes.append(_create_metric_change(
        "avg_response_time",
        current_engagement.avg_response_time_hours,
        previous_engagement.avg_response_time_hours,
    ))
    metric_changes.append(_create_metric_change(
        "total_reactions",
        current_engagement.total_reactions,
        previous_engagement.total_reactions,
    ))

    # Filter out None changes (where previous was 0)
    metric_changes = [m for m in metric_changes if m is not None]

    # Detect topic changes if topics provided
    emerging_topics: List[TopicChange] = []
    declining_topics: List[TopicChange] = []
    stable_topics: List[TopicChange] = []

    if current_topics:
        # Extract keywords from previous period
        from .topics import cluster_messages_by_topic
        previous_topics = cluster_messages_by_topic(previous_messages)

        # Compare topic distributions
        current_topic_map = {t.label: t.message_count for t in current_topics}
        previous_topic_map = {t.label: t.message_count for t in previous_topics}

        # Find emerging (new or significantly increased)
        for label, count in current_topic_map.items():
            prev_count = previous_topic_map.get(label, 0)

            if prev_count == 0 and count >= 10:
                emerging_topics.append(TopicChange(
                    label=label,
                    previous_count=0,
                    current_count=count,
                    change_pct=100.0,
                ))
            elif prev_count > 0:
                change_pct = ((count - prev_count) / prev_count) * 100
                if change_pct > 50:
                    emerging_topics.append(TopicChange(
                        label=label,
                        previous_count=prev_count,
                        current_count=count,
                        change_pct=round(change_pct, 1),
                    ))
                elif change_pct < -50:
                    declining_topics.append(TopicChange(
                        label=label,
                        previous_count=prev_count,
                        current_count=count,
                        change_pct=round(change_pct, 1),
                    ))
                else:
                    stable_topics.append(TopicChange(
                        label=label,
                        previous_count=prev_count,
                        current_count=count,
                        change_pct=round(change_pct, 1),
                    ))

    # Generate highlights
    highlights = _generate_highlights(metric_changes)

    return TrendData(
        comparison_period_current=f"{current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}",
        comparison_period_previous=f"{previous_start.strftime('%Y-%m-%d')} to {previous_end.strftime('%Y-%m-%d')}",
        metric_changes=metric_changes,
        emerging_topics=emerging_topics,
        declining_topics=declining_topics,
        stable_topics=stable_topics[:5],  # Limit stable topics
        highlights=highlights,
    )


def _create_metric_change(
    metric: str,
    current: float,
    previous: float,
) -> Optional[MetricChange]:
    """Create a MetricChange object.

    Args:
        metric: Metric name.
        current: Current period value.
        previous: Previous period value.

    Returns:
        MetricChange object, or None if previous is 0.
    """
    if previous == 0:
        if current == 0:
            return None
        # Special case: went from 0 to something
        return MetricChange(
            metric=metric,
            current=current,
            previous=0,
            change_pct=100.0,
            direction=TrendDirection.UP,
            significant=True,
        )

    change_pct = ((current - previous) / previous) * 100

    # Special handling for response time (lower is better)
    if metric == "avg_response_time":
        if change_pct < 0:
            direction = TrendDirection.UP  # Improvement
        elif change_pct > 0:
            direction = TrendDirection.DOWN  # Decline
        else:
            direction = TrendDirection.STABLE
    else:
        if change_pct > 0:
            direction = TrendDirection.UP
        elif change_pct < 0:
            direction = TrendDirection.DOWN
        else:
            direction = TrendDirection.STABLE

    significant = abs(change_pct) >= SIGNIFICANCE_THRESHOLD

    return MetricChange(
        metric=metric,
        current=round(current, 1),
        previous=round(previous, 1),
        change_pct=round(change_pct, 1),
        direction=direction,
        significant=significant,
    )


def _generate_highlights(metric_changes: List[MetricChange]) -> List[TrendHighlight]:
    """Generate trend highlights from metric changes.

    Args:
        metric_changes: List of metric changes.

    Returns:
        List of TrendHighlight objects.
    """
    highlights: List[TrendHighlight] = []

    for change in metric_changes:
        if not change.significant:
            continue

        # Human-readable metric names
        metric_names = {
            "message_volume": "Message volume",
            "messages_per_day": "Daily messages",
            "active_channels": "Active channels",
            "daily_active_members": "Daily active members",
            "unique_authors": "Unique contributors",
            "reply_rate": "Reply rate",
            "avg_response_time": "Response time",
            "total_reactions": "Total reactions",
        }

        metric_name = metric_names.get(change.metric, change.metric)

        if change.direction == TrendDirection.UP:
            if change.metric == "avg_response_time":
                # Slower response time is negative
                highlights.append(TrendHighlight(
                    type="decline",
                    description=f"{metric_name} increased {change.change_pct:.0f}% (slower responses)",
                    impact="warning",
                ))
            else:
                highlights.append(TrendHighlight(
                    type="spike",
                    description=f"{metric_name} increased {change.change_pct:.0f}%",
                    impact="positive",
                ))
        elif change.direction == TrendDirection.DOWN:
            if change.metric == "avg_response_time":
                # Faster response time is positive
                highlights.append(TrendHighlight(
                    type="improvement",
                    description=f"{metric_name} decreased {abs(change.change_pct):.0f}% (faster responses)",
                    impact="positive",
                ))
            else:
                highlights.append(TrendHighlight(
                    type="decline",
                    description=f"{metric_name} decreased {abs(change.change_pct):.0f}%",
                    impact="warning",
                ))

    return highlights
