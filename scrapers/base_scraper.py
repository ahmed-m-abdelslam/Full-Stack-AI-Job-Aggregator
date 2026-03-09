"""Abstract base class for all job scrapers — مع فلاتر البلد والتاريخ."""

import time
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

import requests
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config.settings import settings
from utils.logger import logger


@dataclass
class ScrapeConfig:
    """إعدادات السحب — البلد والتاريخ والحدود."""
    countries: list[str]
    date_from: Optional[datetime]
    date_to: Optional[datetime]
    max_jobs: int
    keywords: list[str]
    num_pages: int = 3

    @classmethod
    def from_settings(cls, num_pages: int = 3) -> "ScrapeConfig":
        """إنشاء الإعدادات من ملف الـ .env تلقائياً."""
        date_from, date_to = settings.get_date_range()
        return cls(
            countries=settings.get_target_countries_list(),
            date_from=date_from,
            date_to=date_to,
            max_jobs=settings.max_jobs_per_source,
            keywords=settings.search_keywords,
            num_pages=num_pages,
        )

    def is_within_date_range(self, date: Optional[datetime]) -> bool:
        """تحقق إن التاريخ داخل النطاق المطلوب — يتعامل مع aware و naive."""
        if date is None:
            return True

        from datetime import timezone

        # توحيد الـ timezone — خلي كل التواريخ aware
        def make_aware(dt: datetime) -> datetime:
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        date = make_aware(date)

        if self.date_from:
            date_from = make_aware(self.date_from)
            if date < date_from:
                return False

        if self.date_to:
            date_to = make_aware(self.date_to)
            if date > date_to:
                return False

        return True


    def matches_country(self, location: Optional[str]) -> bool:
        """تحقق إن الموقع يطابق أحد البلدان المطلوبة."""
        if not self.countries:
            return True  # لو مفيش بلدان محددة — نمرر كل حاجة
        if not location:
            return True  # لو مفيش موقع — نمرره (أحسن من إننا نضيعه)

        location_lower = location.lower().strip()

        # ★ Remote jobs تتقبل دايماً — لأنها متاحة لأي بلد
        remote_keywords = ["remote", "anywhere", "worldwide", "global", "work from home", "wfh"]
        if any(kw in location_lower for kw in remote_keywords):
            return True

        # خريطة الاختصارات والمرادفات لأشهر البلدان
        country_aliases = {
            "egypt": ["egypt", "cairo", "alexandria", "giza", "مصر"],
            "uae": ["uae", "united arab emirates", "dubai", "abu dhabi", "الإمارات"],
            "saudi arabia": ["saudi", "saudi arabia", "riyadh", "jeddah", "السعودية", "ksa"],
            "united states": ["united states", "usa", "us", "new york", "san francisco",
                            "california", "remote us", "seattle", "austin", "boston"],
            "united kingdom": ["united kingdom", "uk", "london", "manchester", "england"],
            "germany": ["germany", "berlin", "munich", "deutschland"],
            "canada": ["canada", "toronto", "vancouver", "montreal"],
            "india": ["india", "bangalore", "mumbai", "delhi", "hyderabad"],
            "remote": ["remote", "anywhere", "worldwide", "global", "work from home"],
            "qatar": ["qatar", "doha", "قطر"],
            "kuwait": ["kuwait", "الكويت"],
            "bahrain": ["bahrain", "البحرين"],
            "oman": ["oman", "muscat", "عمان"],
            "jordan": ["jordan", "amman", "الأردن"],
            "lebanon": ["lebanon", "beirut", "لبنان"],
            "morocco": ["morocco", "casablanca", "المغرب"],
            "tunisia": ["tunisia", "tunis", "تونس"],
        }

        for target_country in self.countries:
            target_lower = target_country.lower().strip()

            # مطابقة مباشرة
            if target_lower in location_lower:
                return True

            # مطابقة عبر المرادفات
            aliases = country_aliases.get(target_lower, [])
            for alias in aliases:
                if alias in location_lower:
                    return True

        return False


    def get_location_query(self) -> str:
        """إرجاع نص البلد لاستخدامه في استعلام البحث."""
        if not self.countries:
            return ""
        return self.countries[0]  # نستخدم أول بلد كأساس للبحث


@dataclass
class RawJob:
    """Data transfer object for a scraped job before database insertion."""
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    url: str = ""
    date_posted: Optional[datetime] = None
    job_type: Optional[str] = None
    source: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description,
            "url": self.url,
            "date_posted": self.date_posted,
            "job_type": self.job_type,
            "source": self.source,
        }


class BaseScraper(ABC):
    """Base class providing common scraping infrastructure."""

    SOURCE_NAME: str = "unknown"
    BASE_URL: str = ""

    def __init__(self):
        self.ua = UserAgent()
        self.session = requests.Session()
        self._update_headers()

    def _update_headers(self) -> None:
        self.session.headers.update({
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        })

    def _respectful_delay(self) -> None:
        delay = settings.request_delay_seconds + random.uniform(0.5, 2.0)
        time.sleep(delay)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    )
    def _get(self, url: str, params: Optional[dict] = None) -> requests.Response:
        self._update_headers()
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response

    @abstractmethod
    def scrape(self, keyword: str, config: ScrapeConfig) -> list[RawJob]:
        """Scrape jobs for a given keyword with country and date filters."""
        ...

    def classify_job_type(self, text: str) -> Optional[str]:
        text_lower = (text or "").lower()
        if any(w in text_lower for w in ["remote", "work from home", "wfh", "anywhere"]):
            return "Remote"
        if any(w in text_lower for w in ["hybrid", "flexible"]):
            return "Hybrid"
        if any(w in text_lower for w in ["onsite", "on-site", "in-office", "office"]):
            return "Onsite"
        return None

    def filter_jobs(self, jobs: list[RawJob], config: ScrapeConfig) -> list[RawJob]:
        """فلترة الوظائف حسب البلد والتاريخ والحد الأقصى."""
        filtered = []
        skipped_country = 0
        skipped_date = 0

        for job in jobs:
            # فلتر البلد
            if not config.matches_country(job.location):
                skipped_country += 1
                continue

            # فلتر التاريخ
            if not config.is_within_date_range(job.date_posted):
                skipped_date += 1
                continue

            filtered.append(job)

            # الحد الأقصى
            if len(filtered) >= config.max_jobs:
                logger.info(
                    f"[{self.SOURCE_NAME}] Reached max jobs limit ({config.max_jobs})"
                )
                break

        if skipped_country > 0 or skipped_date > 0:
            logger.info(
                f"[{self.SOURCE_NAME}] Filtered out: "
                f"{skipped_country} wrong country, {skipped_date} out of date range"
            )

        return filtered
