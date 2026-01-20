#!/usr/bin/env python3
"""
Fuzzy search engine for member profiles.

Uses rapidfuzz for high-performance fuzzy text matching.

Usage:
    from lib.fuzzy_search import FuzzySearchEngine, SearchQuery

    engine = FuzzySearchEngine(profiles)
    results = engine.search("gamers who joined recently")
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    fuzz = None  # type: ignore
    RAPIDFUZZ_AVAILABLE = False

from .profile_models import UnifiedMemberProfile
from .member_models import MemberBasic


class MatchField(Enum):
    """Fields that can be matched in search."""
    USERNAME = "username"
    DISPLAY_NAME = "display_name"
    BIO = "bio"
    ROLES = "roles"
    INTERESTS = "interests"
    KEYWORDS = "keywords"
    EXPERTISE = "expertise"
    CONNECTED_ACCOUNTS = "connected_accounts"


@dataclass
class MatchReason:
    """Explains why a result matched the query."""
    field: MatchField
    matched_term: str
    query_term: str
    score: float  # 0-100

    def __str__(self) -> str:
        return f"{self.field.value}: '{self.matched_term}' matched '{self.query_term}' ({self.score:.0f}%)"


@dataclass
class SearchResult:
    """A single search result with match details."""
    profile: UnifiedMemberProfile
    relevance_score: float  # 0-100 composite score
    match_reasons: list[MatchReason] = field(default_factory=list)

    @property
    def top_match_reason(self) -> Optional[MatchReason]:
        """Get the highest-scoring match reason."""
        if not self.match_reasons:
            return None
        return max(self.match_reasons, key=lambda r: r.score)


@dataclass
class SearchQuery:
    """Parsed search query with filters."""
    text_query: str = ""
    role_filter: Optional[str] = None
    joined_since: Optional[datetime] = None
    joined_before: Optional[datetime] = None
    engagement_tier: Optional[str] = None  # silent/lurker/occasional/active/champion
    min_score_threshold: float = 60.0
    max_results: int = 50

    @classmethod
    def from_natural_language(cls, query: str) -> "SearchQuery":
        """
        Parse natural language query into structured filters.

        Examples:
            "gamers" -> text_query="gamers"
            "developers joined last week" -> text_query="developers", joined_since=7 days ago
            "active members with moderator role" -> engagement_tier="active", role_filter="moderator"
        """
        parsed = cls()
        remaining_terms = []

        # Tokenize
        tokens = query.lower().split()
        i = 0

        while i < len(tokens):
            token = tokens[i]

            # Parse "joined last X" patterns
            if token == "joined" and i + 2 < len(tokens):
                if tokens[i + 1] == "last":
                    period = tokens[i + 2]
                    if period in ("week", "7d", "7days"):
                        parsed.joined_since = datetime.now(timezone.utc) - timedelta(days=7)
                        i += 3
                        continue
                    elif period in ("month", "30d", "30days"):
                        parsed.joined_since = datetime.now(timezone.utc) - timedelta(days=30)
                        i += 3
                        continue
                    elif period in ("year", "365d"):
                        parsed.joined_since = datetime.now(timezone.utc) - timedelta(days=365)
                        i += 3
                        continue

            # Parse "since Xd" patterns
            if token == "since" and i + 1 < len(tokens):
                next_token = tokens[i + 1]
                match = re.match(r"(\d+)d?", next_token)
                if match:
                    days = int(match.group(1))
                    parsed.joined_since = datetime.now(timezone.utc) - timedelta(days=days)
                    i += 2
                    continue

            # Parse "with X role" patterns
            if token == "with" and i + 2 < len(tokens) and tokens[i + 2] == "role":
                parsed.role_filter = tokens[i + 1]
                i += 3
                continue

            # Parse "role:X" patterns
            if token.startswith("role:"):
                parsed.role_filter = token[5:]
                i += 1
                continue

            # Parse engagement tier keywords
            if token in ("silent", "lurker", "occasional", "active", "champion"):
                parsed.engagement_tier = token
                i += 1
                continue

            # Parse "active members" pattern
            if token == "active" and i + 1 < len(tokens) and tokens[i + 1] == "members":
                parsed.engagement_tier = "active"
                i += 2
                continue

            # Skip filler words
            if token in ("members", "users", "people", "who", "are", "the", "a", "an", "in", "on"):
                i += 1
                continue

            remaining_terms.append(token)
            i += 1

        parsed.text_query = " ".join(remaining_terms)
        return parsed


class FuzzySearchEngine:
    """
    High-performance fuzzy search engine for member profiles.

    Searches across multiple fields with configurable weights.
    """

    # Field weights for relevance scoring
    FIELD_WEIGHTS = {
        MatchField.USERNAME: 1.5,
        MatchField.DISPLAY_NAME: 1.5,
        MatchField.BIO: 1.2,
        MatchField.ROLES: 1.3,
        MatchField.INTERESTS: 1.4,
        MatchField.KEYWORDS: 1.4,
        MatchField.EXPERTISE: 1.3,
        MatchField.CONNECTED_ACCOUNTS: 1.0,
    }

    def __init__(self, profiles: list[UnifiedMemberProfile]):
        """
        Initialize search engine with profiles to search.

        Args:
            profiles: List of unified member profiles
        """
        self.profiles = profiles
        self._build_index()

    def _build_index(self) -> None:
        """Build searchable text index for each profile."""
        self._index: dict[str, dict[MatchField, list[str]]] = {}

        for profile in self.profiles:
            user_id = profile.user_id
            self._index[user_id] = {}

            # Username and display name
            self._index[user_id][MatchField.USERNAME] = [profile.username.lower()]
            self._index[user_id][MatchField.DISPLAY_NAME] = [profile.display_name.lower()]

            # Bio
            if profile.discord_data.bio:
                # Split bio into searchable terms
                bio_terms = self._extract_terms(profile.discord_data.bio)
                self._index[user_id][MatchField.BIO] = bio_terms

            # Roles (from all servers)
            roles = []
            for server in profile.discord_data.servers:
                roles.extend([r.lower() for r in server.roles])
            self._index[user_id][MatchField.ROLES] = list(set(roles))

            # Inferred interests
            if profile.derived_insights.inferred_interests:
                interests = [ii.interest.lower() for ii in profile.derived_insights.inferred_interests]
                self._index[user_id][MatchField.INTERESTS] = interests

            # Keywords from behavioral data
            if profile.behavioral_data.keywords:
                self._index[user_id][MatchField.KEYWORDS] = [k.lower() for k in profile.behavioral_data.keywords]

            # Expertise tags
            if profile.derived_insights.expertise_tags:
                self._index[user_id][MatchField.EXPERTISE] = [t.lower() for t in profile.derived_insights.expertise_tags]

            # Connected accounts (platform names)
            if profile.discord_data.connected_accounts:
                platforms = [ca.platform.lower() for ca in profile.discord_data.connected_accounts]
                self._index[user_id][MatchField.CONNECTED_ACCOUNTS] = platforms

    def _extract_terms(self, text: str) -> list[str]:
        """Extract searchable terms from text."""
        # Remove special characters and split
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        terms = text.split()
        # Filter short terms and common words
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                     "have", "has", "had", "do", "does", "did", "will", "would", "could",
                     "should", "may", "might", "must", "shall", "can", "to", "of", "in",
                     "for", "on", "with", "at", "by", "from", "as", "into", "through",
                     "and", "or", "but", "if", "then", "else", "when", "up", "down",
                     "out", "off", "over", "under", "again", "further", "once", "here",
                     "there", "all", "each", "few", "more", "most", "other", "some",
                     "such", "no", "nor", "not", "only", "own", "same", "so", "than",
                     "too", "very", "just", "i", "me", "my", "we", "our", "you", "your",
                     "he", "him", "his", "she", "her", "it", "its", "they", "them", "their"}
        return [t for t in terms if len(t) > 2 and t not in stopwords]

    def search(self, query: SearchQuery | str) -> list[SearchResult]:
        """
        Search profiles matching the query.

        Args:
            query: SearchQuery object or natural language string

        Returns:
            List of SearchResult sorted by relevance (highest first)
        """
        if isinstance(query, str):
            query = SearchQuery.from_natural_language(query)

        results: list[SearchResult] = []

        for profile in self.profiles:
            # Apply filters first
            if not self._matches_filters(profile, query):
                continue

            # If no text query, include all filtered results with base score
            if not query.text_query:
                results.append(SearchResult(
                    profile=profile,
                    relevance_score=50.0,  # Base score for filter-only matches
                    match_reasons=[]
                ))
                continue

            # Fuzzy match against text query
            match_reasons = self._fuzzy_match_profile(profile, query.text_query)

            if match_reasons:
                # Calculate composite relevance score
                relevance_score = self._calculate_relevance(match_reasons)

                if relevance_score >= query.min_score_threshold:
                    results.append(SearchResult(
                        profile=profile,
                        relevance_score=relevance_score,
                        match_reasons=match_reasons
                    ))

        # Sort by relevance
        results.sort(key=lambda r: r.relevance_score, reverse=True)

        # Limit results
        return results[:query.max_results]

    def _matches_filters(self, profile: UnifiedMemberProfile, query: SearchQuery) -> bool:
        """Check if profile matches all query filters."""
        # Role filter
        if query.role_filter:
            has_role = False
            role_filter_lower = query.role_filter.lower()
            for server in profile.discord_data.servers:
                for role in server.roles:
                    if role_filter_lower in role.lower():
                        has_role = True
                        break
                if has_role:
                    break
            if not has_role:
                return False

        # Join date filters
        if query.joined_since or query.joined_before:
            # Get earliest join date across servers
            join_date = None
            for server in profile.discord_data.servers:
                if server.joined_at:
                    if join_date is None or server.joined_at < join_date:
                        join_date = server.joined_at

            if join_date:
                if query.joined_since and join_date < query.joined_since:
                    return False
                if query.joined_before and join_date > query.joined_before:
                    return False
            elif query.joined_since or query.joined_before:
                # No join date data but filter requires it
                return False

        # Engagement tier filter
        if query.engagement_tier:
            tier = profile.derived_insights.engagement_tier.value.lower()
            if tier != query.engagement_tier.lower():
                return False

        return True

    def _fuzzy_match_profile(self, profile: UnifiedMemberProfile, text_query: str) -> list[MatchReason]:
        """Perform fuzzy matching against profile fields."""
        match_reasons: list[MatchReason] = []
        query_terms = text_query.lower().split()
        user_id = profile.user_id

        if user_id not in self._index:
            return []

        for field, terms in self._index[user_id].items():
            if not terms:
                continue

            for query_term in query_terms:
                for term in terms:
                    # Calculate fuzzy similarity
                    if RAPIDFUZZ_AVAILABLE and fuzz is not None:
                        score = fuzz.ratio(query_term, term)
                        # Also check partial ratio for substring matches
                        partial_score = fuzz.partial_ratio(query_term, term)
                        score = max(score, partial_score * 0.9)  # Slight penalty for partial
                    else:
                        # Fallback: simple substring matching
                        if query_term in term or term in query_term:
                            score = 80.0
                        elif query_term[:3] == term[:3]:  # Prefix match
                            score = 60.0
                        else:
                            score = 0.0

                    if score >= 60:  # Minimum match threshold
                        match_reasons.append(MatchReason(
                            field=field,
                            matched_term=term,
                            query_term=query_term,
                            score=score
                        ))

        return match_reasons

    def _calculate_relevance(self, match_reasons: list[MatchReason]) -> float:
        """Calculate composite relevance score from match reasons."""
        if not match_reasons:
            return 0.0

        # Group by field and take best match per field
        field_scores: dict[MatchField, float] = {}
        for reason in match_reasons:
            weighted_score = reason.score * self.FIELD_WEIGHTS.get(reason.field, 1.0)
            if reason.field not in field_scores or weighted_score > field_scores[reason.field]:
                field_scores[reason.field] = weighted_score

        # Combine field scores
        # Use a formula that rewards multiple field matches
        if len(field_scores) == 1:
            return list(field_scores.values())[0]

        # Average of scores with bonus for multiple matches
        avg_score = sum(field_scores.values()) / len(field_scores)
        multi_match_bonus = min(10 * (len(field_scores) - 1), 20)  # Up to +20 for multiple matches

        return min(avg_score + multi_match_bonus, 100.0)


def search_members(
    profiles: list[UnifiedMemberProfile],
    query: str,
    max_results: int = 50,
    min_score: float = 60.0
) -> list[SearchResult]:
    """
    Convenience function to search member profiles.

    Args:
        profiles: List of profiles to search
        query: Natural language search query
        max_results: Maximum results to return
        min_score: Minimum relevance score (0-100)

    Returns:
        List of SearchResult sorted by relevance
    """
    engine = FuzzySearchEngine(profiles)
    search_query = SearchQuery.from_natural_language(query)
    search_query.max_results = max_results
    search_query.min_score_threshold = min_score
    return engine.search(search_query)


def search_basic_members(
    members: list[MemberBasic],
    query: str,
    max_results: int = 50,
) -> list[tuple[MemberBasic, float, list[str]]]:
    """
    Search basic member data without full profiles.

    Returns tuples of (member, score, match_fields).
    """
    results = []
    query_lower = query.lower()
    query_terms = query_lower.split()

    for member in members:
        match_fields = []
        total_score = 0.0

        # Search username
        for term in query_terms:
            if RAPIDFUZZ_AVAILABLE and fuzz is not None:
                score = fuzz.partial_ratio(term, member.username.lower())
            else:
                score = 80.0 if term in member.username.lower() else 0.0

            if score >= 60:
                match_fields.append(f"username: {member.username}")
                total_score = max(total_score, score)

        # Search display name
        for term in query_terms:
            if RAPIDFUZZ_AVAILABLE and fuzz is not None:
                score = fuzz.partial_ratio(term, member.display_name.lower())
            else:
                score = 80.0 if term in member.display_name.lower() else 0.0

            if score >= 60:
                match_fields.append(f"display_name: {member.display_name}")
                total_score = max(total_score, score)

        # Search roles
        for role in member.roles:
            for term in query_terms:
                if RAPIDFUZZ_AVAILABLE and fuzz is not None:
                    score = fuzz.partial_ratio(term, role.lower())
                else:
                    score = 80.0 if term in role.lower() else 0.0

                if score >= 60:
                    match_fields.append(f"role: {role}")
                    total_score = max(total_score, score * 0.9)  # Slight penalty for role matches

        if match_fields:
            results.append((member, total_score, list(set(match_fields))))

    # Sort by score descending
    results.sort(key=lambda x: x[1], reverse=True)

    return results[:max_results]
