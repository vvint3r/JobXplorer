"""Pipeline dispatch — replaces src/main_get_jobs.py with Celery task chains.

Each pipeline stage is a separate function that can report progress independently.
The dispatch_pipeline task orchestrates them sequentially.
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..celery_app import celery_app
from ..config import get_settings
from .base import PipelineTask

logger = logging.getLogger(__name__)

# Stage weights for progress calculation
STAGE_WEIGHTS = {
    "full": {
        "job_search": (0.0, 0.3),
        "job_details": (0.3, 0.5),
        "merge": (0.5, 0.6),
        "insights": (0.6, 0.75),
        "alignment": (0.75, 0.9),
        "optimize": (0.9, 1.0),
    },
    "search": {
        "job_search": (0.0, 0.5),
        "job_details": (0.5, 0.8),
        "merge": (0.8, 1.0),
    },
    "insights": {
        "insights": (0.0, 1.0),
    },
    "alignment": {
        "alignment": (0.0, 1.0),
    },
    "optimize": {
        "optimize": (0.0, 1.0),
    },
}

# LinkedIn job type → URL code
_JOB_TYPE_CODES = {
    "full_time": "F",
    "contract": "C",
    "part_time": "P",
    "internship": "I",
    "temporary": "T",
}

# Compiled regex for "X hours/days/weeks ago"
_TIME_AGO_RE = re.compile(r"(\d+)\s*(hour|day|week|month)s?\s*ago", re.IGNORECASE)


# ── dispatch_pipeline ──────────────────────────────────────────────────────────

@celery_app.task(bind=True, base=PipelineTask, name="pipeline.dispatch")
def dispatch_pipeline(self, run_id: str, user_id: str, pipeline_type: str):
    """Main dispatcher — runs the requested pipeline stages sequentially."""
    from ..models.pipeline_run import PipelineRun
    from ..models.search_config import SearchConfig

    try:
        run = self.db.get(PipelineRun, run_id)
        if not run:
            logger.error(f"Pipeline run {run_id} not found")
            return

        config = self.db.get(SearchConfig, str(run.search_config_id))
        if not config:
            self.fail_run(run_id, "Search config not found")
            return

        stages = STAGE_WEIGHTS.get(pipeline_type, {})

        for stage_name, (start_pct, end_pct) in stages.items():
            self.set_stage(run_id, stage_name, start_pct)
            logger.info(f"[{run_id}] Starting stage: {stage_name}")

            if stage_name == "job_search":
                _run_job_search(self, run_id, user_id, config, start_pct, end_pct)
            elif stage_name == "job_details":
                _run_job_details(self, run_id, user_id, config, start_pct, end_pct)
            elif stage_name == "merge":
                _run_merge(self, run_id, user_id, config, start_pct, end_pct)
            elif stage_name == "insights":
                _run_insights(self, run_id, user_id, config, start_pct, end_pct)
            elif stage_name == "alignment":
                _run_alignment(self, run_id, user_id, config, start_pct, end_pct)
            elif stage_name == "optimize":
                _run_optimize(self, run_id, user_id, config, start_pct, end_pct)

        self.complete_run(run_id)
        logger.info(f"[{run_id}] Pipeline completed successfully")

    except Exception as e:
        logger.exception(f"[{run_id}] Pipeline failed")
        self.fail_run(run_id, str(e))
        raise


# ── LinkedIn URL builder ───────────────────────────────────────────────────────

def _salary_filter_param(salary_min: Optional[int]) -> str:
    """Map minimum salary to LinkedIn's f_SB2 filter code."""
    if not salary_min:
        return ""
    if salary_min >= 160000:
        return "&f_SB2=5"
    if salary_min >= 140000:
        return "&f_SB2=6"
    if salary_min >= 120000:
        return "&f_SB2=7"
    if salary_min >= 100000:
        return "&f_SB2=8"
    return ""


def _build_linkedin_search_url(config) -> str:
    """Build a LinkedIn job search URL from a SearchConfig record."""
    job_title = config.job_title
    search_type = config.search_type or "exact"

    if search_type == "exact":
        keywords = f'%22{job_title.lower().replace(" ", "%20")}%22'
    else:
        keywords = job_title.lower().replace(" ", "%20")

    geo_codes: list[str] = config.work_geo_codes or ["1"]  # Default: Remote
    work_geo = "&f_WT=" + "%2C".join(geo_codes)

    salary = _salary_filter_param(config.salary_min)

    jt_code = _JOB_TYPE_CODES.get(config.job_type or "full_time", "F")

    return (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={keywords}"
        f"{work_geo}"
        f"{salary}"
        f"&f_JT={jt_code}"
        f"&geoId=103644278"
        f"&origin=JOB_SEARCH_PAGE_JOB_FILTER"
        f"&refresh=true"
    )


