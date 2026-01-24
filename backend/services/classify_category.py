import re
from typing import Dict, Iterable, Set, Tuple

# The only categories we ever return.
CATEGORIES: Tuple[str, ...] = ("World", "Politics", "Business", "Technology", "Culture")

# Phrase matches are weighted higher than single-word matches.
PHRASE_WEIGHT = 3

# Keep phrases lowercase and without punctuation. We match them against normalized text.
PHRASES: Dict[str, Tuple[str, ...]] = {
    "World": (
        "united nations",
        "european union",
        "middle east",
        "peace talks",
        "cease fire",
        "border dispute",
        "foreign ministry",
    ),
    "Politics": (
        "white house",
        "supreme court",
        "government shutdown",
        "executive order",
        "campaign trail",
        "state of the union",
    ),
    "Business": (
        "stock market",
        "interest rates",
        "quarterly earnings",
        "federal reserve",
        "supply chain",
        "venture capital",
        "private equity",
        "merger talks",
        "initial public offering",
    ),
    "Technology": (
        "artificial intelligence",
        "machine learning",
        "data breach",
        "cyber attack",
        "open source",
        "cloud computing",
        "semiconductor",
    ),
    "Culture": (
        "box office",
        "award show",
        "red carpet",
        "music festival",
        "book review",
        "art exhibit",
        "video game",
    ),
}

# Single-token keywords. Use Sets for speed.
KEYWORDS: Dict[str, Set[str]] = {
    "World": {
        "war",
        "sanctions",
        "nato",
        "ukraine",
        "russia",
        "china",
        "taiwan",
        "israel",
        "gaza",
        "iran",
        "embassy",
        "refugee",
        "diplomacy",
        "foreign",
        "military",
    },
    "Politics": {
        "election",
        "vote",
        "voting",
        "congress",
        "senate",
        "house",
        "president",
        "governor",
        "mayor",
        "democrat",
        "republican",
        "bill",
        "legislation",
        "court",
        "supreme",
        "campaign",
        "shutdown",
    },
    "Business": {
        "stocks",
        "shares",
        "earnings",
        "revenue",
        "profit",
        "inflation",
        "tariffs",
        "market",
        "markets",
        "bank",
        "banking",
        "deal",
        "merger",
        "acquisition",
        "ipo",
        "economy",
        "oil",
        "jobs",
        "unemployment",
    },
    "Technology": {
        "ai",
        "software",
        "hardware",
        "chip",
        "chips",
        "semiconductor",
        "cybersecurity",
        "hack",
        "hacker",
        "breach",
        "robot",
        "startup",
        "app",
        "apps",
        "cloud",
        "data",
        "privacy",
        "google",
        "apple",
        "microsoft",
        "meta",
        "tesla",
    },
    "Culture": {
        "film",
        "movie",
        "music",
        "album",
        "concert",
        "festival",
        "fashion",
        "art",
        "museum",
        "theater",
        "television",
        "tv",
        "celebrity",
        "sports",
        "game",
        "games",
        "book",
        "books",
    },
}

_non_alnum = re.compile(r"[^a-z0-9\s]+")
_ws = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """
    Lowercase and remove punctuation (keep alnum + spaces), collapse whitespace.
    """
    if not text:
        return ""
    text = text.lower()
    text = _non_alnum.sub(" ", text)
    text = _ws.sub(" ", text).strip()
    return text


def _score_phrases(padded_text: str, phrases: Iterable[str]) -> int:
    score = 0
    for phrase in phrases:
        # Exact-ish phrase match via space padding to avoid substring issues.
        if f" {phrase} " in padded_text:
            score += PHRASE_WEIGHT
    return score


def classify_category(headline: str, subtext: str) -> str:
    """
    Deterministic, synchronous classifier.
    Returns exactly one of: World, Politics, Business, Technology, Culture.

    Culture is the default when:
    - no keywords/phrases match, OR
    - there is a tie for the top score.
    """
    normalized = _normalize(f"{headline or ''} {subtext or ''}")
    if not normalized:
        return "Culture"

    padded = f" {normalized} "
    tokens = set(normalized.split())

    scores = {cat: 0 for cat in CATEGORIES}
    for cat in CATEGORIES:
        scores[cat] += _score_phrases(padded, PHRASES.get(cat, ()))
        scores[cat] += len(tokens & KEYWORDS.get(cat, set()))

    best_score = max(scores.values())
    if best_score <= 0:
        return "Culture"

    best = [cat for cat, score in scores.items() if score == best_score]
    return best[0] if len(best) == 1 else "Culture"

