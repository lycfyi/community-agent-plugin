"""Health metrics calculations for Discord Community Analytics.

Calculates activity, engagement, and contributor metrics from parsed messages.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median
from typing import Dict, List, Optional, Tuple

from .models import (
    ActivityMetrics,
    ChannelActivity,
    ContributorDistribution,
    ContributorMetrics,
    EngagementMetrics,
    HealthScores,
    PeakDay,
    PeakTime,
    ReactionStat,
    TopContributor,
)
from .parser import ParsedMessage


@dataclass
class MetricsInput:
    """Input data for metrics calculation."""
    messages: List[ParsedMessage]
    analysis_start: datetime
    analysis_end: datetime


def calculate_activity_metrics(
    messages: List[ParsedMessage],
    analysis_start: datetime,
    analysis_end: datetime,
) -> ActivityMetrics:
    """Calculate activity metrics from messages.

    Args:
        messages: List of parsed messages.
        analysis_start: Start of analysis period.
        analysis_end: End of analysis period.

    Returns:
        ActivityMetrics object.
    """
    if not messages:
        return ActivityMetrics(
            total_messages=0,
            messages_per_day_average=0,
            messages_per_day_min=0,
            messages_per_day_max=0,
            active_channels=0,
            inactive_channels=0,
        )

    total_days = max(1, (analysis_end - analysis_start).days + 1)

    # Count messages per day
    daily_counts: Dict[str, int] = defaultdict(int)
    for msg in messages:
        date_key = msg.timestamp.strftime("%Y-%m-%d")
        daily_counts[date_key] += 1

    # Fill in missing days with 0
    current_date = analysis_start
    while current_date <= analysis_end:
        date_key = current_date.strftime("%Y-%m-%d")
        if date_key not in daily_counts:
            daily_counts[date_key] = 0
        current_date += timedelta(days=1)

    daily_values = list(daily_counts.values())
    total_messages = sum(daily_values)

    # Channel breakdown
    channel_counts: Dict[str, int] = defaultdict(int)
    for msg in messages:
        channel_counts[msg.channel_name] += 1

    # Sort channels by message count
    sorted_channels = sorted(
        channel_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )

    channel_breakdown = [
        ChannelActivity(
            name=name,
            messages=count,
            percentage=round((count / total_messages) * 100, 1) if total_messages else 0
        )
        for name, count in sorted_channels[:10]  # Top 10 channels
    ]

    # Count active vs inactive channels
    # A channel is "active" if it has at least 1 message per day on average
    active_threshold = total_days * 0.1  # At least 10% of days had activity
    active_channels = sum(1 for count in channel_counts.values() if count >= active_threshold)
    inactive_channels = len(channel_counts) - active_channels

    # Peak hours (0-23)
    hour_counts: Dict[int, int] = defaultdict(int)
    for msg in messages:
        hour_counts[msg.timestamp.hour] += 1

    peak_hours = [
        PeakTime(hour=hour, messages=count)
        for hour, count in sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    ]

    # Peak days of week
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_counts: Dict[str, int] = defaultdict(int)
    for msg in messages:
        day_name = day_names[msg.timestamp.weekday()]
        day_counts[day_name] += 1

    peak_days = [
        PeakDay(day=day, messages=count)
        for day, count in sorted(day_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    ]

    return ActivityMetrics(
        total_messages=total_messages,
        messages_per_day_average=round(total_messages / total_days, 1),
        messages_per_day_min=min(daily_values) if daily_values else 0,
        messages_per_day_max=max(daily_values) if daily_values else 0,
        active_channels=active_channels,
        inactive_channels=inactive_channels,
        channel_breakdown=channel_breakdown,
        peak_hours=peak_hours,
        peak_days=peak_days,
    )


def calculate_engagement_metrics(
    messages: List[ParsedMessage],
    analysis_start: datetime,
    analysis_end: datetime,
) -> EngagementMetrics:
    """Calculate engagement metrics from messages.

    Args:
        messages: List of parsed messages.
        analysis_start: Start of analysis period.
        analysis_end: End of analysis period.

    Returns:
        EngagementMetrics object.
    """
    if not messages:
        return EngagementMetrics(
            unique_authors=0,
            daily_active_members_average=0,
            daily_active_members_percentage=0,
            messages_per_author_average=0,
            messages_per_author_median=0,
            reply_rate=0,
            avg_response_time_hours=0,
            total_reactions=0,
            messages_with_reactions=0,
            avg_reactions_per_message=0,
        )

    total_days = max(1, (analysis_end - analysis_start).days + 1)

    # Unique authors
    author_ids = set()
    author_message_counts: Dict[str, int] = defaultdict(int)
    for msg in messages:
        author_ids.add(msg.author_id)
        author_message_counts[msg.author_id] += 1

    unique_authors = len(author_ids)

    # Daily active members
    daily_authors: Dict[str, set] = defaultdict(set)
    for msg in messages:
        date_key = msg.timestamp.strftime("%Y-%m-%d")
        daily_authors[date_key].add(msg.author_id)

    daily_active_counts = [len(authors) for authors in daily_authors.values()]
    daily_active_average = sum(daily_active_counts) / total_days if total_days else 0
    daily_active_percentage = (daily_active_average / unique_authors * 100) if unique_authors else 0

    # Messages per author
    message_counts = list(author_message_counts.values())
    messages_per_author_average = sum(message_counts) / len(message_counts) if message_counts else 0
    messages_per_author_median = median(message_counts) if message_counts else 0

    # Reply rate
    reply_count = sum(1 for msg in messages if msg.is_reply)
    reply_rate = (reply_count / len(messages) * 100) if messages else 0

    # Average response time (simplified - based on replies)
    # Group messages by date/channel to estimate response times
    response_times = []
    messages_by_channel: Dict[str, List[ParsedMessage]] = defaultdict(list)
    for msg in messages:
        messages_by_channel[msg.channel_name].append(msg)

    for channel_msgs in messages_by_channel.values():
        sorted_msgs = sorted(channel_msgs, key=lambda m: m.timestamp)
        for i, msg in enumerate(sorted_msgs):
            if msg.is_reply and i > 0:
                # Find the previous message (rough estimate)
                prev_msg = sorted_msgs[i - 1]
                time_diff = (msg.timestamp - prev_msg.timestamp).total_seconds() / 3600
                if time_diff < 168:  # Within a week
                    response_times.append(time_diff)

    avg_response_time_hours = sum(response_times) / len(response_times) if response_times else 0

    # Reactions
    total_reactions = sum(msg.total_reactions for msg in messages)
    messages_with_reactions = sum(1 for msg in messages if msg.total_reactions > 0)
    avg_reactions_per_message = total_reactions / len(messages) if messages else 0

    # Top reactions
    all_reactions: Counter = Counter()
    for msg in messages:
        for emoji, count in msg.reactions.items():
            all_reactions[emoji] += count

    top_reactions = [
        ReactionStat(emoji=emoji, count=count)
        for emoji, count in all_reactions.most_common(5)
    ]

    return EngagementMetrics(
        unique_authors=unique_authors,
        daily_active_members_average=round(daily_active_average, 1),
        daily_active_members_percentage=round(daily_active_percentage, 1),
        messages_per_author_average=round(messages_per_author_average, 1),
        messages_per_author_median=round(messages_per_author_median, 1),
        reply_rate=round(reply_rate, 1),
        avg_response_time_hours=round(avg_response_time_hours, 1),
        total_reactions=total_reactions,
        messages_with_reactions=messages_with_reactions,
        avg_reactions_per_message=round(avg_reactions_per_message, 2),
        top_reactions=top_reactions,
    )


def calculate_contributor_metrics(
    messages: List[ParsedMessage],
    analysis_start: datetime,
    analysis_end: datetime,
) -> ContributorMetrics:
    """Calculate contributor metrics from messages.

    Args:
        messages: List of parsed messages.
        analysis_start: Start of analysis period.
        analysis_end: End of analysis period.

    Returns:
        ContributorMetrics object.
    """
    if not messages:
        return ContributorMetrics(total_unique=0)

    # Count messages and engagement per author
    author_data: Dict[str, Dict] = defaultdict(lambda: {
        "name": "",
        "message_count": 0,
        "engagement_received": 0,
        "first_message": None,
    })

    for msg in messages:
        data = author_data[msg.author_id]
        data["name"] = msg.author_name
        data["message_count"] += 1
        data["engagement_received"] += msg.total_reactions
        if data["first_message"] is None or msg.timestamp < data["first_message"]:
            data["first_message"] = msg.timestamp

    total_messages = len(messages)
    total_unique = len(author_data)

    # Sort by message count
    sorted_authors = sorted(
        author_data.items(),
        key=lambda x: x[1]["message_count"],
        reverse=True
    )

    # Top 10 contributors
    top_contributors = [
        TopContributor(
            author_id=author_id,
            author_name=data["name"],
            message_count=data["message_count"],
            percentage=round((data["message_count"] / total_messages) * 100, 1),
            engagement_received=data["engagement_received"],
        )
        for author_id, data in sorted_authors[:10]
    ]

    # New contributors (first message in analysis period)
    # A "new" contributor has their first message within the first 7 days of the period
    new_threshold = analysis_start + timedelta(days=7)
    new_contributors = [
        (author_id, data) for author_id, data in author_data.items()
        if data["first_message"] and data["first_message"] <= new_threshold
    ]
    new_contributors_count = len(new_contributors)

    # Retention: how many new contributors posted again after 7 days
    retained_count = 0
    for author_id, data in new_contributors:
        # Check if they have messages after the first 7 days
        author_msgs = [m for m in messages if m.author_id == author_id]
        has_later_messages = any(
            m.timestamp > new_threshold for m in author_msgs
        )
        if has_later_messages:
            retained_count += 1

    retention_rate = (retained_count / new_contributors_count * 100) if new_contributors_count else 0

    # Distribution (Pareto analysis)
    message_counts = sorted([d["message_count"] for d in author_data.values()], reverse=True)

    def calc_percentile_contribution(pct: float) -> float:
        """Calculate what percentage of messages come from top pct% of authors."""
        n_authors = max(1, int(len(message_counts) * pct))
        top_messages = sum(message_counts[:n_authors])
        return (top_messages / total_messages * 100) if total_messages else 0

    distribution = ContributorDistribution(
        top_1_pct=round(calc_percentile_contribution(0.01), 1),
        top_10_pct=round(calc_percentile_contribution(0.10), 1),
        top_50_pct=round(calc_percentile_contribution(0.50), 1),
    )

    return ContributorMetrics(
        total_unique=total_unique,
        top_contributors=top_contributors,
        new_contributors_count=new_contributors_count,
        new_contributors_retention_rate=round(retention_rate, 1),
        distribution=distribution,
    )


def calculate_health_scores(
    activity: ActivityMetrics,
    engagement: EngagementMetrics,
    contributors: ContributorMetrics,
) -> HealthScores:
    """Calculate composite health scores from metrics.

    Each dimension is scored 0-100:
    - Activity: Based on message volume and channel activity
    - Engagement: Based on reply rate, reactions, and active members
    - Responsiveness: Based on response time
    - Diversity: Based on contributor distribution

    Args:
        activity: Activity metrics.
        engagement: Engagement metrics.
        contributors: Contributor metrics.

    Returns:
        HealthScores object with scores 0-100.
    """
    # Activity score
    # Factors: messages per day, active channels
    activity_score = 0
    if activity.messages_per_day_average > 0:
        # Messages per day: 100+ is great, 10+ is good
        msg_score = min(100, activity.messages_per_day_average * 2)

        # Active channels: more is better, cap at 10
        channel_score = min(100, activity.active_channels * 10)

        activity_score = int((msg_score * 0.7 + channel_score * 0.3))

    # Engagement score
    # Factors: daily active %, reply rate, reactions
    engagement_score = 0
    if engagement.unique_authors > 0:
        # Daily active %: 10%+ is healthy
        active_score = min(100, engagement.daily_active_members_percentage * 5)

        # Reply rate: 30%+ is good
        reply_score = min(100, engagement.reply_rate * 2)

        # Reactions: average of 0.5+ per message is good
        reaction_score = min(100, engagement.avg_reactions_per_message * 100)

        engagement_score = int((active_score * 0.4 + reply_score * 0.4 + reaction_score * 0.2))

    # Responsiveness score
    # Factor: average response time (lower is better)
    responsiveness_score = 100
    if engagement.avg_response_time_hours > 0:
        # Under 4 hours is great, over 24 hours is poor
        if engagement.avg_response_time_hours < 4:
            responsiveness_score = 100
        elif engagement.avg_response_time_hours < 8:
            responsiveness_score = 80
        elif engagement.avg_response_time_hours < 24:
            responsiveness_score = 60
        else:
            responsiveness_score = max(20, 100 - engagement.avg_response_time_hours)

    # Diversity score
    # Factor: contribution distribution (less concentrated is better)
    diversity_score = 50
    if contributors.distribution:
        # If top 10% contributes less than 50%, good diversity
        top_10_pct = contributors.distribution.top_10_pct
        if top_10_pct < 40:
            diversity_score = 100
        elif top_10_pct < 50:
            diversity_score = 80
        elif top_10_pct < 60:
            diversity_score = 60
        elif top_10_pct < 80:
            diversity_score = 40
        else:
            diversity_score = 20

    # Overall score (weighted average)
    overall = int(
        activity_score * 0.3 +
        engagement_score * 0.3 +
        responsiveness_score * 0.2 +
        diversity_score * 0.2
    )

    return HealthScores(
        overall=overall,
        activity=activity_score,
        engagement=engagement_score,
        responsiveness=responsiveness_score,
        diversity=diversity_score,
    )
