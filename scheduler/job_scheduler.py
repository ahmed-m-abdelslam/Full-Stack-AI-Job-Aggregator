"""Background scheduler for periodic scraping and AI processing."""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config.settings import settings
from scrapers.scraper_manager import ScraperManager
from ai_processing import AIProcessor
from utils.logger import logger


class JobScheduler:
    """Manages periodic background tasks."""

    def __init__(self):
        self.scheduler = BackgroundScheduler(
            job_defaults={
                "coalesce": True,         # لو فات وقت التشغيل — يشغلها مرة واحدة بس
                "max_instances": 1,       # مش هيشغل نفس الـ job مرتين في نفس الوقت
                "misfire_grace_time": 3600,  # لو اتأخر ساعة — يشغلها برضو
            }
        )
        self.scraper_manager = ScraperManager(
            sources=["remoteok", "linkedin", "wuzzuf"]  # المصادر الشغالة
        )
        self.ai_processor = AIProcessor()

    def _run_scraping_cycle(self) -> None:
        """Execute a full scraping cycle."""
        logger.info("=" * 60)
        logger.info("SCHEDULED SCRAPING CYCLE STARTED")
        logger.info("=" * 60)
        try:
            summary = self.scraper_manager.run_all(
                num_pages=3,
                # بيستخدم الإعدادات من .env (البلد والأيام والحد الأقصى)
            )
            logger.info(f"Scraping cycle complete: {summary['total_new']} new jobs found")
        except Exception as e:
            logger.error(f"Scraping cycle failed: {e}")

    def _run_ai_processing_cycle(self) -> None:
        """Execute AI processing on unprocessed jobs."""
        logger.info("=" * 60)
        logger.info("SCHEDULED AI PROCESSING CYCLE STARTED")
        logger.info("=" * 60)
        try:
            stats = self.ai_processor.process_unprocessed_jobs(batch_size=30)
            logger.info(f"AI processing complete: {stats}")
        except Exception as e:
            logger.error(f"AI processing cycle failed: {e}")

    def _run_full_cycle(self) -> None:
        """Run scraping then AI processing."""
        self._run_scraping_cycle()
        self._run_ai_processing_cycle()

    def start(self) -> None:
        """Start the scheduler with daily updates."""

        # ========== جدول 1: سحب يومي الساعة 8 الصبح ==========
        self.scheduler.add_job(
            self._run_full_cycle,
            trigger=CronTrigger(hour=8, minute=0),
            id="daily_morning_scrape",
            name="Daily Morning Scrape (8:00 AM)",
            replace_existing=True,
        )

        # ========== جدول 2: سحب تاني الساعة 8 بالليل ==========
        self.scheduler.add_job(
            self._run_full_cycle,
            trigger=CronTrigger(hour=20, minute=0),
            id="daily_evening_scrape",
            name="Daily Evening Scrape (8:00 PM)",
            replace_existing=True,
        )

        # ========== جدول 3: AI processing كل 4 ساعات ==========
        # عشان لو في وظائف اتسحبت ومتعالجتش
        self.scheduler.add_job(
            self._run_ai_processing_cycle,
            trigger=IntervalTrigger(hours=4),
            id="periodic_ai_processing",
            name="AI Processing Every 4 Hours",
            replace_existing=True,
        )

        self.scheduler.start()

        # طباعة الجدول
        logger.info("=" * 60)
        logger.info("SCHEDULER STARTED — Automatic Updates Enabled")
        logger.info("=" * 60)
        jobs = self.scheduler.get_jobs()
        for job in jobs:
            logger.info(f"  Scheduled: {job.name} — Next run: {job.next_run_time}")
        logger.info("=" * 60)

    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped.")

    def run_now(self) -> None:
        """Manually trigger a full cycle immediately."""
        self._run_full_cycle()

    def get_status(self) -> dict:
        """Get current scheduler status for the dashboard."""
        jobs = self.scheduler.get_jobs() if self.scheduler.running else []
        return {
            "running": self.scheduler.running if hasattr(self.scheduler, 'running') else False,
            "jobs": [
                {
                    "name": job.name,
                    "next_run": str(job.next_run_time) if job.next_run_time else "N/A",
                }
                for job in jobs
            ],
        }
