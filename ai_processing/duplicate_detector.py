"""Detects duplicate job postings using sentence-transformer embeddings and cosine similarity."""

import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy import select, text
from typing import Optional

from config.settings import settings
from database.connection import get_session
from database.models import Job
from utils.logger import logger


class DuplicateDetector:
    """Detects and marks duplicate job listings using embedding similarity."""

    def __init__(self):
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        self.model = SentenceTransformer(settings.embedding_model)
        self.threshold = settings.duplicate_similarity_threshold
        logger.info(f"Embedding model loaded. Similarity threshold: {self.threshold}")

    def compute_embedding(self, text: str) -> Optional[np.ndarray]:
        if not text or len(text.strip()) < 10:
            return None
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding

    def create_job_text(self, job: Job) -> str:
        parts = [job.title or "", job.company or ""]
        if job.description:
            parts.append(job.description[:1000])
        if job.location:
            parts.append(job.location)
        return " | ".join(p for p in parts if p)

    def _embedding_to_pgvector_str(self, embedding) -> str:
        """تحويل numpy array أو list لـ pgvector format string."""
        if isinstance(embedding, np.ndarray):
            values = embedding.flatten().tolist()
        elif isinstance(embedding, list):
            # لو list of lists أو list عادية
            if len(embedding) > 0 and isinstance(embedding[0], list):
                values = embedding[0]
            else:
                values = embedding
        else:
            values = list(embedding)

        # pgvector format: [0.1,0.2,0.3,...]
        return "[" + ",".join(f"{v:.8f}" for v in values) + "]"

    def generate_embeddings(self, batch_size: int = 100) -> int:
        processed = 0

        with get_session() as session:
            jobs = list(
                session.execute(
                    select(Job)
                    .where(Job.embedding.is_(None))
                    .where(Job.title.isnot(None))
                    .limit(batch_size)
                ).scalars().all()
            )

            if not jobs:
                logger.info("No jobs need embeddings.")
                return 0

            texts = [self.create_job_text(job) for job in jobs]
            embeddings = self.model.encode(
                texts, normalize_embeddings=True, show_progress_bar=True
            )

            for job, embedding in zip(jobs, embeddings):
                # تحويل لـ list عادية عشان pgvector يفهمها
                job.embedding = embedding.tolist()
                processed += 1

        logger.info(f"Generated embeddings for {processed} jobs.")
        return processed

    def detect_duplicates(self) -> int:
        duplicates_found = 0

        with get_session() as session:
            jobs = list(
                session.execute(
                    select(Job)
                    .where(Job.embedding.isnot(None))
                    .where(Job.is_duplicate == False)
                    .order_by(Job.created_at)
                ).scalars().all()
            )

            if len(jobs) < 2:
                return 0

            logger.info(f"Checking {len(jobs)} jobs for duplicates...")

            max_distance = 1.0 - self.threshold

            for i, job in enumerate(jobs):
                if job.is_duplicate:
                    continue

                embedding_str = self._embedding_to_pgvector_str(job.embedding)

                try:
                    # استخدام CAST بدل :: عشان SQLAlchemy ما يتلخبطش
                    similar = session.execute(
                        text("""
                            SELECT id, 1 - (embedding <=> CAST(:emb AS vector)) as similarity
                            FROM jobs
                            WHERE id != :job_id
                              AND id < :job_id
                              AND embedding IS NOT NULL
                              AND is_duplicate = false
                              AND (embedding <=> CAST(:emb AS vector)) < :max_distance
                            ORDER BY embedding <=> CAST(:emb AS vector)
                            LIMIT 1
                        """),
                        {
                            "emb": embedding_str,
                            "job_id": job.id,
                            "max_distance": max_distance,
                        },
                    ).fetchone()

                    if similar:
                        job.is_duplicate = True
                        job.duplicate_of_id = similar[0]
                        duplicates_found += 1
                        logger.debug(
                            f"Job #{job.id} '{job.title}' is duplicate of "
                            f"#{similar[0]} (similarity: {similar[1]:.3f})"
                        )

                except Exception as e:
                    logger.warning(f"Duplicate check failed for job #{job.id}: {e}")
                    continue

        logger.info(f"Duplicate detection complete: {duplicates_found} duplicates found.")
        return duplicates_found