# ── Cookie helpers ─────────────────────────────────────────────────────────────

def _download_cookies_sync(storage_path: str) -> list | None:
    """Synchronously download and JSON-parse LinkedIn cookies from Supabase Storage."""
    try:
        settings = get_settings()
        from supabase import create_client
        supa = create_client(settings.supabase_url, settings.supabase_service_role_key)
        raw = supa.storage.from_("cookies").download(storage_path)
        if isinstance(raw, (bytes, bytearray)):
            return json.loads(raw.decode())
        return None
    except Exception as e:
        logger.warning(f"Could not download cookies from {storage_path}: {e}")
        return None


def _inject_cookies(driver, cookies: list) -> None:
    """Load session cookies into the Selenium driver and refresh."""
    driver.delete_all_cookies()
    loaded = 0
    for cookie in cookies:
        try:
            driver.add_cookie({
                "name": cookie["name"],
                "value": cookie["value"],
                "domain": cookie["domain"],
                "path": cookie.get("path", "/"),
                "secure": cookie.get("secure", False),
                "httpOnly": cookie.get("httpOnly", False),
            })
            loaded += 1
        except Exception:
            continue
    logger.info(f"Loaded {loaded}/{len(cookies)} LinkedIn cookies")
    driver.refresh()
    time.sleep(4)


# ── LinkedIn job card scraping ─────────────────────────────────────────────────

def _locate_jobs_container(driver, timeout: int = 15):
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    selectors = [
        "div.jobs-search-two-pane__results-container ul.jobs-search__results-list",
        "ul.jobs-search__results-list",
        "div[class*='scaffold-layout__list']",
    ]
    for selector in selectors:
        try:
            return WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
        except TimeoutException:
            continue
    raise TimeoutException("Could not locate jobs results container")


def _extract_job_card(job_el) -> dict | None:
    """Extract basic job info from a LinkedIn job card element."""
    from selenium.common.exceptions import NoSuchElementException
    from selenium.webdriver.common.by import By

    try:
        # Job title
        try:
            el = job_el.find_element(
                By.CSS_SELECTOR,
                "a[class*='job-card-container__link'] span[aria-hidden='true'] strong",
            )
            job_title = el.text.strip()
            if not job_title:
                el = job_el.find_element(By.CSS_SELECTOR, "a[class*='job-card-container__link']")
                job_title = (el.get_attribute("aria-label") or "").replace(" with verification", "")
        except NoSuchElementException:
            job_title = "Not Available"

        # Job URL — required
        try:
            url_el = job_el.find_element(By.CSS_SELECTOR, "a.job-card-container__link")
            job_url = (url_el.get_attribute("href") or "").split("?")[0]
        except NoSuchElementException:
            return None
        if not job_url:
            return None

        # Company name
        company_name = None
        for sel in [
            "div.artdeco-entity-lockup__subtitle span",
            "span[class*='entity-lockup__subtitle']",
        ]:
            try:
                text = job_el.find_element(By.CSS_SELECTOR, sel).text.strip()
                if text:
                    company_name = text
                    break
            except NoSuchElementException:
                continue

        # Location
        try:
            location = job_el.find_element(
                By.CSS_SELECTOR, "ul.job-card-container__metadata-wrapper li span"
            ).text.strip() or None
        except NoSuchElementException:
            location = None

        # Salary range
        try:
            salary_range = job_el.find_element(
                By.CSS_SELECTOR, "div.artdeco-entity-lockup__metadata span"
            ).text.strip() or None
        except NoSuchElementException:
            salary_range = None

        # Remote status
        try:
            remote_el = job_el.find_element(
                By.XPATH,
                ".//*[contains(text(), 'Remote') or contains(text(), 'Onsite') or contains(text(), 'Hybrid')]",
            )
            remote_status = remote_el.text.strip() or None
        except NoSuchElementException:
            remote_status = None

        return {
            "job_title": job_title,
            "job_url": job_url,
            "company_title": company_name,
            "location": location,
            "salary_range": salary_range,
            "remote_status": remote_status,
        }
    except Exception as e:
        logger.debug(f"Error extracting job card: {e}")
        return None


