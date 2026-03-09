import numpy as np
from openai import OpenAI
from sqlalchemy import text, select
from database.models import Job
from database.connection import get_session
from config.settings import settings
from utils.logger import logger


class DuplicateDetector:
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.threshold = settings.duplicate_similarity_threshold
        logger.info(f"Using OpenAI embeddings. Similarity threshold: {self.threshold}")

    def _get_embedding(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings from OpenAI (cheap: text-embedding-3-small)"""
        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=texts
        )
        return [item.embedding for item in response.data]

    def _embedding_to_pgvector_str(self, embedding) -> str:
        if isinstance(embedding, np.ndarray):
            return "[" + ",".join(str(float(x)) for x in embedding) + "]"
        if isinstance(embedding, list):
            return "[" + ",".join(str(float(x)) for x in embedding) + "]"
        return str(embedding)

    def generate_embeddings(self, jobs: list[Job]) -> int:
        if not jobs:
            return 0

        texts = []
        for job in jobs:
            text_content = f"{job.title} {job.company} {job.description[:500] if job.description else ''}"
            texts.append(text_content)

        batch_size = 50
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = self._get_embedding(batch)
            all_embeddings.extend(embeddings)

        with get_session() as session:
            for job, embedding in zip(jobs, all_embeddings):
                emb_str = self._embedding_to_pgvector_str(embedding)
                session.execute(
                    text("UPDATE jobs SET embedding = CAST(:emb AS vector) WHERE id = :job_id"),
                    {"emb": emb_str, "job_id": job.id}
                )
            session.commit()

        logger.info(f"Generated embeddings for {len(jobs)} jobs.")
        return len(jobs)

    def detect_duplicates(self) -> int:
        duplicates_found = 0
        with get_session() as session:
            jobs = list(session.execute(
                select(Job)
                .where(Job.embedding.isnot(None))
                .where(Job.is_duplicate == False)
                .order_by(Job.created_at)
            ).scalars().all())

            if len(jobs) < 2:
                return 0

            logger.info(f"Checking {len(jobs)} jobs for duplicates...")
            max_distance = 1.0 - self.threshold

            for job in jobs:
                if job.is_duplicate:
                    continue
                embedding_str = self._embedding_to_pgvector_str(job.embedding)
                try:
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
                        {"emb": embedding_str, "job_id": job.id, "max_distance": max_distance}
                    ).fetchone()

                    if similar:
                        job.is_duplicate = True
                        job.duplicate_of_id = similar[0]
                        duplicates_found += 1
                except Exception as e:
                    logger.warning(f"Duplicate check failed for job #{job.id}: {e}")
                    continue

            session.commit()
        logger.info(f"Duplicate detection complete: {duplicates_found} duplicates found.")
        return duplicates_found
