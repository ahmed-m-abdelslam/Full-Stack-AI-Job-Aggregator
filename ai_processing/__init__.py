"""AI Processing Pipeline — orchestrates summarization, skill extraction, classification, and deduplication."""

from typing import Optional

from database.connection import get_session
from database.repository import JobRepository
from ai_processing.summarizer import summarize_job
from ai_processing.skill_extractor import extract_skills
from ai_processing.job_classifier import classify_job
from ai_processing.duplicate_detector import DuplicateDetector
from utils.logger import logger # type: ignore


class AIProcessor:
    """Runs the full AI enrichment pipeline on unprocessed jobs."""

    def __init__(self):
        self.duplicate_detector = DuplicateDetector()

    def process_unprocessed_jobs(self, batch_size: int = 50) -> dict:
        """Process all jobs that haven't been enriched with AI yet."""
        stats = {
            "summarized": 0,
            "skills_extracted": 0,
            "classified": 0,
            "embeddings_generated": 0,
            "duplicates_found": 0,
            "errors": 0,
        }

        with get_session() as session:
            jobs = JobRepository.get_jobs_without_ai_processing(session, limit=batch_size)
            logger.info(f"Processing {len(jobs)} jobs with AI pipeline...")

            for job in jobs:
                try:
                    # 1. Summarize
                    if job.description and not job.summary:
                        summary = summarize_job(job.description)
                        if summary:
                            job.summary = summary
                            stats["summarized"] += 1

                    # 2. Extract skills
                    if job.description and not job.extracted_skills:
                        skills = extract_skills(job.description)
                        if skills:
                            job.extracted_skills = skills
                            stats["skills_extracted"] += 1

                    # 3. Classify
                    if not job.category:
                        category = classify_job(job.title, job.description or "")
                        if category:
                            job.category = category
                            stats["classified"] += 1

                except Exception as e:
                    logger.error(f"AI processing failed for job #{job.id}: {e}")
                    stats["errors"] += 1
                    continue

        # 4. Generate embeddings
        stats["embeddings_generated"] = self.duplicate_detector.generate_embeddings(
            batch_size=batch_size
        )

        # 5. Detect duplicates
        stats["duplicates_found"] = self.duplicate_detector.detect_duplicates()

        logger.info(f"AI processing complete: {stats}")
        return stats
