"""Scraper for Glassdoor — مع فلاتر البلد والتاريخ."""

from typing import Optional
from datetime import datetime

from scrapers.base_scraper import BaseScraper, RawJob, ScrapeConfig
from utils.logger import logger
from utils.helpers import clean_text
from config.settings import settings

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class GlassdoorScraper(BaseScraper):
    SOURCE_NAME = "glassdoor"
    BASE_URL = "https://www.glassdoor.com"

    # Glassdoor — نطاقات البلدان
    COUNTRY_DOMAINS = {
        "egypt": "https://www.glassdoor.com",
        "uae": "https://www.glassdoor.ae",
        "united arab emirates": "https://www.glassdoor.ae",
        "saudi arabia": "https://www.glassdoor.com",
        "united states": "https://www.glassdoor.com",
        "united kingdom": "https://www.glassdoor.co.uk",
        "germany": "https://www.glassdoor.de",
        "canada": "https://www.glassdoor.ca",
        "india": "https://www.glassdoor.co.in",
    }

    # فلتر التاريخ في Glassdoor
    DAYS_TO_GLASSDOOR_FILTER = {
        1: "fromAge=1",
        3: "fromAge=3",
        7: "fromAge=7",
        14: "fromAge=14",
        30: "fromAge=30",
    }

    def _create_driver(self):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium is not installed")

        options = Options()
        if settings.selenium_headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(f"--user-agent={self.ua.random}")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

    def _get_date_filter(self) -> str:
        days = settings.scrape_days_back
        for threshold in sorted(self.DAYS_TO_GLASSDOOR_FILTER.keys()):
            if days <= threshold:
                return self.DAYS_TO_GLASSDOOR_FILTER[threshold]
        return "fromAge=30"

    def scrape(self, keyword: str, config: ScrapeConfig) -> list[RawJob]:
        if not SELENIUM_AVAILABLE:
            logger.warning("[Glassdoor] Selenium not available — skipping")
            return []

        raw_jobs: list[RawJob] = []
        driver = None
        countries = config.countries if config.countries else ["united states"]
        date_filter = self._get_date_filter()

        try:
            driver = self._create_driver()

            for country in countries:
                domain = self.COUNTRY_DOMAINS.get(
                    country.lower(), self.BASE_URL
                )
                search_term = keyword.replace(" ", "-").lower()

                # بناء URL مع فلتر التاريخ
                url = (
                    f"{domain}/Job/{search_term}-jobs-"
                    f"SRCH_KO0,{len(search_term)}.htm?{date_filter}"
                )

                # لو البلد محتاج فلتر إضافي في URL
                if country.lower() in ["egypt"]:
                    url += "&locKeyword=Egypt"
                elif country.lower() in ["uae", "united arab emirates"]:
                    url += "&locKeyword=UAE"

                logger.info(f"[Glassdoor/{country}] Opening {url}")
                driver.get(url)

                wait = WebDriverWait(driver, 15)

                for page in range(min(config.num_pages, 2)):
                    if len(raw_jobs) >= config.max_jobs:
                        break

                    try:
                        wait.until(
                            EC.presence_of_all_elements_located(
                                (By.CSS_SELECTOR,
                                 "li.react-job-listing, li[data-test='jobListing']")
                            )
                        )

                        cards = driver.find_elements(
                            By.CSS_SELECTOR,
                            "li.react-job-listing, li[data-test='jobListing']"
                        )

                        for card in cards:
                            if len(raw_jobs) >= config.max_jobs:
                                break
                            try:
                                title_elem = card.find_element(
                                    By.CSS_SELECTOR,
                                    "a.jobLink, a[data-test='job-link']"
                                )
                                title = clean_text(title_elem.text)
                                job_url = title_elem.get_attribute("href") or ""

                                try:
                                    company_elem = card.find_element(
                                        By.CSS_SELECTOR,
                                        "div.d-flex a, "
                                        "span.EmployerProfile_compactEmployerName__LE242"
                                    )
                                    company = clean_text(company_elem.text)
                                except Exception:
                                    company = "Unknown"

                                try:
                                    loc_elem = card.find_element(
                                        By.CSS_SELECTOR,
                                        "span[data-test='emp-location']"
                                    )
                                    location = clean_text(loc_elem.text)
                                except Exception:
                                    location = country

                                job_type = self.classify_job_type(location or "")

                                raw_jobs.append(RawJob(
                                    title=title,
                                    company=company,
                                    location=location,
                                    description="",
                                    url=job_url,
                                    date_posted=None,
                                    job_type=job_type,
                                    source=self.SOURCE_NAME,
                                ))

                            except Exception as e:
                                logger.warning(f"[Glassdoor] Card error: {e}")
                                continue

                        # الصفحة التالية
                        if page < config.num_pages - 1:
                            try:
                                next_btn = driver.find_element(
                                    By.CSS_SELECTOR,
                                    "button.nextButton, button[data-test='pagination-next']"
                                )
                                next_btn.click()
                                self._respectful_delay()
                            except Exception:
                                break

                    except Exception as e:
                        logger.error(f"[Glassdoor/{country}] Page error: {e}")
                        break

        except Exception as e:
            logger.error(f"[Glassdoor] Scraping failed: {e}")
        finally:
            if driver:
                driver.quit()

        filtered = self.filter_jobs(raw_jobs, config)
        logger.info(f"[Glassdoor] After filtering: {len(filtered)} jobs")
        return filtered
