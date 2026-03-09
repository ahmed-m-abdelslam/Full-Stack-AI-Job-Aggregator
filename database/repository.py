"""Data access layer for job operations."""
from sqlalchemy import select, func, or_, and_, desc
from datetime import datetime
from datetime import datetime
from typing import Optional
from sqlalchemy import select, func, or_, and_, desc
from sqlalchemy.orm import Session

from database.models import Job, ScrapeLog
from database.connection import get_session
from utils.logger import logger
from utils.helpers import generate_job_hash


class JobRepository:
    """Repository class encapsulating all job database operations."""

    @staticmethod
    def upsert_job(session: Session, job_data: dict) -> tuple[Job, bool]:
        """
        Insert a new job or skip if it already exists (by hash).
        Returns the job and a boolean indicating whether it was newly created.
        """
        job_hash = generate_job_hash(
            job_data["title"], job_data["company"], job_data["url"]
        )
        existing = session.execute(
            select(Job).where(Job.job_hash == job_hash)
        ).scalar_one_or_none()

        if existing:
            return existing, False

        job = Job(job_hash=job_hash, **job_data)
        session.add(job)
        session.flush()
        return job, True

    @staticmethod
    def get_jobs(
        session: Session,
        title_filter: Optional[str] = None,
        company_filter: Optional[str] = None,
        location_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        job_type_filter: Optional[str] = None,
        source_filter: Optional[str] = None,
        search_query: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        exclude_duplicates: bool = True,
        limit: int = 200,
        offset: int = 0,
    ) -> list[Job]:
        """Retrieve jobs with optional filters including date range."""
        stmt = select(Job)

        if exclude_duplicates:
            stmt = stmt.where(Job.is_duplicate == False)

        if title_filter:
            stmt = stmt.where(Job.title.ilike(f"%{title_filter}%"))
        if company_filter:
            stmt = stmt.where(Job.company.ilike(f"%{company_filter}%"))
        if location_filter:
            stmt = stmt.where(Job.location.ilike(f"%{location_filter}%"))
        if category_filter:
            stmt = stmt.where(Job.category == category_filter)
        if job_type_filter:
            stmt = stmt.where(Job.job_type == job_type_filter)
        if source_filter:
            stmt = stmt.where(Job.source == source_filter)

        # فلتر التاريخ
        if date_from:
            stmt = stmt.where(
                or_(
                    Job.date_posted >= date_from,
                    Job.date_posted.is_(None)  # نعرض الوظائف اللي مفيهاش تاريخ برضو
                )
            )
        if date_to:
            stmt = stmt.where(
                or_(
                    Job.date_posted <= date_to,
                    Job.date_posted.is_(None)
                )
            )

        if search_query:
            pattern = f"%{search_query}%"
            stmt = stmt.where(
                or_(
                    Job.title.ilike(pattern),
                    Job.company.ilike(pattern),
                    Job.description.ilike(pattern),
                    Job.summary.ilike(pattern),
                )
            )

        stmt = stmt.order_by(desc(Job.date_posted), desc(Job.created_at))
        stmt = stmt.limit(limit).offset(offset)
        result = session.execute(stmt).scalars().all()
        return list(result)


    @staticmethod
    def count_jobs(session: Session, exclude_duplicates: bool = True) -> int:
        stmt = select(func.count(Job.id))
        if exclude_duplicates:
            stmt = stmt.where(Job.is_duplicate == False)
        return session.execute(stmt).scalar() or 0

    @staticmethod
    def get_filter_options(session: Session) -> dict:
        """Retrieve distinct values for all filterable columns."""
        def distinct_values(column):
            result = session.execute(
                select(column)
                .where(column.isnot(None))
                .where(Job.is_duplicate == False)
                .distinct()
                .order_by(column)
            ).scalars().all()
            return [v for v in result if v]

        return {
            "categories": distinct_values(Job.category),
            "job_types": distinct_values(Job.job_type),
            "sources": distinct_values(Job.source),
            "companies": distinct_values(Job.company),
            "locations": distinct_values(Job.location),
        }

    @staticmethod
    def get_jobs_without_embeddings(session: Session, limit: int = 100) -> list[Job]:
        stmt = (
            select(Job)
            .where(Job.embedding.is_(None))
            .where(Job.description.isnot(None))
            .limit(limit)
        )
        return list(session.execute(stmt).scalars().all())

    @staticmethod
    def get_jobs_without_ai_processing(session: Session, limit: int = 50) -> list[Job]:
        stmt = (
            select(Job)
            .where(Job.summary.is_(None))
            .where(Job.description.isnot(None))
            .limit(limit)
        )
        return list(session.execute(stmt).scalars().all())

    @staticmethod
    def log_scrape(
        session: Session,
        source: str,
        keyword: str,
        jobs_found: int,
        jobs_new: int,
        jobs_duplicate: int,
        status: str,
        error_message: Optional[str] = None,
        duration_seconds: Optional[float] = None,
    ) -> ScrapeLog:
        log = ScrapeLog(
            source=source,
            keyword=keyword,
            jobs_found=jobs_found,
            jobs_new=jobs_new,
            jobs_duplicate=jobs_duplicate,
            status=status,
            error_message=error_message,
            duration_seconds=duration_seconds,
            completed_at=datetime.utcnow() if status != "running" else None,
        )
        session.add(log)
        session.flush()
        return log
