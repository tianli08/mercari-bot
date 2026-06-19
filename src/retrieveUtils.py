"""Scraping helpers for marketplace search pages."""

import random
from urllib.parse import urlencode

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .config import app_config, settings
from .constants import BUYEE_LINK, MERCARI_BASE_URL
from .listings import (
    ListingRecord,
    SearchContext,
    SearchDefinition,
    extract_marketplace_item_id,
)
from .logging_utils import get_logger

scraper_logger = get_logger("scraper")


def _search_context(search: SearchDefinition) -> dict[str, str]:
    """Return common log context for a search definition."""
    return {
        "marketplace": search.marketplace,
        "filter": search.filter_name,
        "keyword": search.keyword,
        "url": search.url,
    }


def mercari_link(driver, search: SearchDefinition) -> list[ListingRecord]:
    """Scrape a Mercari search page and return normalized listings."""
    all_items: list[ListingRecord] = []
    try:
        driver.get(search.url)
    except TimeoutException as exc:
        scraper_logger.warning(
            "Mercari page load timed out; attempting to stop the page load",
            context={**_search_context(search), "exception": type(exc).__name__},
        )
        try:
            driver.execute_script("window.stop();")
        except WebDriverException as stop_exc:
            scraper_logger.warning(
                "Failed to stop timed-out Mercari page load",
                context={**_search_context(search), "exception": type(stop_exc).__name__},
            )
    except WebDriverException as exc:
        scraper_logger.warning(
            "Mercari page load failed; search will return no listings",
            context={**_search_context(search), "exception": type(exc).__name__},
        )
        return all_items

    try:
        WebDriverWait(driver, 7).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="item-cell"]'))
        )
    except TimeoutException as exc:
        scraper_logger.warning(
            "No item cells found before timeout; search will return no listings",
            context={**_search_context(search), "exception": type(exc).__name__},
        )
        return all_items

    total_items = driver.find_elements(by=By.CSS_SELECTOR, value='[data-testid="item-cell"]')

    scraper_logger.debug("Scraped item cells", context={**_search_context(search), "items": len(total_items)})

    for item in total_items:
        try:
            content = item.text
            if not content.strip():
                continue

            link_scrape = item.find_element(by=By.TAG_NAME, value="a")
            listing_url = link_scrape.get_attribute("href")
            if not listing_url:
                continue

            image_scrape = item.find_element(by=By.TAG_NAME, value="img")
            image = image_scrape.get_attribute("src")

            full_title_scrape = item.find_element(By.CSS_SELECTOR, value=".merItemThumbnail")
            full_title = full_title_scrape.get_attribute("aria-label")

            all_items.append(
                ListingRecord.from_scrape(
                    marketplace=search.marketplace,
                    url=listing_url,
                    title=full_title,
                    image_url=image,
                    raw_content=content,
                    search_context=SearchContext(
                        filter_name=search.filter_name,
                        keyword=search.keyword,
                        search_url=search.url,
                    ),
                )
            )
        except ValueError as exc:
            scraper_logger.warning(
                "Skipping invalid scraped listing",
                context={**_search_context(search), "exception": type(exc).__name__},
            )
        except WebDriverException as exc:
            scraper_logger.warning(
                "Skipping listing after Selenium extraction error",
                context={**_search_context(search), "exception": type(exc).__name__},
            )

    try:
        scraper_logger.debug("Scraped page title", context={**_search_context(search), "title": driver.title})
    except Exception as exc:
        scraper_logger.warning(
            "Could not read scraped page title",
            context={**_search_context(search), "exception": type(exc).__name__},
        )

    return all_items


def query_interval(search_count: int) -> float:
    """Return the delay between individual searches in a round-robin loop."""
    if search_count <= 0:
        return 60.0

    min_seconds = max(1.0, settings.query_interval_min_seconds)
    max_seconds = max(min_seconds, settings.query_interval_max_seconds)
    interval_seconds = random.uniform(min_seconds, max_seconds)
    scraper_logger.debug(
        "Calculated legacy query interval",
        context={
            "interval_seconds": f"{interval_seconds:.2f}",
            "rotation_estimate_seconds": f"{interval_seconds * search_count:.2f}",
            "searches": search_count,
        },
    )
    return interval_seconds


def link_generator() -> list[SearchDefinition]:
    """Generate normalized Mercari search definitions."""
    all_urls: list[SearchDefinition] = []
    for filter_data in app_config.filters:
        for keyword in filter_data.keywords:
            params = {"keyword": keyword, "sort": "created_time", "order": "desc"}
            url = f"{MERCARI_BASE_URL}?{urlencode(params)}"
            all_urls.append(
                SearchDefinition(
                    marketplace="mercari",
                    filter_name=filter_data.name,
                    keyword=keyword,
                    url=url,
                )
            )
    return all_urls


def merge_listing_results(
    aggregated_results: dict[str, ListingRecord],
    scraped_results: list[ListingRecord],
) -> None:
    """Collapse duplicate listing matches into canonical records."""
    for listing in scraped_results:
        existing = aggregated_results.get(listing.canonical_id)
        if existing is None:
            aggregated_results[listing.canonical_id] = listing
            continue
        existing.merge(listing)


def link_crafter(mercari_link: str) -> str | None:
    """Build a Buyee listing URL from a Mercari item URL."""
    if "/shops/product/" in mercari_link:
        return None

    item_id = extract_marketplace_item_id("mercari", mercari_link)
    if not item_id:
        return None

    return f"{BUYEE_LINK}{item_id}"
