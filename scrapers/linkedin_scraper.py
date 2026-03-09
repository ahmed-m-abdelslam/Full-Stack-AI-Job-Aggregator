"""Scraper for LinkedIn — مع فلاتر البلد والتاريخ."""

from urllib.parse import quote_plus
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper, RawJob, ScrapeConfig
from utils.logger import logger
from utils.helpers import clean_text, parse_relative_date
from config.settings import settings


class LinkedInScraper(BaseScraper):
    SOURCE_NAME = "linkedin"
    BASE_URL = "https://www.linkedin.com"

    # LinkedIn geoId — معرفات البلدان
    COUNTRY_GEO_IDS = {
        "egypt": "106155005",
        "uae": "104305776",
        "united arab emirates": "104305776",
        "saudi arabia": "100459316",
        "united states": "103644278",
        "united kingdom": "101165590",
        "germany": "101282230",
        "canada": "101174742",
        "india": "102713980",
        "qatar": "104035893",
        "kuwait": "106197167",
        "jordan": "101312532",
        "morocco": "102787409",
        "remote": "",
    }

    # LinkedIn f_TPR — فلتر الوقت
    DAYS_TO_LINKEDIN_FILTER = {
        1: "r86400",      # last 24 hours
        7: "r604800",     # last week
        30: "r2592000",   # last month
    }

    def _get_geo_id(self, country: str) -> str:
        return self.COUNTRY_GEO_IDS.get(country.lower(), "")

    def _get_time_filter(self, config: ScrapeConfig) -> str:
        days = settings.scrape_days_back
        for threshold in sorted(self.DAYS_TO_LINKEDIN_FILTER.keys()):
            if days <= threshold:
                return self.DAYS_TO_LINKEDIN_FILTER[threshold]
        return "r2592000"

    def scrape(self, keyword: str, config: ScrapeConfig) -> list[RawJob]:
        all_jobs: list[RawJob] = []
        time_filter = self._get_time_filter(config)

        countries = config.countries if config.countries else ["united states"]

        for country in countries:
            geo_id = self._get_geo_id(country)
            country_jobs: list[RawJob] = []

            for page in range(config.num_pages):
                if len(country_jobs) >= config.max_jobs:
                    break

                start = page * 25
                params = {
                    "keywords": keyword,
                    "start": start,
                    "sortBy": "DD",
                    "f_TPR": time_filter,  # ← فلتر الوقت
                }
                if geo_id:
                    params["geoId"] = geo_id  # ← فلتر البلد

                try:
                    logger.info(
                        f"[LinkedIn/{country}] Page {page + 1} for '{keyword}' "
                        f"(time filter: {time_filter})"
                    )
                    response = self._get(
                        f"{self.BASE_URL}/jobs-guest/jobs/api/seeMoreJobPostings/search",
                        params=params,
                    )
                    soup = BeautifulSoup(response.text, "lxml")
                    cards = soup.select("li")

                    if not cards:
                        break

                    for card in cards:
                        try:
                            title_elem = card.select_one("h3.base-search-card__title")
                            if not title_elem:
                                continue
                            title = clean_text(title_elem.get_text())

                            company_elem = card.select_one(
                                "h4.base-search-card__subtitle a"
                            )
                            company = (
                                clean_text(company_elem.get_text())
                                if company_elem else "Unknown"
                            )

                            location_elem = card.select_one(
                                "span.job-search-card__location"
                            )
                            location = (
                                clean_text(location_elem.get_text())
                                if location_elem else country
                            )

                            link_elem = card.select_one("a.base-card__full-link")
                            job_url = (
                                link_elem["href"].split("?")[0]
                                if link_elem else ""
                            )

                            time_elem = card.select_one("time")
                            date_posted = None
                            if time_elem:
                                date_str = time_elem.get("datetime", "")
                                if date_str:
                                    try:
                                        from datetime import datetime
                                        date_posted = datetime.strptime(
                                            date_str, "%Y-%m-%d"
                                        )
                                    except ValueError:
                                        date_posted = parse_relative_date(
                                            time_elem.get_text()
                                        )

                            job_type = self.classify_job_type(location or "")

                            raw_job = RawJob(
                                title=title,
                                company=company,
                                location=location,
                                description="",
                                url=job_url,
                                date_posted=date_posted,
                                job_type=job_type,
                                source=self.SOURCE_NAME,
                            )
                            country_jobs.append(raw_job)

                        except Exception as e:
                            logger.warning(f"[LinkedIn/{country}] Error: {e}")
                            continue

                    self._respectful_delay()

                except Exception as e:
                    logger.error(f"[LinkedIn/{country}] Page {page + 1} failed: {e}")
                    continue

            all_jobs.extend(country_jobs)

        filtered = self.filter_jobs(all_jobs, config)
        logger.info(f"[LinkedIn] Total after filtering: {len(filtered)} jobs")
        return filtered
