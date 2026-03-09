"""SQLAlchemy ORM models for the job aggregator database."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, Boolean,
    UniqueConstraint, Index, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # Core fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str] = mapped_column(String(300), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    date_posted: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    job_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Remote/Hybrid/Onsite
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # linkedin/indeed/etc.

    # AI-enriched fields
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_skills: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ai_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Embedding for duplicate detection
    embedding = Column(Vector(384), nullable=True)  # all-MiniLM-L6-v2 produces 384-dim

    # Deduplication
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duplicate_of_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_jobs_title_company", "title", "company"),
        Index("ix_jobs_source", "source"),
        Index("ix_jobs_category", "category"),
        Index("ix_jobs_date_posted", "date_posted"),
        Index("ix_jobs_is_duplicate", "is_duplicate"),
    )

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, title='{self.title}', company='{self.company}', source='{self.source}')>"


class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    jobs_found: Mapped[int] = mapped_column(Integer, default=0)
    jobs_new: Mapped[int] = mapped_column(Integer, default=0)
    jobs_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success / error
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
