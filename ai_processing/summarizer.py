"""Uses OpenAI LLM to summarize job descriptions."""

from typing import Optional
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from utils.logger import logger


client = OpenAI(api_key=settings.openai_api_key)

SYSTEM_PROMPT = """You are a job description summarizer. Given a job description, produce a concise
2-4 sentence summary capturing:
- The main role and responsibilities
- Key requirements or qualifications
- Notable benefits or unique aspects

Be factual and concise. Do not add information not present in the original text."""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
def summarize_job(description: str) -> Optional[str]:
    """Summarize a job description using the configured LLM."""
    if not description or len(description.strip()) < 50:
        return None

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Summarize this job description:\n\n{description[:4000]}"},
            ],
            max_tokens=250,
            temperature=0.3,
        )
        summary = response.choices[0].message.content.strip()
        return summary
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        raise
