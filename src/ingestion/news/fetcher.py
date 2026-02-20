import requests
import feedparser
from email.utils import parsedate_to_datetime
from datetime import timezone

from src.pipelines.sentiment import analyze_news_sentiment


def fetch_news(company_name: str, max_results: int = 5) -> list:
    """
    Fetch news using Google News RSS feed (no API key required).
    """
    query = f"{company_name} NSE stock"
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-IN&gl=IN&ceid=IN:en"

    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:max_results]:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            score, label = analyze_news_sentiment(title, summary)

            published_raw = entry.get("published")
            published_at = None
            if published_raw:
                try:
                    parsed = parsedate_to_datetime(published_raw)
                    if parsed.tzinfo:
                        published_at = parsed.astimezone(timezone.utc).replace(tzinfo=None)
                    else:
                        published_at = parsed
                except Exception:
                    published_at = None

            articles.append({
                "symbol": company_name,
                "title": title,
                "url": entry.get("link", ""),
                "published_at": published_at,
                "source": entry.get("source", {}).get("title", "Google News"),
                "summary": summary,
                "sentiment_score": score,
                "sentiment_label": label,
            })
        return articles
    except Exception as e:
        print(f"  RSS error for {company_name}: {e}")
        return []
