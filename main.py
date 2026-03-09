#!/usr/bin/env python3
"""
AI Job Aggregator — Main entry point.

Usage:
    python main.py serve
    python main.py scrape
    python main.py scrape --countries Egypt,UAE --days 3 --max-jobs 30
    python main.py scrape --countries "United States" --from 2025-03-01 --to 2025-03-09
    python main.py process
    python main.py init
    python main.py full --countries Egypt --days 7
"""

import sys
import argparse

from dotenv import load_dotenv # type: ignore
load_dotenv()

from config.settings import settings
from database.connection import init_db
from utils.logger import logger # type: ignore


def cmd_init(args):
    logger.info("Initializing database...")
    init_db()
    logger.info("Database ready.")


def cmd_scrape(args):
    from scrapers.scraper_manager import ScraperManager

    init_db()

    # قراءة الفلاتر من الأوامر أو من الإعدادات
    countries = None
    if args.countries:
        countries = [c.strip() for c in args.countries.split(",")]

    manager = ScraperManager(
        sources=args.sources.split(",") if args.sources else None
    )

    summary = manager.run_all(
        keywords=args.keywords.split(",") if args.keywords else None,
        num_pages=args.pages,
        countries=countries,
        days_back=args.days,
        date_from=args.date_from,
        date_to=args.date_to,
        max_jobs=args.max_jobs,
    )

    logger.info(f"Scraping complete: {summary}")
    return summary


def cmd_process(args):
    from ai_processing import AIProcessor

    init_db()
    processor = AIProcessor()
    stats = processor.process_unprocessed_jobs(batch_size=args.batch_size)
    logger.info(f"Processing complete: {stats}")
    return stats


def cmd_serve(args):
    from web_app.app import create_app
    from scheduler.job_scheduler import JobScheduler

    init_db()

    scheduler = JobScheduler()
    scheduler.start()

    app = create_app()

    port = settings.get_port()
    host = settings.dash_host

    logger.info(f"Dashboard at http://{host}:{port}")

    try:
        app.run(
            host=host,
            port=port,
            debug=settings.dash_debug,
        )
    finally:
        scheduler.stop()




def cmd_full(args):
    cmd_scrape(args)
    cmd_process(args)
    cmd_serve(args)


def main():
    parser = argparse.ArgumentParser(
        description="AI Job Aggregator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py init
  python main.py scrape --countries Egypt --days 7
  python main.py scrape --countries "Egypt,UAE" --days 3 --max-jobs 30
  python main.py scrape --countries "United States" --from 2025-03-01 --to 2025-03-09
  python main.py scrape --sources remoteok,indeed --days 7
  python main.py process --batch-size 20
  python main.py serve
  python main.py full --countries Egypt --days 7
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # ---- init ----
    subparsers.add_parser("init", help="Initialize the database")

    # ---- scrape ----
    scrape_parser = subparsers.add_parser("scrape", help="Run scrapers")
    scrape_parser.add_argument(
        "--countries", "-c",
        type=str, default=None,
        help='البلدان مفصولة بفاصلة، مثال: "Egypt,UAE,Saudi Arabia"'
    )
    scrape_parser.add_argument(
        "--days", "-d",
        type=int, default=None,
        help="عدد الأيام اللي فاتت (مثال: 7 = آخر أسبوع)"
    )
    scrape_parser.add_argument(
        "--date-from", "--from",
        type=str, default=None, dest="date_from",
        help="تاريخ البداية (YYYY-MM-DD)"
    )
    scrape_parser.add_argument(
        "--date-to", "--to",
        type=str, default=None, dest="date_to",
        help="تاريخ النهاية (YYYY-MM-DD)"
    )
    scrape_parser.add_argument(
        "--max-jobs", "-m",
        type=int, default=None,
        help="الحد الأقصى للوظائف لكل مصدر/كلمة بحث"
    )
    scrape_parser.add_argument(
        "--pages", "-p",
        type=int, default=3,
        help="عدد الصفحات لكل مصدر (default: 3)"
    )
    scrape_parser.add_argument(
        "--sources", "-s",
        type=str, default=None,
        help='المصادر مفصولة بفاصلة: "remoteok,indeed,linkedin,wuzzuf,glassdoor"'
    )
    scrape_parser.add_argument(
        "--keywords", "-k",
        type=str, default=None,
        help='كلمات البحث مفصولة بفاصلة: "AI Engineer,Data Scientist"'
    )

    # ---- process ----
    process_parser = subparsers.add_parser("process", help="Run AI processing")
    process_parser.add_argument(
        "--batch-size", "-b",
        type=int, default=50,
        help="عدد الوظائف اللي تتعالج في الدفعة الواحدة"
    )

    # ---- serve ----
    subparsers.add_parser("serve", help="Start web dashboard")

    # ---- full ----
    full_parser = subparsers.add_parser("full", help="Scrape + Process + Serve")
    full_parser.add_argument("--countries", "-c", type=str, default=None)
    full_parser.add_argument("--days", "-d", type=int, default=None)
    full_parser.add_argument("--date-from", "--from", type=str, default=None, dest="date_from")
    full_parser.add_argument("--date-to", "--to", type=str, default=None, dest="date_to")
    full_parser.add_argument("--max-jobs", "-m", type=int, default=None)
    full_parser.add_argument("--pages", "-p", type=int, default=3)
    full_parser.add_argument("--sources", "-s", type=str, default=None)
    full_parser.add_argument("--keywords", "-k", type=str, default=None)
    full_parser.add_argument("--batch-size", "-b", type=int, default=50)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "init": cmd_init,
        "scrape": cmd_scrape,
        "process": cmd_process,
        "serve": cmd_serve,
        "full": cmd_full,
    }

    try:
        commands[args.command](args)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