def _scrape_linkedin_search(driver, url: str, max_pages: int = 3) -> list[dict]:
    """Navigate to LinkedIn search URL and scrape all job cards across pages."""
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.by import By

    jobs: list[dict] = []
    driver.get(url)
    time.sleep(5)

    for page in range(1, max_pages + 1):
        logger.info(f"Scraping LinkedIn page {page}...")
        try:
            container = _locate_jobs_container(driver)
        except TimeoutException:
            logger.warning(f"No jobs container found on page {page}, stopping")
            break

        # Scroll to load all lazy-loaded cards
        for _ in range(5):
            driver.execute_script("arguments[0].scrollBy(0, 300);", container)
            time.sleep(0.8)

        cards = container.find_elements(By.CSS_SELECTOR, "li.scaffold-layout__list-item")
        logger.info(f"Page {page}: found {len(cards)} cards")

        for card in cards:
            data = _extract_job_card(card)
            if data:
                jobs.append(data)

        # Navigate to next page
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "[aria-label='View next page']")
            if not next_btn.is_enabled():
                break
            next_btn.click()
            time.sleep(3)
        except Exception:
            break

    return jobs


# ── Job details scraping ───────────────────────────────────────────────────────

def _parse_days_since_posted(date_text: str | None) -> int | None:
    """Parse 'X days/weeks/months ago' text into days count."""
    if not date_text:
        return None
    m = _TIME_AGO_RE.search(date_text)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    if unit == "hour":
        return 0
    if unit == "day":
        return n
    if unit == "week":
        return n * 7
    if unit == "month":
        return n * 30
    return None


