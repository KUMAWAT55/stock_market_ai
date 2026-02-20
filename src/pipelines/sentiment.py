import re
from html import unescape


POSITIVE_WORDS = {
    "beat", "beats", "bullish", "buy", "growth", "gains", "gain", "up",
    "upgrade", "outperform", "record", "strong", "surge", "profit", "profits",
    "expands", "expansion", "rally", "optimistic", "improves", "improved",
    "positive", "recovery", "momentum", "raises", "rise", "rises",
}

NEGATIVE_WORDS = {
    "miss", "misses", "bearish", "sell", "drop", "drops", "down", "downgrade",
    "underperform", "weak", "slump", "loss", "losses", "falls", "fall",
    "decline", "declines", "warning", "cuts", "cut", "negative", "risk",
    "lawsuit", "fraud", "default", "concern", "concerns",
}


def _clean_text(text: str) -> str:
    if not text:
        return ""
    cleaned = unescape(text)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"http[s]?://\S+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def analyze_news_sentiment(title: str, summary: str) -> tuple[float, str]:
    text = _clean_text(f"{title or ''} {summary or ''}")
    if not text:
        return 0.0, "neutral"

    tokens = re.findall(r"[a-z]+", text)
    if not tokens:
        return 0.0, "neutral"

    pos = sum(1 for token in tokens if token in POSITIVE_WORDS)
    neg = sum(1 for token in tokens if token in NEGATIVE_WORDS)

    if pos == 0 and neg == 0:
        return 0.0, "neutral"

    score = (pos - neg) / float(pos + neg)
    score = max(min(score, 1.0), -1.0)

    if score >= 0.2:
        label = "positive"
    elif score <= -0.2:
        label = "negative"
    else:
        label = "neutral"

    return round(score, 4), label
