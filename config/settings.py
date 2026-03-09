"""Centralized configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from datetime import datetime
import os


class Settings(BaseSettings):
    # Database — يقرأ DATABASE_URL من Railway أو Neon
    database_url: str = Field(
        default="postgresql://jobuser:jobpassword@localhost:5432/ai_jobs_db",
        alias="DATABASE_URL",
    )

    # OpenAI
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # Scraping
    scrape_interval_hours: int = Field(default=6, alias="SCRAPE_INTERVAL_HOURS")
    request_delay_seconds: float = Field(default=2.0, alias="REQUEST_DELAY_SECONDS")
    selenium_headless: bool = Field(default=True, alias="SELENIUM_HEADLESS")

    # فلتر البلد
    target_countries: str = Field(default="Egypt", alias="TARGET_COUNTRIES")

    # فلتر التاريخ
    scrape_days_back: int = Field(default=1, alias="SCRAPE_DAYS_BACK")
    scrape_date_from: Optional[str] = Field(default=None, alias="SCRAPE_DATE_FROM")
    scrape_date_to: Optional[str] = Field(default=None, alias="SCRAPE_DATE_TO")

    # الحد الأقصى
    max_jobs_per_source: int = Field(default=30, alias="MAX_JOBS_PER_SOURCE")

    # Embedding
    embedding_model: str = Field(default="all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")
    duplicate_similarity_threshold: float = Field(
        default=0.92, alias="DUPLICATE_SIMILARITY_THRESHOLD"
    )

    # Web App — Railway بيبعت PORT
    dash_host: str = Field(default="0.0.0.0", alias="DASH_HOST")
    dash_port: int = Field(default=8050, alias="DASH_PORT")
    dash_debug: bool = Field(default=False, alias="DASH_DEBUG")

    # Search keywords
    search_keywords: list[str] = Field(
        default=[
            "Artificial Intelligence",
            "Machine Learning",
            "Data Scientist",
            "NLP Engineer",
            "LLM Engineer",
            "AI Engineer",
            "Deep Learning",
        ]
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def get_target_countries_list(self) -> list[str]:
        return [c.strip() for c in self.target_countries.split(",") if c.strip()]

    def get_date_range(self) -> tuple[Optional[datetime], Optional[datetime]]:
        from datetime import timedelta, timezone

        if self.scrape_date_from and self.scrape_date_to:
            try:
                date_from = datetime.strptime(self.scrape_date_from, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                date_to = datetime.strptime(self.scrape_date_to, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=timezone.utc
                )
                return date_from, date_to
            except ValueError:
                pass

        date_to = datetime.now(timezone.utc)
        date_from = date_to - timedelta(days=self.scrape_days_back)
        return date_from, date_to

    def get_port(self) -> int:
        """Railway بيبعت PORT كـ env variable."""
        return int(os.environ.get("PORT", self.dash_port))


settings = Settings()
