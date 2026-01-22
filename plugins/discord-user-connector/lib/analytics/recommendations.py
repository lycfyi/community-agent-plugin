"""Recommendation generator for Discord Community Health Analytics.

Generates actionable recommendations based on metrics and benchmarks.
"""

from typing import List, Optional

from .models import (
    ActivityMetrics,
    BenchmarkComparison,
    ContributorMetrics,
    EngagementMetrics,
    HealthScores,
    HealthStatus,
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
    TrendData,
)


def generate_recommendations(
    health_scores: HealthScores,
    activity: ActivityMetrics,
    engagement: EngagementMetrics,
    contributors: ContributorMetrics,
    benchmarks: Optional[BenchmarkComparison] = None,
    trends: Optional[TrendData] = None,
) -> List[Recommendation]:
    """Generate prioritized recommendations based on analysis.

    Args:
        health_scores: Calculated health scores.
        activity: Activity metrics.
        engagement: Engagement metrics.
        contributors: Contributor metrics.
        benchmarks: Optional benchmark comparisons.
        trends: Optional trend data.

    Returns:
        List of Recommendation objects, sorted by priority.
    """
    recommendations: List[Recommendation] = []
    rec_id = 1

    # Check activity metrics
    if activity.messages_per_day_average < 10:
        recommendations.append(Recommendation(
            id=rec_id,
            priority=RecommendationPriority.HIGH,
            category=RecommendationCategory.ACTIVITY,
            title="Increase overall community activity",
            description=(
                f"Average activity is {activity.messages_per_day_average:.1f} messages/day. "
                "Consider initiatives to boost engagement."
            ),
            metric_reference="messages_per_day_average",
            current_value=activity.messages_per_day_average,
            target_value=50,
            actions=[
                "Create conversation starters or discussion topics",
                "Host community events or AMAs",
                "Encourage introductions in new member channels",
                "Review and update channel organization",
            ],
        ))
        rec_id += 1

    # Check for inactive channels
    if activity.inactive_channels > 0:
        inactive_ratio = activity.inactive_channels / max(1, activity.active_channels + activity.inactive_channels)
        if inactive_ratio > 0.5:
            recommendations.append(Recommendation(
                id=rec_id,
                priority=RecommendationPriority.MEDIUM,
                category=RecommendationCategory.CONTENT,
                title="Address inactive channels",
                description=(
                    f"{activity.inactive_channels} channels have low activity. "
                    "Consider consolidating or revitalizing them."
                ),
                metric_reference="inactive_channels",
                current_value=activity.inactive_channels,
                target_value=max(1, activity.inactive_channels // 2),
                actions=[
                    "Archive unused channels to reduce clutter",
                    "Merge similar low-activity channels",
                    "Create targeted content for underused channels",
                    "Review channel purposes and update descriptions",
                ],
            ))
            rec_id += 1

    # Check engagement metrics
    if engagement.daily_active_members_percentage < 10:
        recommendations.append(Recommendation(
            id=rec_id,
            priority=RecommendationPriority.HIGH,
            category=RecommendationCategory.ENGAGEMENT,
            title="Improve member engagement rate",
            description=(
                f"Only {engagement.daily_active_members_percentage:.1f}% of members are active daily. "
                "Target at least 10% daily active members."
            ),
            metric_reference="daily_active_members_percentage",
            current_value=engagement.daily_active_members_percentage,
            target_value=10.0,
            actions=[
                "Send welcome messages to new members",
                "Create engagement incentives or rewards",
                "Schedule regular community activities",
                "Use mentions to bring members back into conversations",
            ],
        ))
        rec_id += 1

    if engagement.reply_rate < 30:
        recommendations.append(Recommendation(
            id=rec_id,
            priority=RecommendationPriority.MEDIUM,
            category=RecommendationCategory.ENGAGEMENT,
            title="Increase conversation reply rate",
            description=(
                f"Reply rate is {engagement.reply_rate:.1f}%. "
                "More replies indicate healthier discussions."
            ),
            metric_reference="reply_rate",
            current_value=engagement.reply_rate,
            target_value=30.0,
            actions=[
                "Encourage moderators to respond to unanswered questions",
                "Create FAQ channels for common questions",
                "Acknowledge contributions with reactions or replies",
                "Ask follow-up questions to spark discussions",
            ],
        ))
        rec_id += 1

    if engagement.avg_response_time_hours > 24:
        recommendations.append(Recommendation(
            id=rec_id,
            priority=RecommendationPriority.HIGH,
            category=RecommendationCategory.ENGAGEMENT,
            title="Reduce response time",
            description=(
                f"Average response time is {engagement.avg_response_time_hours:.1f} hours. "
                "Faster responses improve member satisfaction."
            ),
            metric_reference="avg_response_time_hours",
            current_value=engagement.avg_response_time_hours,
            target_value=4.0,
            actions=[
                "Assign dedicated moderators for different time zones",
                "Set up notification alerts for unanswered questions",
                "Create a support ticket system for important queries",
                "Encourage community members to help each other",
            ],
        ))
        rec_id += 1

    # Check contributor diversity
    if contributors.distribution:
        if contributors.distribution.top_10_pct > 80:
            recommendations.append(Recommendation(
                id=rec_id,
                priority=RecommendationPriority.MEDIUM,
                category=RecommendationCategory.ENGAGEMENT,
                title="Encourage broader participation",
                description=(
                    f"Top 10% of members create {contributors.distribution.top_10_pct:.1f}% of content. "
                    "Healthier communities have more diverse contributors."
                ),
                metric_reference="top_10_pct_contribution",
                current_value=contributors.distribution.top_10_pct,
                target_value=50.0,
                actions=[
                    "Recognize and highlight new contributors",
                    "Create easy entry points for first-time posters",
                    "Ask lurkers specific questions to encourage participation",
                    "Run community spotlights for different members",
                ],
            ))
            rec_id += 1

    # Check top contributor recognition
    if contributors.top_contributors:
        top_contributor = contributors.top_contributors[0]
        if top_contributor.percentage > 10:
            recommendations.append(Recommendation(
                id=rec_id,
                priority=RecommendationPriority.LOW,
                category=RecommendationCategory.MODERATION,
                title="Recognize top contributors",
                description=(
                    f"{top_contributor.author_name} contributes {top_contributor.percentage:.1f}% of messages. "
                    "Consider recognizing dedicated members."
                ),
                metric_reference="top_contributor_percentage",
                current_value=top_contributor.percentage,
                target_value=5.0,
                actions=[
                    "Create a contributor recognition program",
                    "Award special roles or badges to active members",
                    "Feature top contributors in announcements",
                    "Consider them for moderator positions",
                ],
            ))
            rec_id += 1

    # Check new contributor retention
    if contributors.new_contributors_count > 0 and contributors.new_contributors_retention_rate < 50:
        recommendations.append(Recommendation(
            id=rec_id,
            priority=RecommendationPriority.HIGH,
            category=RecommendationCategory.ENGAGEMENT,
            title="Improve new member retention",
            description=(
                f"Only {contributors.new_contributors_retention_rate:.1f}% of new members remain active. "
                "Focus on onboarding experience."
            ),
            metric_reference="new_contributors_retention_rate",
            current_value=contributors.new_contributors_retention_rate,
            target_value=70.0,
            actions=[
                "Create a welcoming onboarding experience",
                "Assign mentors or buddies to new members",
                "Follow up with new members who haven't posted",
                "Gather feedback from members who left",
            ],
        ))
        rec_id += 1

    # Check benchmark failures
    if benchmarks:
        for comparison in benchmarks.comparisons:
            if comparison.status == HealthStatus.CRITICAL:
                recommendations.append(Recommendation(
                    id=rec_id,
                    priority=RecommendationPriority.HIGH,
                    category=RecommendationCategory.ACTIVITY,
                    title=f"Address critical: {comparison.metric}",
                    description=(
                        f"{comparison.metric} is at critical level "
                        f"({comparison.value:.1f} vs threshold {comparison.threshold_warning:.1f})."
                    ),
                    metric_reference=comparison.metric,
                    current_value=comparison.value,
                    target_value=comparison.threshold_healthy,
                    actions=[
                        f"Review factors affecting {comparison.metric}",
                        "Compare with successful communities",
                        "Implement targeted improvement plan",
                    ],
                ))
                rec_id += 1
            elif comparison.status == HealthStatus.WARNING:
                recommendations.append(Recommendation(
                    id=rec_id,
                    priority=RecommendationPriority.MEDIUM,
                    category=RecommendationCategory.ACTIVITY,
                    title=f"Improve {comparison.metric}",
                    description=(
                        f"{comparison.metric} is below healthy threshold "
                        f"({comparison.value:.1f} vs {comparison.threshold_healthy:.1f})."
                    ),
                    metric_reference=comparison.metric,
                    current_value=comparison.value,
                    target_value=comparison.threshold_healthy,
                    actions=[
                        f"Monitor {comparison.metric} trends",
                        "Identify contributing factors",
                        "Set improvement goals",
                    ],
                ))
                rec_id += 1

    # Check trend data for significant declines
    if trends:
        for change in trends.metric_changes:
            if change.significant and change.direction.value == "down":
                recommendations.append(Recommendation(
                    id=rec_id,
                    priority=RecommendationPriority.HIGH,
                    category=RecommendationCategory.ACTIVITY,
                    title=f"Investigate {change.metric} decline",
                    description=(
                        f"{change.metric} dropped {abs(change.change_pct):.1f}% this week. "
                        "Significant declines need attention."
                    ),
                    metric_reference=change.metric,
                    current_value=change.current,
                    target_value=change.previous,
                    actions=[
                        "Review recent changes that may have caused decline",
                        "Check for external factors affecting the community",
                        "Gather feedback from members",
                        "Implement recovery strategies",
                    ],
                ))
                rec_id += 1

    # Sort by priority (HIGH first, then MEDIUM, then LOW)
    priority_order = {
        RecommendationPriority.HIGH: 0,
        RecommendationPriority.MEDIUM: 1,
        RecommendationPriority.LOW: 2,
    }
    recommendations.sort(key=lambda r: priority_order[r.priority])

    return recommendations
