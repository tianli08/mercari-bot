"""Scraping helpers for marketplace search pages."""

import random
from typing import cast
from urllib.parse import urlencode

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .config import get_legacy_app_config, settings
from .constants import BUYEE_LINK, MERCARI_BASE_URL
from .listings import (
    ListingRecord,
    SearchContext,
    SearchDefinition,
    extract_marketplace_item_id,
)
from .logging_utils import get_logger

scraper_logger = get_logger("scraper")

ITEM_CELL_SELECTOR = '[data-testid="item-cell"]'
ITEM_LINK_TAG = "a"
ITEM_IMAGE_TAG = "img"
ITEM_TITLE_SELECTOR = ".merItemThumbnail"
SEARCH_RESULTS_WAIT_SECONDS = 7


def _search_context(search: SearchDefinition) -> dict[str, str]:
    """Return common log context for a search definition."""
    return {
        "marketplace": search.marketplace,
        "filter": search.filter_name,
        "keyword": search.keyword,
        "url": search.url,
    }


def _log_search_warning(search: SearchDefinition, message: str, exc: BaseException) -> None:
    """Log a scraper warning with common search context."""
    scraper_logger.warning(
        message,
        context={**_search_context(search), "exception": type(exc).__name__},
    )


def mercari_link(driver: WebDriver, search: SearchDefinition) -> list[ListingRecord]:
    """Scrape a Mercari search page and return normalized listings."""
    all_items: list[ListingRecord] = []
    if not _load_mercari_page(driver, search):
        return all_items

    if not _wait_for_item_cells(driver, search):
        return all_items

    total_items = _find_item_cells(driver)
    scraper_logger.debug("Scraped item cells", context={**_search_context(search), "items": len(total_items)})

    all_items = _extract_listing_records(total_items, search)
    _log_page_title(driver, search)
    return all_items


def _load_mercari_page(driver: WebDriver, search: SearchDefinition) -> bool:
    """Load the Mercari search URL, returning false only for failed page loads."""
    try:
        driver.get(search.url)
    except TimeoutException as exc:
        _log_search_warning(
            search,
            "Mercari page load timed out; attempting to stop the page load",
            exc,
        )
        try:
            driver.execute_script("window.stop();")
        except WebDriverException as stop_exc:
            _log_search_warning(
                search,
                "Failed to stop timed-out Mercari page load",
                stop_exc,
            )
    except WebDriverException as exc:
        _log_search_warning(
            search,
            "Mercari page load failed; search will return no listings",
            exc,
        )
        return False
    return True


def _wait_for_item_cells(driver: WebDriver, search: SearchDefinition) -> bool:
    """Wait for at least one item cell to appear on the current page."""
    try:
        WebDriverWait(driver, SEARCH_RESULTS_WAIT_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ITEM_CELL_SELECTOR))
        )
    except TimeoutException as exc:
        _log_search_warning(
            search,
            "No item cells found before timeout; search will return no listings",
            exc,
        )
        return False
    return True


def _find_item_cells(driver: WebDriver) -> list[WebElement]:
    """Return all Mercari item cells from the current page."""
    return driver.find_elements(by=By.CSS_SELECTOR, value=ITEM_CELL_SELECTOR)


def _extract_listing_records(total_items: list[WebElement], search: SearchDefinition) -> list[ListingRecord]:
    """Extract normalized listing records from Selenium item cells."""
    all_items: list[ListingRecord] = []
    for item in total_items:
        try:
            listing = _extract_listing_record(item, search)
            if listing is None:
                continue
            all_items.append(listing)
        except ValueError as exc:
            _log_search_warning(
                search,
                "Skipping invalid scraped listing",
                exc,
            )
        except WebDriverException as exc:
            _log_search_warning(
                search,
                "Skipping listing after Selenium extraction error",
                exc,
            )
    return all_items


def _extract_listing_record(item: WebElement, search: SearchDefinition) -> ListingRecord | None:
    """Extract one listing record from a Selenium item cell."""
    content = item.text
    if not content.strip():
        return None

    listing_url = _element_attribute(item, By.TAG_NAME, ITEM_LINK_TAG, "href")
    if not listing_url:
        return None

    image = _element_attribute(item, By.TAG_NAME, ITEM_IMAGE_TAG, "src")
    full_title = cast(str, _element_attribute(item, By.CSS_SELECTOR, ITEM_TITLE_SELECTOR, "aria-label"))

    return ListingRecord.from_scrape(
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


def _element_attribute(item: WebElement, by: str, value: str, attribute: str) -> str | None:
    """Return an attribute from a child element."""
    element = item.find_element(by=by, value=value)
    return element.get_attribute(attribute)


def _log_page_title(driver: WebDriver, search: SearchDefinition) -> None:
    """Log the page title when Selenium can still read it."""
    try:
        scraper_logger.debug("Scraped page title", context={**_search_context(search), "title": driver.title})
    except Exception as exc:
        _log_search_warning(
            search,
            "Could not read scraped page title",
            exc,
        )


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
    for filter_data in get_legacy_app_config().filters:
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
