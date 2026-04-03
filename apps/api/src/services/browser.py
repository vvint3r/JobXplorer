"""Browserless connection manager — replaces local Chrome/Xvfb (driver_utils.py).

Connects Selenium to a remote Browserless instance for headless Chrome.
"""

import random

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions

from ..config import get_settings

# Random user agents matching the original driver_utils.py
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
]

# Anti-detection JS from the original driver_utils.py
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({state: Notification.permission})
        : originalQuery(parameters)
);
"""


def create_browserless_driver() -> webdriver.Remote:
    """Create a Selenium Remote WebDriver connected to Browserless.

    Replaces the local `create_driver()` from driver_utils.py.
    """
    settings = get_settings()

    options = ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument(f"--user-agent={random.choice(USER_AGENTS)}")

    # Random window size (matching original)
    width = random.randint(1050, 1200)
    height = random.randint(800, 1000)
    options.add_argument(f"--window-size={width},{height}")

    browserless_url = settings.browserless_url
    token = settings.browserless_token

    # Browserless v2 expects WebDriver protocol at /webdriver
    remote_url = f"{browserless_url}/webdriver"
    if token:
        remote_url = f"{browserless_url}/webdriver?token={token}"

    driver = webdriver.Remote(
        command_executor=remote_url,
        options=options,
    )

    # Inject stealth script into the current context.
    # execute_cdp_cmd is unavailable on Remote; execute_script runs in the
    # active page context and is sufficient for basic anti-detection.
    try:
        driver.execute_script(STEALTH_JS)
    except Exception:
        pass  # Non-fatal — page may not be ready yet

    return driver


def cleanup_browserless_driver(driver: webdriver.Remote) -> None:
    """Quit the remote driver session."""
    try:
        driver.quit()
    except Exception:
        pass
