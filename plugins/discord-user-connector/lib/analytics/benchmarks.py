"""Benchmark comparison for Discord Community Health Analytics.

Compares metrics against predefined thresholds and supports
server-to-server comparison.
"""

from typing import Dict, List, Optional

from .models import (
    ActivityMetrics,
    BenchmarkComparison,
    BenchmarkResult,
    ContributorMetrics,
    EngagementMetrics,
    HealthReport,
    HealthStatus,
)


# Default benchmark thresholds
# Format: {metric: {healthy: threshold, warning: threshold}}
# For "lower is better" metrics, healthy < warning
DEFAULT_BENCHMARKS: Dict[str, Dict[str, float]] = {
    # Engagement metrics
    "daily_active_pct": {
        "healthy": 10.0,  # 10%+ is healthy
        "warning": 5.0,   # 5-10% is warning
        # <5% is critical
    },
    "response_rate": {
        "healthy": 30.0,  # 30%+ is healthy
        "warning": 15.0,  # 15-30% is warning
        # <15% is critical
    },
    "avg_response_time_hours": {
        "healthy": 4.0,   # <4 hours is healthy
        "warning": 24.0,  # 4-24 hours is warning
        # >24 hours is critical
        "lower_is_better": True,
    },
    "messages_per_active_member": {
        "healthy": 2.0,   # 2+ messages/member is healthy
        "warning": 1.0,   # 1-2 is warning
        # <1 is critical
    },
    # Activity metrics
    "messages_per_day": {
        "healthy": 50.0,  # 50+ msgs/day is healthy
        "warning": 10.0,  # 10-50 is warning
        # <10 is critical
    },
    "active_channel_ratio": {
        "healthy": 0.5,   # 50%+ channels active is healthy
        "warning": 0.3,   # 30-50% is warning
        # <30% is critical
    },
    # Contributor metrics
    "contributor_diversity": {
        "healthy": 50.0,  # Top 10% contributes <50% is healthy
        "warning": 70.0,  # 50-70% is warning
        # >70% is critical
        "lower_is_better": True,
    },
    "new_member_retention": {
        "healthy": 50.0,  # 50%+ retention is healthy
        "warning": 30.0,  # 30-50% is warning
        # <30% is critical
    },
}


def compare_to_benchmarks(
    activity: ActivityMetrics,
    engagement: EngagementMetrics,
    contributors: ContributorMetrics,
    custom_benchmarks: Optional[Dict[str, Dict[str, float]]] = None,
) -> BenchmarkComparison:
    """Compare metrics against benchmark thresholds.

    Args:
        activity: Activity metrics.
        engagement: Engagement metrics.
        contributors: Contributor metrics.
        custom_benchmarks: Optional custom threshold overrides.

    Returns:
        BenchmarkComparison object.
    """
    # Merge custom benchmarks with defaults
    benchmarks = DEFAULT_BENCHMARKS.copy()
    if custom_benchmarks:
        for metric, thresholds in custom_benchmarks.items():
            if metric in benchmarks:
                benchmarks[metric].update(thresholds)
            else:
                benchmarks[metric] = thresholds

    source = "custom" if custom_benchmarks else "default"
    comparisons: List[BenchmarkResult] = []

    # Calculate derived metrics
    total_channels = activity.active_channels + activity.inactive_channels
    active_channel_ratio = (
        activity.active_channels / total_channels
        if total_channels > 0 else 0
    )

    messages_per_active = (
        activity.messages_per_day_average / engagement.daily_active_members_average
        if engagement.daily_active_members_average > 0 else 0
    )

    contributor_diversity = (
        contributors.distribution.top_10_pct
        if contributors.distribution else 50.0
    )

    # Build metrics dict for comparison
    metrics = {
        "daily_active_pct": engagement.daily_active_members_percentage,
        "response_rate": engagement.reply_rate,
        "avg_response_time_hours": engagement.avg_response_time_hours,
        "messages_per_active_member": messages_per_active,
        "messages_per_day": activity.messages_per_day_average,
        "active_channel_ratio": active_channel_ratio,
        "contributor_diversity": contributor_diversity,
        "new_member_retention": contributors.new_contributors_retention_rate,
    }

    # Compare each metric
    for metric_name, value in metrics.items():
        if metric_name not in benchmarks:
            continue

        threshold = benchmarks[metric_name]
        healthy_threshold = threshold["healthy"]
        warning_threshold = threshold["warning"]
        lower_is_better = threshold.get("lower_is_better", False)

        status = _determine_status(
            value, healthy_threshold, warning_threshold, bool(lower_is_better)
        )

        comparisons.append(BenchmarkResult(
            metric=metric_name,
            value=round(value, 2),
            threshold_healthy=healthy_threshold,
            threshold_warning=warning_threshold,
            status=status,
        ))

    # Calculate overall assessment
    overall = _calculate_overall_assessment(comparisons)

    # Calculate score (0-100)
    score = _calculate_benchmark_score(comparisons)

    return BenchmarkComparison(
        source=source,
        comparisons=comparisons,
        overall_assessment=overall,
        score=score,
    )


