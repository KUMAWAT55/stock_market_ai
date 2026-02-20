import requests
import feedparser
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
            print("start*****************")
            for key in entry:
                print ( key ,">>>", entry[key])
            print("end*****************")

            articles.append({
                "symbol": company_name,
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "published_at": entry.get("published", ""),
                "source": entry.get("source", {}).get("title", "Google News"),
                "summary":entry.get("summary")
            })
        return articles
    except Exception as e:
        print(f"  RSS error for {company_name}: {e}")
        return []

