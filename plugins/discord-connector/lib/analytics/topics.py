"""Topic clustering for Discord Community Health Analytics.

Implements TF-IDF-like keyword extraction and topic clustering
without external dependencies (pure Python stdlib).
"""

import re
import math
from collections import Counter, defaultdict
from typing import Dict, List, Set, Tuple

from .models import (
    Sentiment,
    TopContributor,
    TopicCluster,
    TopicTrend,
)
from .parser import ParsedMessage


# English stopwords (common words to filter out)
STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "about", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "can", "will", "just", "don", "should", "now", "i", "me", "my", "myself",
    "we", "our", "ours", "ourselves", "you", "your", "yours", "yourself",
    "yourselves", "he", "him", "his", "himself", "she", "her", "hers",
    "herself", "it", "its", "itself", "they", "them", "their", "theirs",
    "themselves", "what", "which", "who", "whom", "this", "that", "these",
    "those", "am", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having", "do", "does", "did", "doing", "would",
    "could", "ought", "im", "youre", "hes", "shes", "its", "were", "theyre",
    "ive", "youve", "weve", "theyve", "id", "youd", "hed", "shed", "wed",
    "theyd", "ill", "youll", "hell", "shell", "well", "theyll", "isnt",
    "arent", "wasnt", "werent", "hasnt", "havent", "hadnt", "doesnt",
    "dont", "didnt", "wont", "wouldnt", "shouldnt", "cant", "couldnt",
    "mustnt", "lets", "thats", "whos", "whats", "heres", "theres", "whens",
    "wheres", "whys", "hows", "because", "as", "until", "while", "of",
    "against", "although", "otherwise", "however", "thus", "since",
    "unless", "meanwhile", "yet", "still", "also", "already", "always",
    "never", "ever", "maybe", "perhaps", "probably", "actually", "really",
    "basically", "literally", "definitely", "certainly", "obviously",
    "lol", "lmao", "yeah", "yes", "no", "ok", "okay", "hey", "hi", "hello",
    "thanks", "thank", "please", "sorry", "oh", "um", "uh", "hmm", "like",
    "just", "get", "got", "go", "going", "gone", "come", "coming", "came",
    "see", "seeing", "saw", "seen", "know", "knowing", "knew", "known",
    "think", "thinking", "thought", "make", "making", "made", "take",
    "taking", "took", "taken", "give", "giving", "gave", "given", "find",
    "finding", "found", "tell", "telling", "told", "ask", "asking", "asked",
    "use", "using", "used", "try", "trying", "tried", "need", "needing",
    "needed", "want", "wanting", "wanted", "look", "looking", "looked",
    "one", "two", "three", "four", "five", "first", "second", "third",
    "last", "next", "new", "old", "good", "bad", "great", "right", "left",
    "bit", "way", "thing", "things", "stuff", "lot", "lots", "kind", "sort",
    "type", "much", "many", "something", "anything", "nothing", "everything",
    "someone", "anyone", "everyone", "nobody", "everybody", "people",
    "person", "time", "day", "days", "week", "weeks", "month", "months",
    "year", "years", "today", "tomorrow", "yesterday",
}

# Minimum word length to consider
MIN_WORD_LENGTH = 3

# Maximum topics to generate (excluding "Other")
MAX_TOPICS = 10

# Minimum messages for a topic to be considered
MIN_TOPIC_MESSAGES = 10


def preprocess_text(text: str) -> List[str]:
    """Preprocess text for topic extraction.

    Args:
        text: Raw message content.

    Returns:
        List of cleaned, lowercase tokens.
    """
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)

    # Remove mentions (@username)
    text = re.sub(r'@\w+', '', text)

    # Remove Discord emoji codes (:emoji:)
    text = re.sub(r':\w+:', '', text)

    # Remove special characters, keep only alphanumeric and spaces
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)

    # Lowercase and split
    words = text.lower().split()

    # Filter stopwords and short words
    tokens = [
        word for word in words
        if word not in STOPWORDS and len(word) >= MIN_WORD_LENGTH
    ]

    return tokens


def calculate_tf(documents: List[List[str]]) -> List[Dict[str, float]]:
    """Calculate term frequency for each document.

    Args:
        documents: List of tokenized documents.

    Returns:
        List of TF dictionaries.
    """
    tf_list = []
    for doc in documents:
        word_count = Counter(doc)
        total_words = len(doc) if doc else 1
        tf = {word: count / total_words for word, count in word_count.items()}
        tf_list.append(tf)
    return tf_list


def calculate_idf(documents: List[List[str]]) -> Dict[str, float]:
    """Calculate inverse document frequency.

    Args:
        documents: List of tokenized documents.

    Returns:
        IDF dictionary.
    """
    n_docs = len(documents)
    if n_docs == 0:
        return {}

    # Count document frequency for each word
    df: Dict[str, int] = defaultdict(int)
    for doc in documents:
        unique_words = set(doc)
        for word in unique_words:
            df[word] += 1

    # Calculate IDF
    idf = {}
    for word, freq in df.items():
        idf[word] = math.log(n_docs / (1 + freq))

    return idf


