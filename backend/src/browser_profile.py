"""Browser fingerprint selection and injection for Selenium sessions."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BrowserProfile:
    """A plausible desktop browser profile for Mercari scraping."""

    user_agent: str
    width: int
    height: int
    timezone: str
    locale: str
    accept_language: str
    platform: str
    device_scale_factor: float
    hardware_concurrency: int
    device_memory: int

    @property
    def languages(self) -> list[str]:
        """Return ordered navigator languages for the profile."""
        return [language.split(";")[0] for language in self.accept_language.split(",")]


_BROWSER_PROFILES: tuple[BrowserProfile, ...] = (
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/135.0.0.0 Safari/537.36"
        ),
        width=1920,
        height=1080,
        timezone="Asia/Tokyo",
        locale="ja-JP",
        accept_language="ja-JP,ja,en-US;q=0.9",
        platform="Win32",
        device_scale_factor=1.0,
        hardware_concurrency=8,
        device_memory=8,
    ),
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/135.0.0.0 Safari/537.36"
        ),
        width=1728,
        height=1117,
        timezone="Asia/Tokyo",
        locale="ja-JP",
        accept_language="ja-JP,ja,en-US;q=0.9",
        platform="MacIntel",
        device_scale_factor=2.0,
        hardware_concurrency=8,
        device_memory=8,
    ),
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ),
        width=1536,
        height=864,
        timezone="Asia/Seoul",
        locale="ja-JP",
        accept_language="ja-JP,ja,en-US;q=0.9",
        platform="Win32",
        device_scale_factor=1.25,
        hardware_concurrency=12,
        device_memory=8,
    ),
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_6) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ),
        width=1440,
        height=900,
        timezone="Asia/Tokyo",
        locale="ja-JP",
        accept_language="ja-JP,ja,en-US;q=0.9",
        platform="MacIntel",
        device_scale_factor=2.0,
        hardware_concurrency=10,
        device_memory=8,
    ),
)


def pick_browser_profile() -> BrowserProfile:
    """Select a browser profile for a new Selenium session."""
    return random.choice(_BROWSER_PROFILES)


def build_fingerprint_script(profile: BrowserProfile) -> str:
    """Return a script that masks Selenium defaults with the chosen profile."""
    languages = json.dumps(profile.languages)
    locale = json.dumps(profile.locale)
    platform = json.dumps(profile.platform)
    timezone = json.dumps(profile.timezone)

    return f"""
const profile = {{
  languages: {languages},
  locale: {locale},
  platform: {platform},
  timezone: {timezone},
  hardwareConcurrency: {profile.hardware_concurrency},
  deviceMemory: {profile.device_memory},
  screenWidth: {profile.width},
  screenHeight: {profile.height},
  availWidth: {profile.width},
  availHeight: {profile.height - 40},
}};

Object.defineProperty(navigator, "webdriver", {{
  get: () => undefined,
}});
Object.defineProperty(navigator, "language", {{
  get: () => profile.locale,
}});
Object.defineProperty(navigator, "languages", {{
  get: () => profile.languages,
}});
Object.defineProperty(navigator, "platform", {{
  get: () => profile.platform,
}});
Object.defineProperty(navigator, "hardwareConcurrency", {{
  get: () => profile.hardwareConcurrency,
}});
Object.defineProperty(navigator, "deviceMemory", {{
  get: () => profile.deviceMemory,
}});
Object.defineProperty(screen, "width", {{
  get: () => profile.screenWidth,
}});
Object.defineProperty(screen, "height", {{
  get: () => profile.screenHeight,
}});
Object.defineProperty(screen, "availWidth", {{
  get: () => profile.availWidth,
}});
Object.defineProperty(screen, "availHeight", {{
  get: () => profile.availHeight,
}});

window.chrome = window.chrome || {{ runtime: {{}} }};

const originalResolvedOptions = Intl.DateTimeFormat.prototype.resolvedOptions;
Intl.DateTimeFormat.prototype.resolvedOptions = function(...args) {{
  const options = originalResolvedOptions.apply(this, args);
  return {{
    ...options,
    timeZone: profile.timezone,
  }};
}};
"""
