"""Orchestrates all scrapers — مع ScrapeConfig للتحكم في البلد والتاريخ."""

import time
from datetime import datetime
from typing import Optional

from scrapers.base_scraper import BaseScraper, RawJob, ScrapeConfig
from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.indeed_scraper import IndeedScraper
from scrapers.wuzzuf_scraper import WuzzufScraper
from scrapers.remoteok_scraper import RemoteOKScraper
from scrapers.glassdoor_scraper import GlassdoorScraper
from database.connection import get_session
from database.repository import JobRepository
from config.settings import settings
from utils.logger import logger


class ScraperManager:
    SCRAPER_CLASSES: list[type[BaseScraper]] = [
        RemoteOKScraper,
        IndeedScraper,
        LinkedInScraper,
        WuzzufScraper,
        GlassdoorScraper,
    ]

    def __init__(self, sources: Optional[list[str]] = None):
        self.scrapers: list[BaseScraper] = []
        for cls in self.SCRAPER_CLASSES:
            if sources is None or cls.SOURCE_NAME in sources:
                self.scrapers.append(cls())

        logger.info(
            f"ScraperManager: {len(self.scrapers)} scrapers — "
            f"{[s.SOURCE_NAME for s in self.scrapers]}"
        )

    def run_all(
        self,
        keywords: Optional[list[str]] = None,
        num_pages: int = 3,
        countries: Optional[list[str]] = None,
        days_back: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_jobs: Optional[int] = None,
    ) -> dict:
        """
        تشغيل كل السكرابرز مع إمكانية تخصيص الفلاتر.

        Args:
            keywords:   كلمات البحث (لو None → من الإعدادات)
            num_pages:  عدد الصفحات لكل مصدر
            countries:  قائمة البلدان (لو None → من الإعدادات)
            days_back:  عدد الأيام (لو None → من الإعدادات)
            date_from:  تاريخ بداية "YYYY-MM-DD" (اختياري)
            date_to:    تاريخ نهاية "YYYY-MM-DD" (اختياري)
            max_jobs:   الحد الأقصى لكل مصدر/كلمة
        """
        # بناء ScrapeConfig
        if countries or days_back or date_from or max_jobs:
            # فلاتر مخصصة من المستخدم
            from datetime import timedelta

            if date_from and date_to:
                dt_from = datetime.strptime(date_from, "%Y-%m-%d")
                dt_to = datetime.strptime(date_to, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59
                )
            elif days_back:
                dt_to = datetime.utcnow()
                dt_from = dt_to - timedelta(days=days_back)
            else:
                dt_from, dt_to = settings.get_date_range()

            config = ScrapeConfig(
                countries=countries or settings.get_target_countries_list(),
                date_from=dt_from,
                date_to=dt_to,
                max_jobs=max_jobs or settings.max_jobs_per_source,
                keywords=keywords or settings.search_keywords,
                num_pages=num_pages,
            )
        else:
            config = ScrapeConfig.from_settings(num_pages=num_pages)

        if keywords:
            config.keywords = keywords

        # طباعة ملخص الإعدادات
        logger.info("=" * 60)
        logger.info("SCRAPE CONFIGURATION:")
        logger.info(f"  Countries:  {config.countries}")
        logger.info(f"  Date range: {config.date_from} → {config.date_to}")
        logger.info(f"  Max jobs:   {config.max_jobs} per source/keyword")
        logger.info(f"  Keywords:   {config.keywords}")
        logger.info(f"  Pages:      {config.num_pages}")
        logger.info("=" * 60)

        summary = {
            "total_found": 0,
            "total_new": 0,
            "total_duplicate": 0,
            "errors": 0,
            "config": {
                "countries": config.countries,
                "date_from": str(config.date_from),
                "date_to": str(config.date_to),
                "max_jobs": config.max_jobs,
            },
            "by_source": {},
        }

        for scraper in self.scrapers:
            source = scraper.SOURCE_NAME
            summary["by_source"][source] = {"found": 0, "new": 0, "errors": 0}

            for keyword in config.keywords:
                start_time = time.time()
                try:
                    logger.info(f"[{source}] Scraping '{keyword}'...")
                    raw_jobs = scraper.scrape(keyword, config=config)
                    duration = time.time() - start_time

                    new_count = 0
                    with get_session() as session:
                        for raw_job in raw_jobs:
                            try:
                                _, is_new = JobRepository.upsert_job(
                                    session, raw_job.to_dict()
                                )
                                if is_new:
                                    new_count += 1
                            except Exception as e:
                                logger.warning(f"Insert failed: {e}")
                                continue

                        dup_count = len(raw_jobs) - new_count
                        JobRepository.log_scrape(
                            session,
                            source=source,
                            keyword=keyword,
                            jobs_found=len(raw_jobs),
                            jobs_new=new_count,
                            jobs_duplicate=dup_count,
                            status="success",
                            duration_seconds=duration,
                        )

                    summary["total_found"] += len(raw_jobs)
                    summary["total_new"] += new_count
                    summary["total_duplicate"] += dup_count
                    summary["by_source"][source]["found"] += len(raw_jobs)
                    summary["by_source"][source]["new"] += new_count

                    logger.info(
                        f"[{source}] '{keyword}': {len(raw_jobs)} found, "
                        f"{new_count} new ({duration:.1f}s)"
                    )

                except Exception as e:
                    duration = time.time() - start_time
                    logger.error(f"[{source}] Failed for '{keyword}': {e}")
                    summary["errors"] += 1
                    summary["by_source"][source]["errors"] += 1

                    with get_session() as session:
                        JobRepository.log_scrape(
                            session,
                            source=source, keyword=keyword,
                            jobs_found=0, jobs_new=0, jobs_duplicate=0,
                            status="error", error_message=str(e),
                            duration_seconds=duration,
                        )

        logger.info(
            f"Scraping complete: {summary['total_found']} found, "
            f"{summary['total_new']} new, {summary['errors']} errors"
        )
        return summary