def _get_job_full_details(driver, url: str) -> dict | None:
    """Fetch full job description, application URL, and metadata from a LinkedIn job page."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    try:
        driver.get(url)
        time.sleep(random.uniform(3, 5))
        wait = WebDriverWait(driver, 15)

        # Expand description if "see more" button exists
        try:
            btn = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, ".feed-shared-inline-show-more-text__see-more-less-toggle")
                )
            )
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)
        except Exception:
            pass

        # Job title
        try:
            job_title = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
            ).text.strip() or None
        except Exception:
            job_title = None

        # Full description
        try:
            desc_el = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR,
                     "div.job-details-about-the-job-module__description "
                     "div.feed-shared-inline-show-more-text")
                )
            )
            description = re.sub(r"\s+", " ", desc_el.text.replace("-", " ").strip()) or None
        except Exception:
            description = None

        # Company name
        try:
            company = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.job-details-jobs-unified-top-card__company-name a")
                )
            ).text.strip() or None
        except Exception:
            company = None

        # Days since posted
        days_since_posted: int | None = None
        try:
            tertiary = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR,
                     "div.job-details-jobs-unified-top-card__tertiary-description-container")
                )
            )
            for span in tertiary.find_elements(
                By.CSS_SELECTOR, "span.tvm__text.tvm__text--low-emphasis"
            ):
                if _TIME_AGO_RE.search(span.text):
                    days_since_posted = _parse_days_since_posted(span.text)
                    break
            if days_since_posted is None:
                days_since_posted = _parse_days_since_posted(tertiary.text)
        except Exception:
            pass

        # Location
        try:
            location = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR,
                     "div.job-details-jobs-unified-top-card__primary-description-container "
                     "span.tvm__text")
                )
            ).text.strip() or None
        except Exception:
            location = None

        # Salary
        try:
            salary = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR,
                     "div.job-details-preferences-and-skills__pill span.ui-label.text-body-small")
                )
            ).text.strip() or None
        except Exception:
            salary = None

        # Remote status
        remote_status: str | None = None
        try:
            prefs = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.job-details-fit-level-preferences")
                )
            )
            for btn_el in prefs.find_elements(By.TAG_NAME, "button"):
                text = btn_el.text.strip()
                if "Remote" in text:
                    remote_status = "Remote"
                    break
                elif "Hybrid" in text:
                    remote_status = "Hybrid"
                    break
                elif "Onsite" in text:
                    remote_status = "Onsite"
                    break
        except Exception:
            pass

        # Application URL
        application_url: str | None = None
        try:
            apply_btn = None
            for sel in [
                "button#jobs-apply-button-id",
                "button.jobs-apply-button",
                "div.jobs-apply-button--top-card button",
                "button.artdeco-button--primary[aria-label*='Apply']",
            ]:
                try:
                    apply_btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                    )
                    break
                except Exception:
                    continue

            if apply_btn:
                btn_text = apply_btn.text.strip().lower()
                aria = (apply_btn.get_attribute("aria-label") or "").lower()
                if "easy apply" in btn_text or "easy apply" in aria:
                    application_url = "Easy Apply (LinkedIn)"
                else:
                    # Click and capture new window
                    windows_before = set(driver.window_handles)
                    driver.execute_script("arguments[0].click();", apply_btn)
                    time.sleep(2.5)
                    new_windows = set(driver.window_handles) - windows_before
                    if new_windows:
                        new_win = new_windows.pop()
                        driver.switch_to.window(new_win)
                        time.sleep(1.5)
                        captured = driver.current_url
                        if "linkedin.com" not in captured:
                            application_url = captured
                        driver.close()
                        driver.switch_to.window(list(windows_before)[0])
        except Exception as e:
            logger.debug(f"Could not extract application URL: {e}")

        return {
            "job_title": job_title,
            "company_title": company,
            "description": description,
            "days_since_posted": days_since_posted,
            "location": location,
            "salary_range": salary,
            "remote_status": remote_status,
            "application_url": application_url,
        }

    except Exception as e:
        logger.warning(f"Error fetching job details for {url}: {e}")
        return None


# ── Stage implementations ──────────────────────────────────────────────────────

def _run_job_search(
    task: PipelineTask,
    run_id: str,
    user_id: str,
    config,
    start_pct: float = 0.0,
    end_pct: float = 0.3,
) -> None:
    """Stage 1: Scrape LinkedIn job listings via Browserless and store in jobs table."""
    from ..models.job import Job
    from ..models.user import User
    from ..services.browser import cleanup_browserless_driver, create_browserless_driver

    user = task.db.get(User, uuid.UUID(user_id) if isinstance(user_id, str) else user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    cookies: list | None = None
    if user.linkedin_cookies_storage_path:
        cookies = _download_cookies_sync(user.linkedin_cookies_storage_path)

    if not cookies:
        logger.warning(f"[{run_id}] No LinkedIn cookies found — scraping may require login")

    search_url = _build_linkedin_search_url(config)
    logger.info(f"[{run_id}] LinkedIn URL: {search_url}")

    driver = None
    try:
        driver = create_browserless_driver()

        # Navigate to LinkedIn and inject session cookies
        driver.get("https://www.linkedin.com")
        time.sleep(4)
        if cookies:
            _inject_cookies(driver, cookies)

        # Scrape listings
        jobs_data = _scrape_linkedin_search(driver, search_url, max_pages=3)
        logger.info(f"[{run_id}] Scraped {len(jobs_data)} jobs")

        if not jobs_data:
            logger.warning(f"[{run_id}] No jobs found — check cookies and search params")
            return

        # Write jobs to DB (upsert — ignore duplicates by job_url per user)
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        config_uuid = config.id
        total = len(jobs_data)

        for i, job in enumerate(jobs_data):
            job_url = job.get("job_url", "")
            if not job_url:
                continue

            stmt = (
                pg_insert(Job.__table__)
                .values(
                    id=uuid.uuid4(),
                    user_id=user_uuid,
                    search_config_id=config_uuid,
                    job_id=str(uuid.uuid4()),
                    job_title=job.get("job_title") or "Unknown Title",
                    company_title=job.get("company_title"),
                    job_url=job_url,
                    salary_range=job.get("salary_range"),
                    location=job.get("location"),
                    remote_status=job.get("remote_status"),
                    date_extracted=datetime.now(timezone.utc),
                )
                .on_conflict_do_nothing(constraint="uq_user_job_url")
            )
            task.db.execute(stmt)

            if (i + 1) % 10 == 0 or i == total - 1:
                task.db.commit()
                pct = start_pct + (end_pct - start_pct) * ((i + 1) / total)
                task.update_pipeline_run(run_id, progress=pct)

        task.db.commit()
        logger.info(f"[{run_id}] job_search complete — {total} listings processed")

    except Exception:
        task.db.rollback()
        logger.exception(f"[{run_id}] job_search failed")
        raise
    finally:
        if driver:
            cleanup_browserless_driver(driver)


def _run_job_details(
    task: PipelineTask,
    run_id: str,
    user_id: str,
    config,
    start_pct: float = 0.3,
    end_pct: float = 0.5,
) -> None:
    """Stage 2: Fetch full JD + application URL for each job without a description."""
    from ..models.job import Job
    from ..models.user import User
    from ..services.browser import cleanup_browserless_driver, create_browserless_driver

    user = task.db.get(User, uuid.UUID(user_id) if isinstance(user_id, str) else user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    # Only fetch jobs that lack descriptions
    user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    config_uuid = config.id

    jobs_needing_details = task.db.scalars(
        select(Job)
        .where(
            Job.user_id == user_uuid,
            Job.search_config_id == config_uuid,
            Job.description.is_(None),
        )
    ).all()

    if not jobs_needing_details:
        logger.info(f"[{run_id}] All jobs already have descriptions, skipping job_details stage")
        task.update_pipeline_run(run_id, progress=end_pct)
        return

    logger.info(f"[{run_id}] Fetching details for {len(jobs_needing_details)} jobs")

    # Load cookies for authenticated scraping
    cookies: list | None = None
    if user.linkedin_cookies_storage_path:
        cookies = _download_cookies_sync(user.linkedin_cookies_storage_path)

    driver = None
    try:
        driver = create_browserless_driver()

        # Authenticate before scraping
        driver.get("https://www.linkedin.com")
        time.sleep(4)
        if cookies:
            _inject_cookies(driver, cookies)

        total = len(jobs_needing_details)

        for i, job in enumerate(jobs_needing_details):
            try:
                details = _get_job_full_details(driver, job.job_url)
                if details:
                    # Update the job record with full details
                    if details.get("description"):
                        job.description = details["description"]
                    if details.get("application_url"):
                        job.application_url = details["application_url"]
                    if details.get("days_since_posted") is not None:
                        job.days_since_posted = details["days_since_posted"]
                    if details.get("company_title") and not job.company_title:
                        job.company_title = details["company_title"]
                    if details.get("location") and not job.location:
                        job.location = details["location"]
                    if details.get("salary_range") and not job.salary_range:
                        job.salary_range = details["salary_range"]
                    if details.get("remote_status") and not job.remote_status:
                        job.remote_status = details["remote_status"]
            except Exception as e:
                logger.warning(f"[{run_id}] Failed to get details for job {job.id}: {e}")

            # Commit and update progress every 5 jobs
            if (i + 1) % 5 == 0 or i == total - 1:
                task.db.commit()
                pct = start_pct + (end_pct - start_pct) * ((i + 1) / total)
                task.update_pipeline_run(run_id, progress=pct)

            # Rate-limit to avoid LinkedIn bans (5–10s between requests)
            if i < total - 1:
                time.sleep(random.uniform(5, 10))

        task.db.commit()
        logger.info(f"[{run_id}] job_details complete")

    except Exception:
        task.db.rollback()
        logger.exception(f"[{run_id}] job_details failed")
        raise
    finally:
        if driver:
            cleanup_browserless_driver(driver)


def _run_merge(
    task: PipelineTask,
    run_id: str,
    user_id: str,
    config,
    start_pct: float = 0.5,
    end_pct: float = 0.6,
) -> None:
    """Stage 3: Deduplication is enforced by DB UniqueConstraint — just update progress."""
    # The (user_id, job_url) unique constraint handles all deduplication at insert time.
    # Nothing to do here except advance progress.
    task.update_pipeline_run(run_id, progress=end_pct)
    logger.info(f"[{run_id}] merge stage complete (dedup handled by DB constraint)")


def _run_insights(
    task: PipelineTask,
    run_id: str,
    user_id: str,
    config,
    start_pct: float = 0.6,
    end_pct: float = 0.75,
) -> None:
    """Stage 5: Run JD Insights — reuses JDInsightExtractor.analyse_dataframe() as-is."""
    from ..core.job_extraction.jd_insights import (
        JDInsightExtractor,
        counter_to_sorted_list,
        merge_insights,
    )
    from ..models.insight import JDInsight
    from ..models.job import Job

    user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    config_uuid = config.id

    # Load all jobs with descriptions for this search config
    jobs = task.db.scalars(
        select(Job).where(
            Job.user_id == user_uuid,
            Job.search_config_id == config_uuid,
            Job.description.isnot(None),
        )
    ).all()

    if not jobs:
        logger.warning(f"[{run_id}] No jobs with descriptions — skipping insights")
        task.update_pipeline_run(run_id, progress=end_pct)
        return

    logger.info(f"[{run_id}] Running insights on {len(jobs)} jobs")

    # Build DataFrame
    df = pd.DataFrame([
        {
            "job_title": j.job_title,
            "description": j.description or "",
            "company_title": j.company_title or "",
            "location": j.location or "",
        }
        for j in jobs
    ])

    extractor = JDInsightExtractor()
    category_counters = extractor.analyse_dataframe(df)
    task.update_pipeline_run(run_id, progress=start_pct + (end_pct - start_pct) * 0.6)

    # Convert Counters to JSON-serializable sorted lists
    categorised_phrases = {
        category: counter_to_sorted_list(counter, limit=25)
        for category, counter in category_counters.items()
    }

    summary = {
        "total_jobs": len(jobs),
        "top_terms": counter_to_sorted_list(category_counters.get("description_terms", {}), limit=20),
        "top_companies": counter_to_sorted_list(category_counters.get("companies", {}), limit=10),
        "top_locations": counter_to_sorted_list(category_counters.get("locations", {}), limit=10),
    }

    # Upsert into jd_insights (one row per search_config)
    existing = task.db.scalar(
        select(JDInsight).where(
            JDInsight.user_id == user_uuid,
            JDInsight.search_config_id == config_uuid,
        )
    )

    if existing:
        # Merge with previous insights
        merged_phrases = merge_insights(existing.categorised_phrases or {}, categorised_phrases)
        existing.categorised_phrases = merged_phrases
        existing.summary = summary
        existing.total_jobs_analysed = len(jobs)
    else:
        task.db.add(JDInsight(
            id=uuid.uuid4(),
            user_id=user_uuid,
            search_config_id=config_uuid,
            total_jobs_analysed=len(jobs),
            categorised_phrases=categorised_phrases,
            summary=summary,
        ))

    task.db.commit()
    task.update_pipeline_run(run_id, progress=end_pct)
    logger.info(f"[{run_id}] insights stage complete — analysed {len(jobs)} jobs")


def _run_alignment(
    task: PipelineTask,
    run_id: str,
    user_id: str,
    config,
    start_pct: float = 0.75,
    end_pct: float = 0.9,
) -> None:
    """Stage 5.5: Alignment scoring — reuses score_single_job() as-is."""
    from ..core.job_extraction.alignment_scorer import TextMatcher, score_single_job
    from ..core.job_extraction.jd_term_extractor import IndexMatcher
    from ..models.alignment import AlignmentScore, InputIndex
    from ..models.job import Job
    from ..models.resume import Resume

    user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    config_uuid = config.id

    # Load user's default resume
    resume = task.db.scalar(
        select(Resume).where(
            Resume.user_id == user_uuid,
            Resume.is_default.is_(True),
        )
    )
    if not resume:
        # Fall back to first resume
        resume = task.db.scalar(
            select(Resume).where(Resume.user_id == user_uuid)
        )
    if not resume or not resume.resume_text:
        logger.warning(f"[{run_id}] No resume with text found — skipping alignment")
        task.update_pipeline_run(run_id, progress=end_pct)
        return

    # Load user's most recent input index
    index_record = task.db.scalar(
        select(InputIndex)
        .where(InputIndex.user_id == user_uuid)
        .order_by(InputIndex.created_at.desc())
    )
    if not index_record or not index_record.inputs:
        logger.warning(f"[{run_id}] No input index found — skipping alignment scoring")
        task.update_pipeline_run(run_id, progress=end_pct)
        return

    # inputs is stored as a dict with an "inputs" key or directly as a list
    raw_inputs = index_record.inputs
    if isinstance(raw_inputs, dict) and "inputs" in raw_inputs:
        inputs_list = raw_inputs["inputs"]
    elif isinstance(raw_inputs, list):
        inputs_list = raw_inputs
    else:
        logger.warning(f"[{run_id}] Unexpected input index format — skipping alignment")
        task.update_pipeline_run(run_id, progress=end_pct)
        return

    # Load jobs with descriptions
    jobs = task.db.scalars(
        select(Job).where(
            Job.user_id == user_uuid,
            Job.search_config_id == config_uuid,
            Job.description.isnot(None),
        )
    ).all()

    if not jobs:
        logger.warning(f"[{run_id}] No jobs with descriptions — skipping alignment")
        task.update_pipeline_run(run_id, progress=end_pct)
        return

    logger.info(f"[{run_id}] Scoring alignment for {len(jobs)} jobs")

    # Build matcher instances (shared across all jobs for efficiency)
    matcher = IndexMatcher(inputs_list)
    text_matcher = TextMatcher()

    # Load supplementary terms from user profile
    from ..models.user import User as UserModel
    user_record = task.db.get(UserModel, str(user_uuid))
    supplementary_terms: list = []
    if user_record and user_record.supplementary_terms:
        supplementary_terms = user_record.supplementary_terms
        logger.info(f"[{run_id}] Loaded {len(supplementary_terms)} supplementary terms")

    total = len(jobs)

    for i, job in enumerate(jobs):
        try:
            result = score_single_job(
                jd_text=job.description or "",
                job_title=job.job_title,
                inputs=inputs_list,
                resume_text=resume.resume_text or "",
                supplementary_terms=supplementary_terms,
                matcher=matcher,
                text_matcher=text_matcher,
            )
        except Exception as e:
            logger.warning(f"[{run_id}] Error scoring job {job.id}: {e}")
            continue

        if not result:
            continue

        # Upsert alignment score (check existing first)
        existing_score = task.db.scalar(
            select(AlignmentScore).where(
                AlignmentScore.job_id == job.id,
                AlignmentScore.resume_id == resume.id,
            )
        )

        if existing_score:
            existing_score.alignment_score = result["alignment_score"]
            existing_score.alignment_grade = result["grade"]
            existing_score.matched_inputs = {
                "matched": result.get("matched_inputs", []),
                "supplementary": result.get("supplementary_matches", []),
            }
            existing_score.gaps = result.get("gaps", [])
            existing_score.scored_at = datetime.now(timezone.utc)
        else:
            task.db.add(AlignmentScore(
                id=uuid.uuid4(),
                user_id=user_uuid,
                job_id=job.id,
                resume_id=resume.id,
                alignment_score=result["alignment_score"],
                alignment_grade=result["grade"],
                matched_inputs={
                    "matched": result.get("matched_inputs", []),
                    "supplementary": result.get("supplementary_matches", []),
                },
                gaps=result.get("gaps", []),
                scored_at=datetime.now(timezone.utc),
            ))

        if (i + 1) % 20 == 0 or i == total - 1:
            task.db.commit()
            pct = start_pct + (end_pct - start_pct) * ((i + 1) / total)
            task.update_pipeline_run(run_id, progress=pct)

    task.db.commit()
    logger.info(f"[{run_id}] alignment stage complete — scored {total} jobs")

    # Emit notifications for newly high-scoring jobs (score >= 0.75)
    _emit_high_score_notifications(task, user_uuid, run_id)


def _emit_high_score_notifications(task: "PipelineTask", user_id: uuid.UUID, run_id: str) -> None:
    """Create Notification rows for jobs scored >= 75% in this pipeline run."""
    from ..models.alignment import AlignmentScore
    from ..models.job import Job
    from ..models.notification import Notification

    HIGH_SCORE_THRESHOLD = 0.75

    # Find jobs from this run with high alignment scores that have no unread notification yet
    result = task.db.execute(
        __import__("sqlalchemy", fromlist=["select"])
        .select(Job.id, Job.job_title, Job.company_title, AlignmentScore.alignment_score)
        .join(AlignmentScore, AlignmentScore.job_id == Job.id)
        .where(
            Job.user_id == user_id,
            AlignmentScore.alignment_score >= HIGH_SCORE_THRESHOLD,
            ~__import__("sqlalchemy", fromlist=["exists"])
            .exists()
            .where(
                Notification.user_id == user_id,
                Notification.job_id == Job.id,
            ),
        )
        .limit(10)
    )
    rows = result.all()

    if not rows:
        return

    count = len(rows)
    # One summary notification rather than one per job
    notif = Notification(
        id=uuid.uuid4(),
        user_id=user_id,
        type="new_high_score_jobs",
        title=f"{count} high-match job{'s' if count > 1 else ''} found",
        message=(
            f"Your latest search found {count} job{'s' if count > 1 else ''} "
            f"with ≥75% alignment score. Check your Jobs dashboard."
        ),
    )
    task.db.add(notif)
    task.db.commit()
    logger.info(f"[{run_id}] emitted high-score notification for {count} jobs")


def _run_optimize(
    task: PipelineTask,
    run_id: str,
    user_id: str,
    config,
    start_pct: float = 0.9,
    end_pct: float = 1.0,
) -> None:
    """Stage 6: Resume optimization — optimise resumes for top-aligned jobs."""
    from ..core.auto_application.resume_optimizer import optimise_resume_for_job
    from ..models.alignment import AlignmentScore
    from ..models.job import Job
    from ..models.optimized_resume import OptimizedResume
    from ..models.resume import Resume
    from ..models.user import User as UserModel
    from ..services.encryption import decrypt_value

    user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    config_uuid = uuid.UUID(str(config.id)) if not isinstance(config.id, uuid.UUID) else config.id

    # Load user's default resume
    resume = task.db.scalar(
        select(Resume).where(Resume.user_id == user_uuid, Resume.is_default.is_(True))
    )
    if not resume:
        resume = task.db.scalar(
            select(Resume).where(Resume.user_id == user_uuid)
        )
    if not resume or not resume.components_json:
        logger.warning(f"[{run_id}] No resume with components found — skipping optimization")
        task.update_pipeline_run(run_id, progress=end_pct)
        return

    base_resume = resume.components_json

    # Get OpenAI key (optional — falls back to keyword match)
    user_record = task.db.get(UserModel, str(user_uuid))
    openai_api_key = None
    if user_record and user_record.openai_api_key_encrypted:
        try:
            openai_api_key = decrypt_value(user_record.openai_api_key_encrypted)
        except Exception:
            logger.warning(f"[{run_id}] Could not decrypt OpenAI key — using keyword fallback")

    # Load top-aligned jobs for this search config (score >= 50, limit 20)
    top_jobs = task.db.scalars(
        select(Job)
        .join(AlignmentScore, AlignmentScore.job_id == Job.id)
        .where(
            Job.user_id == user_uuid,
            Job.search_config_id == config_uuid,
            Job.description.isnot(None),
            AlignmentScore.alignment_score >= 50.0,
        )
        .order_by(AlignmentScore.alignment_score.desc())
        .limit(20)
    ).all()

    if not top_jobs:
        # Fall back to all jobs with descriptions (limit 10)
        top_jobs = task.db.scalars(
            select(Job).where(
                Job.user_id == user_uuid,
                Job.search_config_id == config_uuid,
                Job.description.isnot(None),
            )
            .limit(10)
        ).all()

    if not top_jobs:
        logger.warning(f"[{run_id}] No jobs with descriptions — skipping optimization")
        task.update_pipeline_run(run_id, progress=end_pct)
        return

    logger.info(f"[{run_id}] Optimizing resumes for {len(top_jobs)} jobs")
    total = len(top_jobs)

    for i, job in enumerate(top_jobs):
        try:
            result = optimise_resume_for_job(
                base_resume=base_resume,
                job_title=job.job_title,
                company=job.company_title or "Unknown",
                description=job.description or "",
                openai_api_key=openai_api_key,
            )
        except Exception as e:
            logger.warning(f"[{run_id}] Error optimizing resume for job {job.id}: {e}")
            continue

        if not result:
            continue

        method = result.get("_optimised_for", {}).get("method", "keyword_match")

        # Upsert optimized resume
        existing = task.db.scalar(
            select(OptimizedResume).where(
                OptimizedResume.job_id == job.id,
                OptimizedResume.resume_id == resume.id,
            )
        )

        if existing:
            existing.optimized_json = result
            existing.method = method
        else:
            task.db.add(OptimizedResume(
                id=uuid.uuid4(),
                user_id=user_uuid,
                job_id=job.id,
                resume_id=resume.id,
                optimized_json=result,
                method=method,
            ))

        if (i + 1) % 5 == 0 or i == total - 1:
            task.db.commit()
            pct = start_pct + (end_pct - start_pct) * ((i + 1) / total)
            task.update_pipeline_run(run_id, progress=pct)

    task.db.commit()
    logger.info(f"[{run_id}] optimize stage complete — optimized {total} resumes")


# ── Standalone task: generate input index ─────────────────────────────────────


@celery_app.task(bind=True, base=PipelineTask, name="pipeline.generate_index")
def generate_input_index_task(self, user_id: str, job_title: str):
    """Generate or regenerate an input index for a job title using OpenAI.

    This is a standalone task (not part of the main pipeline dispatch) that
    can be triggered from the alignment API endpoint.
    """
    from ..core.job_extraction.input_index_generator import generate_index
    from ..models.alignment import InputIndex
    from ..models.user import User
    from ..services.encryption import decrypt_value

    user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

    user = self.db.get(User, str(user_uuid))
    if not user:
        logger.error(f"User {user_id} not found for index generation")
        return {"error": "User not found"}

    if not user.openai_api_key_encrypted:
        logger.error(f"User {user_id} has no OpenAI API key")
        return {"error": "OpenAI API key not configured"}

    api_key = decrypt_value(user.openai_api_key_encrypted)

    # Check for existing index to get version
    existing = self.db.scalar(
        select(InputIndex)
        .where(InputIndex.user_id == user_uuid)
        .order_by(InputIndex.created_at.desc())
    )
    existing_version = 0
    if existing and existing.index_metadata:
        existing_version = existing.index_metadata.get("version", 0)

    logger.info(f"Generating input index for user {user_id}, job title: {job_title}")
    index_data = generate_index(job_title, api_key, existing_version)

    if not index_data.get("inputs"):
        logger.warning(f"Index generation produced no inputs for user {user_id}")
        return {"error": "No inputs generated", "inputs_count": 0}

    # Upsert: update existing or create new
    if existing and existing.master_job_title.lower() == job_title.lower():
        existing.inputs = index_data
        existing.index_metadata = index_data.get("metadata", {})
        existing.master_job_title = job_title
    else:
        self.db.add(InputIndex(
            id=uuid.uuid4(),
            user_id=user_uuid,
            master_job_title=job_title,
            inputs=index_data,
            metadata=index_data.get("metadata", {}),
        ))

    self.db.commit()
    inputs_count = len(index_data.get("inputs", []))
    logger.info(f"Input index saved: {inputs_count} inputs for user {user_id}")
    return {"status": "ok", "inputs_count": inputs_count}