def _determine_status(
    value: float,
    healthy_threshold: float,
    warning_threshold: float,
    lower_is_better: bool,
) -> HealthStatus:
    """Determine health status based on thresholds.

    Args:
        value: Current metric value.
        healthy_threshold: Threshold for healthy status.
        warning_threshold: Threshold for warning status.
        lower_is_better: If True, lower values are better.

    Returns:
        HealthStatus enum value.
    """
    if lower_is_better:
        # Lower is better (e.g., response time)
        if value <= healthy_threshold:
            return HealthStatus.HEALTHY
        elif value <= warning_threshold:
            return HealthStatus.WARNING
        else:
            return HealthStatus.CRITICAL
    else:
        # Higher is better (e.g., engagement rate)
        if value >= healthy_threshold:
            return HealthStatus.HEALTHY
        elif value >= warning_threshold:
            return HealthStatus.WARNING
        else:
            return HealthStatus.CRITICAL


def _calculate_overall_assessment(
    comparisons: List[BenchmarkResult]
) -> HealthStatus:
    """Calculate overall health assessment from comparisons.

    Args:
        comparisons: List of benchmark results.

    Returns:
        Overall HealthStatus.
    """
    if not comparisons:
        return HealthStatus.HEALTHY

    # Count statuses
    critical_count = sum(1 for c in comparisons if c.status == HealthStatus.CRITICAL)
    warning_count = sum(1 for c in comparisons if c.status == HealthStatus.WARNING)

    # If any critical, overall is critical
    if critical_count > 0:
        return HealthStatus.CRITICAL

    # If more than half are warnings, overall is warning
    if warning_count > len(comparisons) / 2:
        return HealthStatus.WARNING

    return HealthStatus.HEALTHY


def _calculate_benchmark_score(comparisons: List[BenchmarkResult]) -> int:
    """Calculate a 0-100 benchmark score.

    Args:
        comparisons: List of benchmark results.

    Returns:
        Score 0-100.
    """
    if not comparisons:
        return 50

    # Score each comparison
    scores = []
    for comp in comparisons:
        if comp.status == HealthStatus.HEALTHY:
            scores.append(100)
        elif comp.status == HealthStatus.WARNING:
            scores.append(50)
        else:
            scores.append(20)

    return int(sum(scores) / len(scores))


def compare_servers(
    report1: HealthReport,
    report2: HealthReport,
) -> Dict[str, Dict[str, float]]:
    """Compare two server health reports.

    Args:
        report1: First server's health report.
        report2: Second server's health report.

    Returns:
        Dictionary of metric comparisons.
    """
    comparisons = {}

    # Activity comparisons
    comparisons["total_messages"] = {
        report1.server_name: report1.activity.total_messages,
        report2.server_name: report2.activity.total_messages,
    }
    comparisons["messages_per_day"] = {
        report1.server_name: report1.activity.messages_per_day_average,
        report2.server_name: report2.activity.messages_per_day_average,
    }

    # Engagement comparisons
    comparisons["unique_authors"] = {
        report1.server_name: report1.engagement.unique_authors,
        report2.server_name: report2.engagement.unique_authors,
    }
    comparisons["daily_active_pct"] = {
        report1.server_name: report1.engagement.daily_active_members_percentage,
        report2.server_name: report2.engagement.daily_active_members_percentage,
    }
    comparisons["reply_rate"] = {
        report1.server_name: report1.engagement.reply_rate,
        report2.server_name: report2.engagement.reply_rate,
    }
    comparisons["avg_response_time"] = {
        report1.server_name: report1.engagement.avg_response_time_hours,
        report2.server_name: report2.engagement.avg_response_time_hours,
    }

    # Health score comparisons
    comparisons["overall_score"] = {
        report1.server_name: report1.health_scores.overall,
        report2.server_name: report2.health_scores.overall,
    }

    return comparisons


def load_custom_benchmarks(config: Dict) -> Optional[Dict[str, Dict[str, float]]]:
    """Load custom benchmarks from configuration.

    Expected config format:
    ```yaml
    discord:
      analytics:
        benchmarks:
          daily_active_pct:
            healthy: 15
            warning: 8
          response_rate:
            healthy: 40
            warning: 20
    ```

    Args:
        config: Configuration dictionary.

    Returns:
        Custom benchmarks dict, or None if not configured.
    """
    discord_config = config.get("discord", {})
    analytics_config = discord_config.get("analytics", {})
    benchmarks_config = analytics_config.get("benchmarks", {})

    if not benchmarks_config:
        return None

    custom_benchmarks = {}
    for metric, thresholds in benchmarks_config.items():
        if isinstance(thresholds, dict):
            custom_benchmarks[metric] = {
                "healthy": float(thresholds.get("healthy", 0)),
                "warning": float(thresholds.get("warning", 0)),
            }

    return custom_benchmarks if custom_benchmarks else None
