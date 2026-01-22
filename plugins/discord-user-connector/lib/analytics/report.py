"""Report generator for Discord Community Health Analytics.

Generates health-report.md and health-report.yaml files.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import yaml

from .models import (
    AnalysisPeriod,
    BenchmarkComparison,
    HealthReport,
    HealthScores,
    HealthStatus,
    Recommendation,
    RecommendationPriority,
    TopicCluster,
    TrendData,
)
from .parser import MessageParser, ParsedMessage
from .metrics import (
    calculate_activity_metrics,
    calculate_contributor_metrics,
    calculate_engagement_metrics,
    calculate_health_scores,
)
from .topics import cluster_messages_by_topic
from .trends import detect_trends
from .benchmarks import compare_to_benchmarks
from .recommendations import generate_recommendations
from .progress import AnalysisProgress


def generate_health_report(
    server_dir: Path,
    server_id: str,
    server_name: str,
    days: int = 30,
    custom_benchmarks: Optional[dict] = None,
    verbose: bool = False,
) -> HealthReport:
    """Generate a complete health report for a server.

    Args:
        server_dir: Path to server data directory.
        server_id: Server ID.
        server_name: Server display name.
        days: Number of days to analyze.
        custom_benchmarks: Optional custom benchmark thresholds.
        verbose: Show progress output.

    Returns:
        HealthReport object.
    """
    progress = AnalysisProgress(verbose=verbose)
    progress.start()

    # Phase 1: Read messages
    progress.set_phase("reading")

    parser = MessageParser()
    messages: List[ParsedMessage] = []

    # Count total messages first for progress
    message_files = list(server_dir.glob("*/messages.md"))
    total_files = len(message_files)

    for idx, file_path in enumerate(message_files):
        channel_name = file_path.parent.name
        for msg in parser.parse_file(file_path, channel_name):
            messages.append(msg)

        progress.update_phase_progress((idx + 1) / total_files)

    # Calculate analysis period
    analysis_end = datetime.now()
    analysis_start = analysis_end - timedelta(days=days)

    # Filter messages to analysis period
    messages_in_period = [
        m for m in messages
        if analysis_start <= m.timestamp <= analysis_end
    ]

    # Check for edge cases
    partial_report = False
    partial_reason = None

    if not messages_in_period:
        # No messages in period - check if any messages exist
        if messages:
            # Use all available messages
            messages_in_period = messages
            actual_days = (max(m.timestamp for m in messages) - min(m.timestamp for m in messages)).days
            if actual_days < 7:
                partial_report = True
                partial_reason = f"Only {actual_days} days of data available (minimum 7 recommended)"
        else:
            partial_report = True
            partial_reason = "No messages found in synced data"

    # Phase 2: Calculate metrics
    progress.set_phase("metrics")

    activity = calculate_activity_metrics(messages_in_period, analysis_start, analysis_end)
    progress.update_phase_progress(0.33)

    engagement = calculate_engagement_metrics(messages_in_period, analysis_start, analysis_end)
    progress.update_phase_progress(0.66)

    contributors = calculate_contributor_metrics(messages_in_period, analysis_start, analysis_end)
    progress.update_phase_progress(1.0)

    # Phase 3: Topic clustering
    progress.set_phase("topics")

    topics = cluster_messages_by_topic(messages_in_period)
    progress.update_phase_progress(1.0)

    # Detect trends (requires 14+ days)
    trends = detect_trends(
        messages_in_period,
        analysis_start,
        analysis_end,
        current_topics=topics,
    )

    # Compare to benchmarks
    benchmarks = compare_to_benchmarks(
        activity, engagement, contributors,
        custom_benchmarks=custom_benchmarks,
    )

    # Calculate health scores
    health_scores = calculate_health_scores(activity, engagement, contributors)

    # Phase 4: Generate report
    progress.set_phase("report")

    # Generate recommendations
    recommendations = generate_recommendations(
        health_scores, activity, engagement, contributors,
        benchmarks=benchmarks, trends=trends,
    )

    progress.update_phase_progress(0.5)

    # Build report
    report = HealthReport(
        report_id=f"011-{server_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        server_id=server_id,
        server_name=server_name,
        generated_at=datetime.now().isoformat(),
        analysis_period=AnalysisPeriod(
            start=analysis_start.strftime("%Y-%m-%d"),
            end=analysis_end.strftime("%Y-%m-%d"),
            days=days,
        ),
        message_count=len(messages_in_period),
        channel_count=activity.active_channels + activity.inactive_channels,
        health_scores=health_scores,
        activity=activity,
        engagement=engagement,
        contributors=contributors,
        topics=topics,
        trends=trends,
        benchmarks=benchmarks,
        recommendations=recommendations,
        partial_report=partial_report,
        partial_reason=partial_reason,
    )

    progress.update_phase_progress(1.0)
    progress.finish("Analysis complete")

    return report


def save_health_report(report: HealthReport, server_dir: Path) -> tuple[Path, Path]:
    """Save health report to markdown and YAML files.

    Args:
        report: HealthReport object.
        server_dir: Server data directory.

    Returns:
        Tuple of (markdown_path, yaml_path).
    """
    md_path = server_dir / "health-report.md"
    yaml_path = server_dir / "health-report.yaml"

    # Generate markdown
    markdown_content = _generate_markdown_report(report)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    # Generate YAML
    yaml_content = _generate_yaml_report(report)
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    return md_path, yaml_path


def _generate_markdown_report(report: HealthReport) -> str:
    """Generate markdown format health report.

    Args:
        report: HealthReport object.

    Returns:
        Markdown string.
    """
    lines = []

    # YAML frontmatter
    lines.append("---")
    lines.append(f"server_id: \"{report.server_id}\"")
    lines.append(f"server_name: \"{report.server_name}\"")
    lines.append(f"generated_at: \"{report.generated_at}\"")
    lines.append(f"analysis_period: \"{report.analysis_period.start} to {report.analysis_period.end} ({report.analysis_period.days} days)\"")
    lines.append("---")
    lines.append("")

    # Title
    lines.append(f"# Community Health Report: {report.server_name}")
    lines.append("")

    # Partial report warning
    if report.partial_report:
        lines.append(f"> **Note**: {report.partial_reason}")
        lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"**Overall Health Score: {report.health_scores.overall}/100** ({_status_label(report.health_scores.overall)})")
    lines.append("")
    lines.append(f"Your community shows {report.message_count:,} messages from {report.engagement.unique_authors:,} unique members over the past {report.analysis_period.days} days. Key highlights:")
    lines.append("")

    # Key highlights
    highlights = _generate_summary_highlights(report)
    for highlight in highlights[:5]:
        lines.append(f"- {highlight}")
    lines.append("")

    # Health Scores
    lines.append("## Health Scores")
    lines.append("")
    lines.append("| Dimension | Score | Status |")
    lines.append("|-----------|-------|--------|")
    lines.append(f"| Activity | {report.health_scores.activity} | {_status_emoji(report.health_scores.activity)} {_status_label(report.health_scores.activity)} |")
    lines.append(f"| Engagement | {report.health_scores.engagement} | {_status_emoji(report.health_scores.engagement)} {_status_label(report.health_scores.engagement)} |")
    lines.append(f"| Responsiveness | {report.health_scores.responsiveness} | {_status_emoji(report.health_scores.responsiveness)} {_status_label(report.health_scores.responsiveness)} |")
    lines.append(f"| Diversity | {report.health_scores.diversity} | {_status_emoji(report.health_scores.diversity)} {_status_label(report.health_scores.diversity)} |")
    lines.append("")

    # Activity Overview
    lines.append("## Activity Overview")
    lines.append("")
    lines.append("### Message Volume")
    lines.append(f"- **Total messages**: {report.activity.total_messages:,}")
    lines.append(f"- **Daily average**: {report.activity.messages_per_day_average:.1f} messages/day")
    if report.activity.peak_days:
        peak = report.activity.peak_days[0]
        lines.append(f"- **Peak activity**: {peak.day}")
    lines.append("")

    # Channel Distribution
    if report.activity.channel_breakdown:
        lines.append("### Channel Distribution")
        lines.append("")
        lines.append("| Channel | Messages | % |")
        lines.append("|---------|----------|---|")
        for ch in report.activity.channel_breakdown[:5]:
            lines.append(f"| #{ch.name} | {ch.messages:,} | {ch.percentage}% |")
        lines.append("")

    # Topics
    if report.topics:
        lines.append("## Top Topics")
        lines.append("")
        for i, topic in enumerate(report.topics[:10], 1):
            keywords_str = ", ".join(topic.keywords[:5])
            lines.append(f"{i}. **{topic.label}** ({topic.percentage}% of messages) - Keywords: {keywords_str}")
        lines.append("")

    # Trends
    if report.trends:
        lines.append("## Trends")
        lines.append("")
        lines.append("### Significant Changes This Week")
        if report.trends.highlights:
            for highlight in report.trends.highlights[:5]:
                emoji = "📈" if highlight.impact == "positive" else "📉"
                lines.append(f"- {emoji} **{highlight.description}**")
        else:
            lines.append("- No significant changes detected")
        lines.append("")

        if report.trends.emerging_topics:
            lines.append("### Emerging Topics")
            for topic in report.trends.emerging_topics[:3]:
                lines.append(f"- \"{topic.label}\" - {topic.current_count} messages (new this week)")
            lines.append("")

    # Recommendations
    if report.recommendations:
        lines.append("## Recommendations")
        lines.append("")

        high_priority = [r for r in report.recommendations if r.priority == RecommendationPriority.HIGH]
        medium_priority = [r for r in report.recommendations if r.priority == RecommendationPriority.MEDIUM]

        if high_priority:
            lines.append("### High Priority")
            for i, rec in enumerate(high_priority[:3], 1):
                lines.append(f"{i}. **{rec.title}**")
                lines.append(f"   - {rec.description}")
                lines.append(f"   - Actions: {', '.join(rec.actions[:2])}")
            lines.append("")

        if medium_priority:
            lines.append("### Medium Priority")
            for i, rec in enumerate(medium_priority[:3], 1):
                lines.append(f"{i}. **{rec.title}**")
                lines.append(f"   - {rec.description}")
            lines.append("")

    # Benchmarks
    if report.benchmarks:
        lines.append("## Benchmark Comparison")
        lines.append("")
        lines.append("| Metric | Value | Threshold | Status |")
        lines.append("|--------|-------|-----------|--------|")
        for comp in report.benchmarks.comparisons:
            status_emoji = "✅" if comp.status == HealthStatus.HEALTHY else ("⚠️" if comp.status == HealthStatus.WARNING else "❌")
            lines.append(f"| {comp.metric.replace('_', ' ').title()} | {comp.value:.1f} | {comp.threshold_healthy:.1f} | {status_emoji} {comp.status.value.capitalize()} |")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("*Generated by Discord Community Health Analytics*")

    return "\n".join(lines)


def _generate_yaml_report(report: HealthReport) -> str:
    """Generate YAML format health report.

    Args:
        report: HealthReport object.

    Returns:
        YAML string.
    """
    # Convert dataclasses to dicts for YAML serialization
    data = {
        "report_id": report.report_id,
        "server_id": report.server_id,
        "server_name": report.server_name,
        "generated_at": report.generated_at,
        "analysis_period": {
            "start": report.analysis_period.start,
            "end": report.analysis_period.end,
            "days": report.analysis_period.days,
        },
        "message_count": report.message_count,
        "channel_count": report.channel_count,
        "health_scores": {
            "overall": report.health_scores.overall,
            "activity": report.health_scores.activity,
            "engagement": report.health_scores.engagement,
            "responsiveness": report.health_scores.responsiveness,
            "diversity": report.health_scores.diversity,
        },
        "activity": {
            "total_messages": report.activity.total_messages,
            "messages_per_day_average": report.activity.messages_per_day_average,
            "active_channels": report.activity.active_channels,
            "inactive_channels": report.activity.inactive_channels,
        },
        "engagement": {
            "unique_authors": report.engagement.unique_authors,
            "daily_active_members_percentage": report.engagement.daily_active_members_percentage,
            "reply_rate": report.engagement.reply_rate,
            "avg_response_time_hours": report.engagement.avg_response_time_hours,
        },
        "contributors": {
            "total_unique": report.contributors.total_unique,
            "new_contributors_count": report.contributors.new_contributors_count,
            "new_contributors_retention_rate": report.contributors.new_contributors_retention_rate,
        },
    }

    # Add topics
    if report.topics:
        data["topics"] = [
            {
                "id": t.id,
                "label": t.label,
                "keywords": t.keywords,
                "message_count": t.message_count,
                "percentage": t.percentage,
            }
            for t in report.topics
        ]

    # Add trends
    if report.trends:
        data["trends"] = {
            "comparison_period_current": report.trends.comparison_period_current,
            "comparison_period_previous": report.trends.comparison_period_previous,
            "metric_changes": [
                {
                    "metric": m.metric,
                    "current": m.current,
                    "previous": m.previous,
                    "change_pct": m.change_pct,
                    "significant": m.significant,
                }
                for m in report.trends.metric_changes
            ],
        }

    # Add benchmarks
    if report.benchmarks:
        data["benchmarks"] = {
            "source": report.benchmarks.source,
            "overall_assessment": report.benchmarks.overall_assessment.value,
            "score": report.benchmarks.score,
            "comparisons": [
                {
                    "metric": c.metric,
                    "value": c.value,
                    "status": c.status.value,
                }
                for c in report.benchmarks.comparisons
            ],
        }

    # Add recommendations
    if report.recommendations:
        data["recommendations"] = [
            {
                "id": r.id,
                "priority": r.priority.value,
                "category": r.category.value,
                "title": r.title,
                "description": r.description,
                "actions": r.actions,
            }
            for r in report.recommendations
        ]

    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _status_label(score: int) -> str:
    """Get status label from score."""
    if score >= 80:
        return "Healthy"
    elif score >= 60:
        return "Healthy"
    elif score >= 40:
        return "Warning"
    else:
        return "Critical"


def _status_emoji(score: int) -> str:
    """Get status emoji from score."""
    if score >= 60:
        return "✅"
    elif score >= 40:
        return "⚠️"
    else:
        return "❌"


def _generate_summary_highlights(report: HealthReport) -> List[str]:
    """Generate summary highlights for executive summary."""
    highlights = []

    # Daily active members
    if report.engagement.daily_active_members_percentage >= 10:
        highlights.append(f"✅ Daily active members ({report.engagement.daily_active_members_percentage:.1f}%) exceeds healthy threshold")
    else:
        highlights.append(f"⚠️ Daily active members ({report.engagement.daily_active_members_percentage:.1f}%) below healthy threshold")

    # Response rate
    if report.engagement.reply_rate >= 30:
        highlights.append(f"✅ Response rate ({report.engagement.reply_rate:.1f}%) indicates good engagement")
    else:
        highlights.append(f"⚠️ Response rate ({report.engagement.reply_rate:.1f}%) needs improvement")

    # Trends
    if report.trends and report.trends.highlights:
        for h in report.trends.highlights[:2]:
            emoji = "📈" if h.impact == "positive" else "📉"
            highlights.append(f"{emoji} {h.description}")

    # Recommendations
    high_recs = [r for r in report.recommendations if r.priority == RecommendationPriority.HIGH]
    if high_recs:
        highlights.append(f"🔔 {len(high_recs)} high-priority recommendation(s) to address")

    return highlights
