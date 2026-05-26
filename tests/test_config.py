from app.config import DEFAULT_RSS_FEEDS


def test_default_rss_feeds_keep_cshub_feeds_separate() -> None:
    assert "https://www.cshub.com/rss/categories/attacks" in DEFAULT_RSS_FEEDS
    assert "https://www.cshub.com/rss/categories/malware" in DEFAULT_RSS_FEEDS
    assert all(url.startswith("https://") for url in DEFAULT_RSS_FEEDS)
