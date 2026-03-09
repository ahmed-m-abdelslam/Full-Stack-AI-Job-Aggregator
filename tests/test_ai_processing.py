"""Unit tests for AI processing components."""

import pytest # type: ignore
from unittest.mock import patch, MagicMock


class TestSummarizer:
    @patch("ai_processing.summarizer.client")
    def test_summarize_job_returns_summary(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "This is a summary of the job."
        mock_client.chat.completions.create.return_value = mock_response

        from ai_processing.summarizer import summarize_job
        result = summarize_job("A long job description about machine learning engineering...")
        assert result == "This is a summary of the job."

    @patch("ai_processing.summarizer.client")
    def test_summarize_short_text_returns_none(self, mock_client):
        from ai_processing.summarizer import summarize_job
        result = summarize_job("Short")
        assert result is None
        mock_client.chat.completions.create.assert_not_called()


class TestSkillExtractor:
    @patch("ai_processing.skill_extractor.client")
    def test_extract_skills_parses_json(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '["Python", "TensorFlow", "NLP"]'
        mock_client.chat.completions.create.return_value = mock_response

        from ai_processing.skill_extractor import extract_skills
        result = extract_skills("Need Python, TensorFlow, NLP experience for this role...")
        assert result == ["Python", "TensorFlow", "NLP"]

    @patch("ai_processing.skill_extractor.client")
    def test_extract_skills_handles_markdown_wrapper(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '```json\n["Python", "PyTorch"]\n```'
        mock_client.chat.completions.create.return_value = mock_response

        from ai_processing.skill_extractor import extract_skills
        result = extract_skills("Python and PyTorch required for this deep learning position...")
        assert result == ["Python", "PyTorch"]


class TestJobClassifier:
    @patch("ai_processing.job_classifier.client")
    def test_classify_returns_known_category(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Machine Learning Engineer"
        mock_client.chat.completions.create.return_value = mock_response

        from ai_processing.job_classifier import classify_job
        result = classify_job("Senior ML Engineer", "Build and deploy ML models")
        assert result == "Machine Learning Engineer"

    @patch("ai_processing.job_classifier.client")
    def test_classify_defaults_to_other(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Something Unknown"
        mock_client.chat.completions.create.return_value = mock_response

        from ai_processing.job_classifier import classify_job
        result = classify_job("Generic Role")
        assert result == "Other"
