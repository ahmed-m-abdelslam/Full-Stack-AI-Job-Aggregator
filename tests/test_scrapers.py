"""Unit tests for scraper components."""

import pytest # type: ignore
from unittest.mock import patch, MagicMock
from scrapers.base_scraper import BaseScraper, RawJob
from scrapers.remoteok_scraper import RemoteOKScraper
from utils.helpers import clean_text, generate_job_hash, parse_relative_date


class TestRawJob:
    def test_to_dict(self):
        job = RawJob(
            title="ML Engineer",
            company="Acme Corp",
            location="Remote",
            description="Build models",
            url="https://example.com/job/1",
            source="test",
        )
        d = job.to_dict()
        assert d["title"] == "ML Engineer"
        assert d["company"] == "Acme Corp"
        assert d["source"] == "test"
        assert "date_posted" in d

    def test_to_dict_nullable_fields(self):
        job = RawJob(title="AI Eng", company="Co", source="test")
        d = job.to_dict()
        assert d["location"] is None
        assert d["description"] is None


class TestHelpers:
    def test_clean_text_strips_html(self):
        assert "Hello World" in clean_text("<p>Hello <b>World</b></p>")

    def test_clean_text_empty(self):
        assert clean_text(None) == ""
        assert clean_text("") == ""

    def test_generate_job_hash_deterministic(self):
        h1 = generate_job_hash("ML Eng", "Acme", "https://example.com")
        h2 = generate_job_hash("ML Eng", "Acme", "https://example.com")
        assert h1 == h2

    def test_generate_job_hash_different(self):
        h1 = generate_job_hash("ML Eng", "Acme", "https://a.com")
        h2 = generate_job_hash("ML Eng", "Acme", "https://b.com")
        assert h1 != h2

    def test_parse_relative_date_days_ago(self):
        dt = parse_relative_date("3 days ago")
        assert dt is not None

    def test_parse_relative_date_today(self):
        dt = parse_relative_date("today")
        assert dt is not None

    def test_parse_relative_date_invalid(self):
        dt = parse_relative_date("banana")
        assert dt is None


class TestBaseScraper:
    def test_classify_job_type_remote(self):
        scraper = RemoteOKScraper()
        assert scraper.classify_job_type("Work from home position") == "Remote"
        assert scraper.classify_job_type("Remote / Anywhere") == "Remote"

    def test_classify_job_type_hybrid(self):
        scraper = RemoteOKScraper()
        assert scraper.classify_job_type("Hybrid work in NYC") == "Hybrid"

    def test_classify_job_type_onsite(self):
        scraper = RemoteOKScraper()
        assert scraper.classify_job_type("On-site in London") == "Onsite"

    def test_classify_job_type_unknown(self):
        scraper = RemoteOKScraper()
        assert scraper.classify_job_type("San Francisco, CA") is None


class TestRemoteOKScraper:
    @patch("scrapers.remoteok_scraper.RemoteOKScraper._get")
    def test_scrape_parses_api_response(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"legal": "info"},  # metadata element
            {
                "position": "ML Engineer",
                "company": "StartupCo",
                "location": "Remote",
                "description": "Build ML pipelines",
                "url": "/remote-jobs/ml-engineer-123",
                "date": "2024-12-01T10:00:00Z",
                "tags": ["python", "ml"],
            },
        ]
        mock_get.return_value = mock_response

        scraper = RemoteOKScraper()
        jobs = scraper.scrape("machine learning")

        assert len(jobs) == 1
        assert jobs[0].title == "ML Engineer"
        assert jobs[0].company == "StartupCo"
        assert jobs[0].job_type == "Remote"
        assert jobs[0].source == "remoteok"
