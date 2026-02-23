#!/usr/bin/env python3
import json
import logging
import os
import time
from getpass import getpass
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from job_extraction.driver_utils import create_driver, cleanup_driver

COOKIE_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "linkedin_cookies.txt"


def prompt_credential(env_name, prompt_text, hide=False):
    if env_name in os.environ and os.environ[env_name]:
        return os.environ[env_name]
    if hide:
        return getpass(prompt_text)
    return input(prompt_text)


def capture_manual_snapshot(driver, prefix):
    snapshot_dir = Path(__file__).resolve().parent.parent.parent / "data" / "debug"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    html_path = snapshot_dir / f"{prefix}_{timestamp}.html"
    png_path = snapshot_dir / f"{prefix}_{timestamp}.png"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    driver.save_screenshot(str(png_path))
    print(f"Captured snapshot: {html_path}, {png_path}")


def main():
    driver = None
    try:
        username = prompt_credential("LINKEDIN_USERNAME", "LinkedIn username/email: ")
        password = prompt_credential("LINKEDIN_PASSWORD", "LinkedIn password: ", hide=True)

        driver = create_driver(headless=True, profile_name="manual_linkedin_login")
        driver.get("https://www.linkedin.com/login")

        wait = WebDriverWait(driver, 15)
        username_field = None
        for locator in [(By.ID, "username"), (By.NAME, "session_key")]:
            try:
                username_field = wait.until(EC.presence_of_element_located(locator))
                break
            except:
                continue

        password_field = None
        for locator in [(By.ID, "password"), (By.NAME, "session_password")]:
            try:
                password_field = wait.until(EC.presence_of_element_located(locator))
                break
            except:
                continue

        if not username_field or not password_field:
            raise RuntimeError("Unable to locate LinkedIn login form fields.")

        username_field.send_keys(username)
        password_field.send_keys(password)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        print("\nWaiting for LinkedIn to authenticate...")
        time.sleep(5)

        try:
            sign_in_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label*='Sign in as']"))
            )
            logging.info("Found 'Sign in as ...' button, attempting click.")
            sign_in_button.click()
            print("Clicked 'Sign in as ...' button.")
            time.sleep(3)
            capture_manual_snapshot(driver, "manual_login_after_sign_in_button")
        except Exception as exc:
            logging.warning(f"No 'Sign in as ...' button clicked: {exc}")
            capture_manual_snapshot(driver, "manual_login_no_sign_in_button")
            print("No 'Sign in as ...' button found.")

        driver.get("https://www.linkedin.com/feed/")
        time.sleep(3)

        print("Capturing post-login snapshot...")
        capture_manual_snapshot(driver, "manual_login_feed")

        cookies = driver.get_cookies()
        COOKIE_PATH.write_text(json.dumps(cookies, indent=2))
        print(f"\nSaved {len(cookies)} cookies to {COOKIE_PATH}")

    finally:
        if driver:
            cleanup_driver(driver)


if __name__ == "__main__":
    main()

