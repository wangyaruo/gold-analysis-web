from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class SentimentResult:
    label: str
    score: int
    positive_hits: list[str]
    negative_hits: list[str]
    article_count: int


def _article_text(article: Mapping[str, object]) -> str:
    parts = [
        str(article.get("title") or ""),
        str(article.get("description") or ""),
        str(article.get("content") or ""),
    ]
    return " ".join(parts).lower()


def _matches(text: str, keywords: Iterable[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword.lower() in text]


def analyze_news_sentiment(
    articles: Iterable[Mapping[str, object]],
    rules: Mapping[str, object],
) -> SentimentResult:
    article_list = list(articles)
    positive_keywords = list(rules.get("positive_keywords", []))
    negative_keywords = list(rules.get("negative_keywords", []))
    positive_threshold = int(rules.get("positive_threshold", 2))
    negative_threshold = int(rules.get("negative_threshold", -2))

    positive_hits: list[str] = []
    negative_hits: list[str] = []
    for article in article_list:
        text = _article_text(article)
        article_positive_hits = _matches(text, positive_keywords)
        article_negative_hits = _matches(text, negative_keywords)
        positive_hits.extend(article_positive_hits)
        if article_negative_hits:
            negative_hits.append(article_negative_hits[0])

    score = len(positive_hits) - len(negative_hits)
    if score >= positive_threshold:
        label = "positive"
    elif score <= negative_threshold:
        label = "negative"
    else:
        label = "neutral"

    return SentimentResult(
        label=label,
        score=score,
        positive_hits=positive_hits,
        negative_hits=negative_hits,
        article_count=len(article_list),
    )
