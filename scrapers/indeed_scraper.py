"""Scraper for Indeed — مع anti-bot headers ومعالجة 403."""

import httpx
import random
from datetime import datetime
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper, RawJob, ScrapeConfig
from utils.logger import logger
from utils.helpers import clean_text, parse_relative_date
from config.settings import settings


class IndeedScraper(BaseScraper):
    SOURCE_NAME = "indeed"
    BASE_URL = "https://www.indeed.com"

    COUNTRY_DOMAINS = {
        "egypt": "https://eg.indeed.com",
        "uae": "https://ae.indeed.com",
        "united arab emirates": "https://ae.indeed.com",
        "saudi arabia": "https://sa.indeed.com",
        "united states": "https://www.indeed.com",
        "united kingdom": "https://uk.indeed.com",
        "germany": "https://de.indeed.com",
        "canada": "https://ca.indeed.com",
        "india": "https://www.indeed.co.in",
        "qatar": "https://qa.indeed.com",
        "kuwait": "https://kw.indeed.com",
        "bahrain": "https://bh.indeed.com",
        "jordan": "https://jo.indeed.com",
        "morocco": "https://ma.indeed.com",
        "remote": "https://www.indeed.com",
    }

    DAYS_TO_INDEED_FILTER = {
        1: "1",
        3: "3",
        7: "7",
        14: "14",
    }

    def _get_domain_for_country(self, country: str) -> str:
        return self.COUNTRY_DOMAINS.get(country.lower(), self.BASE_URL)

    def _get_date_filter_param(self) -> str:
        days = settings.scrape_days_back
        for threshold in sorted(self.DAYS_TO_INDEED_FILTER.keys()):
            if days <= threshold:
                return self.DAYS_TO_INDEED_FILTER[threshold]
        return "14"

    def _build_headers(self, domain: str) -> dict:
        """بناء headers تبان زي browser حقيقي."""
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{random.randint(120, 133)}.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": f"{domain}/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }

    def _fetch_page(self, url: str, params: dict, domain: str) -> str | None:
        """جلب صفحة من Indeed باستخدام httpx مع anti-bot headers."""
        headers = self._build_headers(domain)

        # نجرب HTTP/2 الأول ولو مش متاح نستخدم HTTP/1.1
        try:
            import h2
            use_http2 = True
        except ImportError:
            use_http2 = False

        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=30,
                http2=use_http2,
            ) as client:
                # أولاً — نزور الصفحة الرئيسية عشان ناخد cookies
                try:
                    home_resp = client.get(domain, headers=headers)
                    cookies = dict(home_resp.cookies)
                except Exception:
                    cookies = {}

                self._respectful_delay()

                # ثانياً — نطلب صفحة البحث
                resp = client.get(
                    url,
                    params=params,
                    headers=headers,
                    cookies=cookies,
                )

                if resp.status_code == 403:
                    logger.warning(f"[Indeed] 403 — trying without params encoding")
                    self._respectful_delay()
                    q = params.get("q", "")
                    l = params.get("l", "")
                    fromage = params.get("fromage", "7")
                    start = params.get("start", "0")
                    full_url = f"{domain}/jobs?q={q}&l={l}&fromage={fromage}&start={start}&sort=date"
                    resp = client.get(full_url, headers=headers, cookies=cookies)

                if resp.status_code == 200:
                    return resp.text
                else:
                    logger.warning(f"[Indeed] Status {resp.status_code}")
                    return None

        except Exception as e:
            logger.warning(f"[Indeed] Request failed: {e}")
            return None


    def scrape(self, keyword: str, config: ScrapeConfig) -> list[RawJob]:
        all_jobs: list[RawJob] = []
        countries = config.countries if config.countries else ["united states"]
        date_filter = self._get_date_filter_param()

        for country in countries:
            domain = self._get_domain_for_country(country)
            country_jobs: list[RawJob] = []

            for page in range(config.num_pages):
                if len(country_jobs) >= config.max_jobs:
                    break

                start = page * 10
                params = {
                    "q": keyword,
                    "start": str(start),
                    "sort": "date",
                    "fromage": date_filter,
                }
                if country.lower() != "remote":
                    params["l"] = country

                logger.info(
                    f"[Indeed/{country}] Page {page + 1} for '{keyword}' "
                    f"(last {date_filter} days)"
                )

                html = self._fetch_page(f"{domain}/jobs", params, domain)

                if not html:
                    logger.info(f"[Indeed/{country}] No response for page {page + 1}")
                    # لو 403 من أول صفحة — مفيش فايدة نكمل
                    if page == 0:
                        break
                    continue

                soup = BeautifulSoup(html, "lxml")

                # Indeed بيغير الـ selectors كتير — نجرب أكتر من selector
                job_cards = (
                    soup.select("div.job_seen_beacon")
                    or soup.select("div.jobsearch-ResultsList > div")
                    or soup.select("div.result")
                    or soup.select("td.resultContent")
                    or soup.select("div[data-jk]")  # كل card فيها data-jk attribute
                )

                if not job_cards:
                    # نجرب نشوف لو الصفحة فيها CAPTCHA
                    if "captcha" in html.lower() or "blocked" in html.lower():
                        logger.warning(f"[Indeed/{country}] CAPTCHA/Block detected")
                        break

                    logger.info(f"[Indeed/{country}] No job cards found on page {page + 1}")
                    if page == 0:
                        # لو أول صفحة ومفيش نتائج — نطبع جزء من الـ HTML للـ debug
                        logger.debug(f"[Indeed/{country}] HTML snippet: {html[:500]}")
                    break

                for card in job_cards:
                    if len(country_jobs) >= config.max_jobs:
                        break

                    try:
                        # Title — جرب أكتر من selector
                        title_elem = (
                            card.select_one("h2.jobTitle a span")
                            or card.select_one("h2.jobTitle a")
                            or card.select_one("h2.jobTitle span")
                            or card.select_one("a[data-jk] span")
                            or card.select_one(".jobTitle")
                        )
                        if not title_elem:
                            continue
                        title = clean_text(title_elem.get_text())
                        if not title:
                            continue

                        # Company
                        company_elem = (
                            card.select_one("span[data-testid='company-name']")
                            or card.select_one("span.companyName")
                            or card.select_one("span.company")
                        )
                        company = (
                            clean_text(company_elem.get_text())
                            if company_elem else "Unknown"
                        )

                        # Location
                        location_elem = (
                            card.select_one("div[data-testid='text-location']")
                            or card.select_one("div.companyLocation")
                            or card.select_one("span.location")
                        )
                        location = (
                            clean_text(location_elem.get_text())
                            if location_elem else country
                        )

                        # URL
                        link_elem = (
                            card.select_one("h2.jobTitle a")
                            or card.select_one("a[data-jk]")
                            or card.select_one("a.jcs-JobTitle")
                        )
                        job_url = ""
                        if link_elem and link_elem.get("href"):
                            href = link_elem["href"]
                            job_url = (
                                href if href.startswith("http")
                                else f"{domain}{href}"
                            )
                        elif link_elem and link_elem.get("data-jk"):
                            jk = link_elem["data-jk"]
                            job_url = f"{domain}/viewjob?jk={jk}"

                        # Date
                        date_elem = (
                            card.select_one("span.date")
                            or card.select_one("span[data-testid='myJobsStateDate']")
                            or card.select_one("span.css-qvloho")
                        )
                        date_posted = None
                        if date_elem:
                            date_posted = parse_relative_date(date_elem.get_text())

                        # Description snippet
                        snippet_elem = (
                            card.select_one("div.job-snippet")
                            or card.select_one("div[class*='job-snippet']")
                            or card.select_one("td.resultContent div ul")
                        )
                        snippet = (
                            clean_text(snippet_elem.get_text())
                            if snippet_elem else ""
                        )

                        job_type = self.classify_job_type(
                            f"{location or ''} {snippet}"
                        )

                        raw_job = RawJob(
                            title=title,
                            company=company,
                            location=location,
                            description=snippet,
                            url=job_url,
                            date_posted=date_posted,
                            job_type=job_type,
                            source=self.SOURCE_NAME,
                        )
                        country_jobs.append(raw_job)

                    except Exception as e:
                        logger.warning(f"[Indeed/{country}] Error parsing card: {e}")
                        continue

                self._respectful_delay()

            logger.info(f"[Indeed/{country}] {len(country_jobs)} raw jobs for '{keyword}'")
            all_jobs.extend(country_jobs)

        filtered = self.filter_jobs(all_jobs, config)
        logger.info(f"[Indeed] Total after filtering: {len(filtered)} jobs")
        return filtered
