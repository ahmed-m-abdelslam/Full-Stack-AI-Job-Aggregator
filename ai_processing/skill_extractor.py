"""Uses OpenAI LLM to extract technical skills from job descriptions."""

import json
from typing import Optional
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from utils.logger import logger


client = OpenAI(api_key=settings.openai_api_key)

SYSTEM_PROMPT = """You are a technical skill extractor for AI/ML/Data Science job postings.
Given a job description, extract all required and preferred technical skills.

Focus on skills like:
- Programming languages (Python, R, SQL, Java, Scala, C++, etc.)
- ML/AI frameworks (TensorFlow, PyTorch, scikit-learn, Keras, Hugging Face, etc.)
- Domains (Machine Learning, Deep Learning, NLP, Computer Vision, LLMs, Reinforcement Learning, etc.)
- Data tools (Spark, Hadoop, Pandas, Airflow, dbt, etc.)
- Cloud platforms (AWS, GCP, Azure, etc.)
- Databases (PostgreSQL, MongoDB, Redis, Elasticsearch, etc.)
- MLOps tools (MLflow, Kubeflow, Docker, Kubernetes, etc.)
- Other relevant technical skills

Return a JSON array of skill strings. Only return the JSON array, no other text.
Example: ["Python", "PyTorch", "NLP", "Transformers", "AWS", "Docker"]"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
def extract_skills(description: str) -> Optional[list[str]]:
    """Extract skills from a job description using the configured LLM."""
    if not description or len(description.strip()) < 30:
        return None

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Extract skills from:\n\n{description[:4000]}"},
            ],
            max_tokens=300,
            temperature=0.1,
        )
        raw_output = response.choices[0].message.content.strip()

        # Parse JSON array from response
        # Handle cases where the model wraps the output in markdown code blocks
        if raw_output.startswith("```"):
            raw_output = raw_output.split("```")[1]
            if raw_output.startswith("json"):
                raw_output = raw_output[4:]
            raw_output = raw_output.strip()

        skills = json.loads(raw_output)
        if isinstance(skills, list):
            return [s.strip() for s in skills if isinstance(s, str) and s.strip()]
        return None

    except json.JSONDecodeError:
        logger.warning(f"Failed to parse skills JSON: {raw_output[:200]}")
        return None
    except Exception as e:
        logger.error(f"Skill extraction failed: {e}")
        raise
