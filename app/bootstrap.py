"""Application bootstrap and initialization."""

import logging
from datetime import datetime

from app.config import get_settings
from app.database import init_db

logger = logging.getLogger(__name__)


class BootstrapError(Exception):
    """Raised when bootstrap fails."""
    pass


def setup_logging() -> None:
    """Configure logging for the application."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def validate_config() -> None:
    """Validate application configuration."""
    settings = get_settings()
    errors = []

    # Validate database URL
    if not settings.database_url:
        errors.append("DATABASE_URL is not configured")

    # Validate API tokens if sources are enabled
    if settings.enable_github and not settings.github_token:
        logger.warning("GitHub source enabled but GITHUB_TOKEN not set (rate limits reduced)")

    if settings.enable_x and not settings.x_bearer_token:
        logger.info("X/Twitter source enabled but X_BEARER_TOKEN not set (collector disabled)")

    if settings.enable_x_feed and not settings.x_feed_urls:
        errors.append("X feed source enabled but no X_FEED_URLS configured")

    if settings.enable_rss and not settings.rss_feed_urls:
        errors.append("RSS source enabled but no RSS feed URLs configured")

    # Validate Discord webhook if needed
    if settings.discord_webhook_url and not settings.discord_webhook_url.startswith("https://"):
        errors.append("DISCORD_WEBHOOK_URL must be a valid HTTPS URL")

    # Validate numeric settings
    if settings.collection_interval_minutes < 1:
        errors.append("COLLECTION_INTERVAL_MINUTES must be >= 1")

    if settings.alert_score_threshold < 0:
        errors.append("ALERT_SCORE_THRESHOLD must be >= 0")

    if settings.max_results_per_source < 1:
        errors.append("MAX_RESULTS_PER_SOURCE must be >= 1")

    if settings.max_concurrent_collectors < 1:
        errors.append("MAX_CONCURRENT_COLLECTORS must be >= 1")

    if settings.collector_timeout_seconds <= 0:
        errors.append("COLLECTOR_TIMEOUT_SECONDS must be > 0")

    if settings.rss_feed_concurrency < 1:
        errors.append("RSS_FEED_CONCURRENCY must be >= 1")

    if settings.x_feed_min_interest_terms < 1:
        errors.append("X_FEED_MIN_INTEREST_TERMS must be >= 1")

    if settings.http_timeout_seconds <= 0:
        errors.append("HTTP_TIMEOUT_SECONDS must be > 0")

    if errors:
        raise BootstrapError("Configuration validation failed:\n- " + "\n- ".join(errors))

    logger.info("Configuration validated successfully")


def initialize_database() -> None:
    """Initialize database and schema."""
    settings = get_settings()
    try:
        init_db()
        logger.info("Database initialized (URL: %s)", settings.database_url)
    except Exception as e:
        raise BootstrapError(f"Database initialization failed: {e}") from e


def log_startup_info() -> None:
    """Log startup information."""
    settings = get_settings()
    logger.info("=" * 60)
    logger.info("Application: %s (v%s)", settings.app_name, "0.1.0")
    logger.info("Started: %s", datetime.utcnow().isoformat())
    logger.info("Log level: %s", settings.log_level.upper())
    logger.info("-" * 60)
    logger.info("Sources configuration:")
    logger.info("  RSS: %s", "enabled" if settings.enable_rss else "disabled")
    if settings.enable_rss and settings.rss_feed_urls:
        logger.info("    - Feed URLs: %d configured", len(settings.rss_feed_urls))
    logger.info("  GitHub: %s", "enabled" if settings.enable_github else "disabled")
    if settings.enable_github:
        logger.info("    - Token: %s", "provided" if settings.github_token else "not provided")
    logger.info("  X/Twitter: %s", "enabled" if settings.enable_x else "disabled")
    if settings.enable_x:
        logger.info("    - Token: %s", "provided" if settings.x_bearer_token else "not provided")
    logger.info("  X/Twitter Snscrape: %s", "enabled" if settings.enable_x_snscrape else "disabled")
    if settings.enable_x_snscrape:
        logger.info("    - Queries: %d configured", len(settings.x_snscrape_queries))
    logger.info("  X RSS/Atom feeds: %s", "enabled" if settings.enable_x_feed else "disabled")
    if settings.enable_x_feed:
        logger.info("    - Feed URLs: %d configured", len(settings.x_feed_urls))
    logger.info("-" * 60)
    logger.info("Collection interval: %d minutes", settings.collection_interval_minutes)
    logger.info("Alert threshold: %d points", settings.alert_score_threshold)
    logger.info("Max results per source: %d", settings.max_results_per_source)
    logger.info("=" * 60)


def bootstrap() -> None:
    """
    Bootstrap the application.
    
    This function:
    1. Sets up logging
    2. Validates configuration
    3. Initializes database
    4. Logs startup information
    
    Raises:
        BootstrapError: If bootstrap fails
    """
    try:
        setup_logging()
        validate_config()
        initialize_database()
        log_startup_info()
        logger.info("Bootstrap completed successfully")
    except BootstrapError as e:
        logger.error("Bootstrap failed: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected bootstrap error: %s", e)
        raise BootstrapError(f"Unexpected error during bootstrap: {e}") from e
