import feedparser
import requests
import re
import base64

from loguru import logger
from datetime import datetime
from newspaper import Article
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
}


# ---------------------------------------
# 1. Extract href from HTML
# ---------------------------------------

def extract_href(text: str):

    match = re.search(r'href="([^"]+)"', text)

    if match:
        return match.group(1)

    return text


# ---------------------------------------
# 2. Decode Google encoded URLs
# ---------------------------------------

def decode_google_url(url: str):

    try:
        if "/articles/" not in url:
            return url

        encoded = url.split("/articles/")[-1]

        decoded = base64.urlsafe_b64decode(
            encoded + "=="
        ).decode("utf-8", errors="ignore")

        match = re.search(r"https?://[^\s]+", decoded)

        if match:
            return match.group(0)

        return url

    except Exception:
        return url


# ---------------------------------------
# 3. Resolve redirect
# ---------------------------------------

def resolve_redirect(url: str):

    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=15,
            allow_redirects=True
        )

        return r.url

    except Exception as e:
        logger.warning(f"Redirect failed: {e}")
        return None


# ---------------------------------------
# 4. Extract article text
# ---------------------------------------

def extract_article_text(url: str):

    # -----------------------------
    # Try newspaper first
    # -----------------------------
    try:
        article = Article(url)
        article.download()
        article.parse()

        text = article.text.strip()

        if text and len(text) > 100:
            return text

    except Exception:
        pass


    # -----------------------------
    # Fallback: BeautifulSoup
    # -----------------------------
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        soup = BeautifulSoup(r.text, "lxml")

        paragraphs = soup.find_all("p")

        text = " ".join(
            p.get_text().strip()
            for p in paragraphs
            if len(p.get_text().strip()) > 40
        )

        if text and len(text) > 100:
            return text

    except Exception as e:
        logger.warning(f"Fallback failed {url}: {e}")

    return None

# ---------------------------------------
# 5. Main Fetcher
# ---------------------------------------

def fetch_news(symbol: str, limit=10):

    logger.info(f"Fetching news for {symbol}")

    query = symbol.replace(" ", "+")

    rss_url = f"https://news.google.com/rss/search?q={query}"

    feed = feedparser.parse(rss_url)

    logger.info(f"RSS entries found: {len(feed.entries)}")

    news_list = []

    for i, entry in enumerate(feed.entries[:limit]):

        try:

            logger.info(f"Processing: {entry.title}")

            # STEP 1: Extract href
            raw_link = extract_href(entry.link)

            # STEP 2: Decode Google wrapper
            decoded_url = decode_google_url(raw_link)

            # STEP 3: Resolve redirect
            final_url = resolve_redirect(decoded_url)

            if not final_url:
                logger.warning("No final URL")
                continue

            logger.info(f"Resolved: {final_url}")

            # STEP 4: Extract content
            article_text = extract_article_text(final_url)

            if not article_text:
                logger.warning("Empty article")
                continue

            logger.info(f"Length: {len(article_text)}")

            if len(article_text) < 80:
                logger.warning("Too short")
                continue

            news = {
                "symbol": symbol,
                "title": entry.title,
                "content": article_text,
                "url": final_url,
                "source": "google_news",
                "published_at": datetime(*entry.published_parsed[:6])
            }

            news_list.append(news)

            logger.success("Added ✅")

        except Exception as e:
            logger.warning(f"Skipping: {e}")

    logger.info(f"Fetched {len(news_list)} full articles")

    return news_list
