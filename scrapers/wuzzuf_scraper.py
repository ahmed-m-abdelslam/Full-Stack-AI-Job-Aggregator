"""Scraper for Wuzzuf — بالـ selectors الصح ومن غير فلاتر URL مكسورة."""

from urllib.parse import quote_plus
from bs4 import BeautifulSoup # type: ignore

from scrapers.base_scraper import BaseScraper, RawJob, ScrapeConfig
from utils.logger import logger # type: ignore
from utils.helpers import clean_text, parse_relative_date


class WuzzufScraper(BaseScraper):
    SOURCE_NAME = "wuzzuf"
    BASE_URL = "https://wuzzuf.net"

    def scrape(self, keyword: str, config: ScrapeConfig) -> list[RawJob]:
        raw_jobs: list[RawJob] = []
        encoded_keyword = quote_plus(keyword)

        for page in range(config.num_pages):
            if len(raw_jobs) >= config.max_jobs:
                break

            # بناء URL بسيط — بدون فلاتر عشان ما يعملش 500
            url = f"{self.BASE_URL}/search/jobs/?q={encoded_keyword}&start={page}"

            try:
                logger.info(f"[Wuzzuf] Page {page + 1} for '{keyword}'")
                response = self._get(url)
                soup = BeautifulSoup(response.text, "lxml")

                # الـ selectors الجديدة
                # كل job card = div.css-lptxge
                # العنوان = h2.css-193uk2c a
                # اللينك = a[href*="/jobs/p/"]
                job_links = soup.select('a[href*="/jobs/p/"]')

                if not job_links:
                    logger.info(f"[Wuzzuf] No jobs found on page {page + 1}")
                    break

                logger.info(f"[Wuzzuf] Found {len(job_links)} job links on page {page + 1}")

                for link in job_links:
                    if len(raw_jobs) >= config.max_jobs:
                        break

                    try:
                        # العنوان
                        title = clean_text(link.get_text())
                        if not title:
                            continue

                        # اللينك
                        href = link.get("href", "")
                        job_url = (
                            href if href.startswith("http")
                            else f"{self.BASE_URL}{href}"
                        )

                        # نطلع للـ card container عشان ناخد باقي البيانات
                        # h2 -> div.css-lptxge (أو نطلع 3-4 مستويات)
                        card = link
                        for _ in range(6):
                            parent = card.parent
                            if parent is None:
                                break
                            card = parent
                            # نوقف لما نلاقي div كبير فيه بيانات كتير
                            card_classes = card.get("class", [])
                            if card.name == "div" and card_classes:
                                # نتأكد إن الـ card فيه أكتر من element واحد
                                children = card.find_all(recursive=False)
                                if len(children) >= 2:
                                    break

                        # الشركة — نبحث عن تاني لينك أو span بعد العنوان
                        company = "Unknown"
                        # نبحث عن كل الـ links في الـ card
                        all_links = card.select("a") if card else []
                        for a in all_links:
                            a_href = a.get("href", "")
                            # لينك الشركة عادة بيكون /company/ أو مش /jobs/
                            if "/company/" in a_href or (
                                a_href and "/jobs/p/" not in a_href and a.get_text().strip()
                            ):
                                company_text = clean_text(a.get_text())
                                if company_text and company_text != title:
                                    company = company_text
                                    break

                        # لو ملقيناش — نجرب span tags
                        if company == "Unknown":
                            spans = card.select("span, a") if card else []
                            for sp in spans:
                                sp_text = clean_text(sp.get_text())
                                if (
                                    sp_text
                                    and sp_text != title
                                    and len(sp_text) < 100
                                    and not any(kw in sp_text.lower() for kw in [
                                        "day", "ago", "remote", "hybrid", "full time",
                                        "part time", "apply", "save",
                                    ])
                                ):
                                    company = sp_text
                                    break

                        # الموقع
                        location = None
                        location_keywords = [
                            "cairo", "egypt", "alexandria", "giza",
                            "remote", "hybrid", "onsite",
                        ]
                        if card:
                            all_text_spans = card.select("span, div")
                            for sp in all_text_spans:
                                sp_text = clean_text(sp.get_text()).lower()
                                if any(kw in sp_text for kw in location_keywords):
                                    location = clean_text(sp.get_text())
                                    # لو النص قصير ومعقول يكون location
                                    if len(location) < 80:
                                        break
                                    location = None

                        # التاريخ
                        date_posted = None
                        if card:
                            time_indicators = ["ago", "day", "hour", "week", "month", "just"]
                            for sp in card.select("span, div"):
                                sp_text = sp.get_text().strip().lower()
                                if any(ind in sp_text for ind in time_indicators):
                                    date_posted = parse_relative_date(sp_text)
                                    if date_posted:
                                        break

                        # نوع الوظيفة
                        job_type = None
                        if card:
                            card_text = card.get_text().lower()
                            job_type = self.classify_job_type(card_text)

                        raw_job = RawJob(
                            title=title,
                            company=company,
                            location=location or "Egypt",
                            description="",
                            url=job_url,
                            date_posted=date_posted,
                            job_type=job_type,
                            source=self.SOURCE_NAME,
                        )
                        raw_jobs.append(raw_job)

                    except Exception as e:
                        logger.warning(f"[Wuzzuf] Error parsing job: {e}")
                        continue

                self._respectful_delay()

            except Exception as e:
                logger.error(f"[Wuzzuf] Page {page + 1} failed for '{keyword}': {e}")
                continue

        logger.info(f"[Wuzzuf] Raw total: {len(raw_jobs)} jobs for '{keyword}'")

        # فلترة بالبلد والتاريخ
        filtered = self.filter_jobs(raw_jobs, config)
        logger.info(f"[Wuzzuf] After filtering: {len(filtered)} jobs")
        return filtered