def extract_keywords(
    messages: List[ParsedMessage],
    top_n: int = 100
) -> List[Tuple[str, float]]:
    """Extract top keywords from messages using TF-IDF.

    Args:
        messages: List of parsed messages.
        top_n: Number of top keywords to extract.

    Returns:
        List of (keyword, score) tuples.
    """
    if not messages:
        return []

    # Tokenize all messages
    documents = [preprocess_text(msg.content) for msg in messages]

    # Calculate TF-IDF
    tf_list = calculate_tf(documents)
    idf = calculate_idf(documents)

    # Aggregate TF-IDF scores across all documents
    keyword_scores: Dict[str, float] = defaultdict(float)
    for tf in tf_list:
        for word, tf_score in tf.items():
            if word in idf:
                keyword_scores[word] += tf_score * idf[word]

    # Sort by score
    sorted_keywords = sorted(
        keyword_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return sorted_keywords[:top_n]


def cluster_messages_by_topic(
    messages: List[ParsedMessage],
    max_topics: int = MAX_TOPICS,
    min_messages: int = MIN_TOPIC_MESSAGES,
) -> List[TopicCluster]:
    """Cluster messages into topics based on keywords.

    Args:
        messages: List of parsed messages.
        max_topics: Maximum number of topics to generate.
        min_messages: Minimum messages for a topic.

    Returns:
        List of TopicCluster objects (including "Other" bucket).
    """
    if not messages:
        return []

    # Extract top keywords
    keywords = extract_keywords(messages, top_n=200)
    if not keywords:
        return [_create_other_topic(messages, 1)]

    # Get top keywords for clustering
    cluster_keywords = [kw for kw, _ in keywords[:50]]

    # Assign messages to clusters based on keyword presence
    # Each message gets assigned to the first matching cluster keyword
    clusters: Dict[str, List[ParsedMessage]] = defaultdict(list)
    unassigned: List[ParsedMessage] = []

    for msg in messages:
        tokens = set(preprocess_text(msg.content))
        assigned = False

        for keyword in cluster_keywords:
            if keyword in tokens:
                clusters[keyword].append(msg)
                assigned = True
                break

        if not assigned:
            unassigned.append(msg)

    # Merge small clusters and build final topics
    topic_clusters: List[TopicCluster] = []
    topic_id = 1
    used_keywords: Set[str] = set()

    for keyword in cluster_keywords:
        if keyword in used_keywords:
            continue

        if len(clusters[keyword]) < min_messages:
            continue

        # Find related keywords for this cluster
        cluster_msgs = clusters[keyword]
        related_keywords = _find_related_keywords(cluster_msgs, used_keywords)

        # Create topic
        all_keywords = [keyword] + related_keywords[:4]
        label = _generate_topic_label(all_keywords)

        topic = _create_topic_cluster(
            topic_id=topic_id,
            label=label,
            keywords=all_keywords,
            messages=cluster_msgs,
            total_messages=len(messages),
        )

        topic_clusters.append(topic)
        used_keywords.add(keyword)
        used_keywords.update(related_keywords)
        topic_id += 1

        if len(topic_clusters) >= max_topics:
            break

    # Add "Other" bucket for remaining messages
    other_messages = unassigned.copy()
    for keyword, msgs in clusters.items():
        if keyword not in used_keywords:
            other_messages.extend(msgs)

    if other_messages:
        topic_clusters.append(_create_other_topic(other_messages, topic_id))

    return topic_clusters


def _find_related_keywords(
    messages: List[ParsedMessage],
    exclude: Set[str]
) -> List[str]:
    """Find related keywords within a cluster.

    Args:
        messages: Messages in the cluster.
        exclude: Keywords to exclude.

    Returns:
        List of related keywords.
    """
    # Extract keywords from cluster messages
    cluster_keywords = extract_keywords(messages, top_n=20)

    return [
        kw for kw, _ in cluster_keywords
        if kw not in exclude
    ]


def _generate_topic_label(keywords: List[str]) -> str:
    """Generate a human-readable label from keywords.

    Args:
        keywords: List of keywords.

    Returns:
        Topic label string.
    """
    if not keywords:
        return "General Discussion"

    # Capitalize first keyword
    label = keywords[0].capitalize()

    # Add secondary keyword if meaningful
    if len(keywords) > 1:
        label = f"{label} {keywords[1].capitalize()}"

    return label


def _create_topic_cluster(
    topic_id: int,
    label: str,
    keywords: List[str],
    messages: List[ParsedMessage],
    total_messages: int,
) -> TopicCluster:
    """Create a TopicCluster from messages.

    Args:
        topic_id: Topic identifier.
        label: Topic label.
        keywords: Topic keywords.
        messages: Messages in this topic.
        total_messages: Total messages for percentage.

    Returns:
        TopicCluster object.
    """
    message_count = len(messages)
    percentage = (message_count / total_messages * 100) if total_messages else 0

    # Get channels
    channels = list(set(msg.channel_name for msg in messages if msg.channel_name))

    # Get top contributors
    author_counts: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "name": ""})
    for msg in messages:
        author_counts[msg.author_id]["count"] += 1
        author_counts[msg.author_id]["name"] = msg.author_name

    top_contributors = [
        TopContributor(
            author_id=author_id,
            author_name=data["name"],
            message_count=data["count"],
            percentage=round((data["count"] / message_count) * 100, 1),
        )
        for author_id, data in sorted(
            author_counts.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )[:5]
    ]

    # Sample messages (first 100 chars of content)
    sample_messages = [
        msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
        for msg in messages[:3]
        if msg.content.strip()
    ]

    return TopicCluster(
        id=topic_id,
        label=label,
        keywords=keywords,
        message_count=message_count,
        percentage=round(percentage, 1),
        channels=channels[:5],
        top_contributors=top_contributors,
        sample_messages=sample_messages,
        sentiment=Sentiment.NEUTRAL,
        trend=TopicTrend.STABLE,
    )


def _create_other_topic(
    messages: List[ParsedMessage],
    topic_id: int,
) -> TopicCluster:
    """Create the "Other" bucket topic.

    Args:
        messages: Unassigned messages.
        topic_id: Topic identifier.

    Returns:
        TopicCluster for "Other".
    """
    return _create_topic_cluster(
        topic_id=topic_id,
        label="Other",
        keywords=["miscellaneous"],
        messages=messages,
        total_messages=len(messages),
    )
