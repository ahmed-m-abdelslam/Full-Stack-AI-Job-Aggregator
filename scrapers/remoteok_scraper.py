"""Scraper for RemoteOK — مع إصلاح API والتعامل مع كلمات البحث."""

from datetime import datetime
from typing import Optional

from scrapers.base_scraper import BaseScraper, RawJob, ScrapeConfig
from utils.logger import logger # type: ignore
from utils.helpers import clean_text


class RemoteOKScraper(BaseScraper):
    SOURCE_NAME = "remoteok"
    BASE_URL = "https://remoteok.com"

    # RemoteOK بيشتغل بـ tags مش كلمات كاملة
    # فمحتاجين نحول الكلمات الطويلة لـ tags قصيرة
    KEYWORD_TO_TAGS = {
        "artificial intelligence": "ai",
        "machine learning": "machine-learning",
        "data scientist": "data-science",
        "data science": "data-science",
        "nlp engineer": "nlp",
        "llm engineer": "ai",
        "ai engineer": "ai",
        "deep learning": "machine-learning",
        "natural language processing": "nlp",
    }

    def scrape(self, keyword: str, config: ScrapeConfig) -> list[RawJob]:
        raw_jobs: list[RawJob] = []

        # تحويل الكلمة لـ tag مناسب لـ RemoteOK
        tag = self.KEYWORD_TO_TAGS.get(keyword.lower(), keyword.lower().replace(" ", "-"))

        # RemoteOK API — نجرب الـ tag وكمان بدون tag
        urls_to_try = [
            f"{self.BASE_URL}/api?tag={tag}",
            f"{self.BASE_URL}/api?tag=ai",  # fallback
        ]

        seen_urls = set()

        for api_url in urls_to_try:
            if len(raw_jobs) >= config.max_jobs:
                break

            try:
                logger.info(f"[RemoteOK] Fetching: {api_url}")
                response = self._get(api_url)

                # التحقق من نوع الرد
                content_type = response.headers.get("content-type", "")
                if "json" not in content_type and "text" not in content_type:
                    logger.warning(f"[RemoteOK] Unexpected content type: {content_type}")
                    continue

                data = response.json()

                if not isinstance(data, list):
                    logger.warning(f"[RemoteOK] Response is not a list: {type(data)}")
                    continue

                # أول عنصر = metadata — نتخطاه
                listings = data[1:] if len(data) > 1 else []
                logger.info(f"[RemoteOK] Got {len(listings)} listings from API")

                for item in listings:
                    if len(raw_jobs) >= config.max_jobs:
                        break

                    try:
                        # RemoteOK ممكن يرجع مفاتيح مختلفة
                        title = (
                            item.get("position")
                            or item.get("title")
                            or ""
                        ).strip()

                        company = (
                            item.get("company")
                            or item.get("company_name")
                            or ""
                        ).strip()

                        if not title or not company:
                            continue

                        # تفادي التكرار
                        url_slug = item.get("url", "") or item.get("slug", "")
                        job_url = (
                            f"{self.BASE_URL}{url_slug}"
                            if url_slug and not url_slug.startswith("http")
                            else url_slug
                        )

                        if job_url in seen_urls:
                            continue
                        seen_urls.add(job_url)

                        # الوصف
                        description = clean_text(
                            item.get("description", "")
                            or item.get("description_html", "")
                        )

                        # الموقع
                        location = (
                            item.get("location", "")
                            or item.get("candidate_required_location", "")
                            or "Worldwide (Remote)"
                        )

                        # التاريخ
                        date_posted = None
                        date_str = item.get("date", "") or item.get("created_at", "")
                        if date_str:
                            try:
                                date_posted = datetime.fromisoformat(
                                    date_str.replace("Z", "+00:00")
                                )
                            except (ValueError, TypeError):
                                pass

                        # Epoch timestamp
                        if not date_posted and item.get("epoch"):
                            try:
                                date_posted = datetime.fromtimestamp(int(item["epoch"]))
                            except (ValueError, TypeError, OSError):
                                pass

                        # التحقق من نطاق التاريخ قبل ما نضيف
                        if not config.is_within_date_range(date_posted):
                            continue

                        # التحقق من الـ keyword في العنوان أو الوصف
                        keyword_lower = keyword.lower()
                        text_to_search = f"{title} {description} {' '.join(item.get('tags', []))}".lower()

                        # مطابقة مرنة — أي جزء من الكلمة
                        keyword_parts = keyword_lower.split()
                        if not any(part in text_to_search for part in keyword_parts):
                            continue

                        raw_job = RawJob(
                            title=title,
                            company=company,
                            location=location,
                            description=description,
                            url=job_url,
                            date_posted=date_posted,
                            job_type="Remote",
                            source=self.SOURCE_NAME,
                        )
                        raw_jobs.append(raw_job)

                    except Exception as e:
                        logger.warning(f"[RemoteOK] Error parsing item: {e}")
                        continue

            except Exception as e:
                logger.warning(f"[RemoteOK] API call failed for {api_url}: {e}")
                continue

            # لو لقينا نتائج من أول URL — مش محتاجين fallback
            if raw_jobs:
                break

        logger.info(f"[RemoteOK] Raw total: {len(raw_jobs)} jobs for '{keyword}'")

        # فلتر البلد (Remote = مقبول لأي بلد)
        filtered = self.filter_jobs(raw_jobs, config)
        logger.info(f"[RemoteOK] After filtering: {len(filtered)} jobs")
        return filtered
