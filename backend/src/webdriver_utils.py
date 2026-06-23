"""Selenium webdriver setup helpers for marketplace scraping."""

import asyncio

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from .browser_profile import BrowserProfile, build_fingerprint_script, pick_browser_profile
from .config import settings
from .logging_utils import get_logger, log_exception

scraper_logger = get_logger("scraper")


def build_webdriver_options(profile: BrowserProfile) -> Options:
    """Build Chrome options for the shared scraping session."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument(f"--window-size={profile.width},{profile.height}")
    options.add_argument(f"--lang={profile.locale}")
    options.add_argument(f"--user-agent={profile.user_agent}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_experimental_option(
        "prefs",
        {"intl.accept_languages": profile.accept_language},
    )
    return options


def apply_browser_profile(driver: webdriver.Chrome, profile: BrowserProfile) -> None:
    """Apply stealth-oriented browser overrides to a new session."""
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd(
        "Network.setUserAgentOverride",
        {
            "userAgent": profile.user_agent,
            "acceptLanguage": profile.accept_language,
            "platform": profile.platform,
        },
    )
    driver.execute_cdp_cmd(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": profile.width,
            "height": profile.height,
            "deviceScaleFactor": profile.device_scale_factor,
            "mobile": False,
        },
    )
    driver.execute_cdp_cmd(
        "Emulation.setTimezoneOverride",
        {"timezoneId": profile.timezone},
    )
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": build_fingerprint_script(profile)},
    )


async def create_driver() -> tuple[webdriver.Chrome, BrowserProfile]:
    """Create a Chrome webdriver without blocking the event loop."""
    profile = pick_browser_profile()
    options = build_webdriver_options(profile)
    driver = await asyncio.to_thread(webdriver.Chrome, options=options)
    await asyncio.to_thread(driver.set_page_load_timeout, settings.selenium_page_load_timeout_seconds)
    await asyncio.to_thread(driver.set_script_timeout, settings.selenium_script_timeout_seconds)
    try:
        await asyncio.to_thread(apply_browser_profile, driver, profile)
    except Exception as exc:
        log_exception(
            scraper_logger,
            "Failed to apply browser profile overrides",
            exc,
            platform=profile.platform,
            timezone=profile.timezone,
        )
    return driver, profile
