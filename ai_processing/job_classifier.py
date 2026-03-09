"""Uses OpenAI LLM to classify jobs into predefined categories."""

from typing import Optional
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from utils.logger import logger


client = OpenAI(api_key=settings.openai_api_key)

CATEGORIES = [
    "AI Engineer",
    "Machine Learning Engineer",
    "Data Scientist",
    "NLP Engineer",
    "LLM Engineer",
    "Data Analyst",
    "Data Engineer",
    "MLOps Engineer",
    "Research Scientist",
    "Computer Vision Engineer",
    "Other",
]

SYSTEM_PROMPT = f"""You are a job classifier. Given a job title and description, classify the job
into exactly one of the following categories:

{chr(10).join(f'- {c}' for c in CATEGORIES)}

Consider both the title and description to make your classification.
Return only the category name, nothing else."""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
def classify_job(title: str, description: str = "") -> Optional[str]:
    """Classify a job into a predefined category."""
    if not title:
        return None

    try:
        user_content = f"Job Title: {title}\n"
        if description:
            user_content += f"\nJob Description:\n{description[:3000]}"

        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            max_tokens=20,
            temperature=0.1,
        )
        category = response.choices[0].message.content.strip()

        # Validate that the returned category is one of our known categories
        for known_cat in CATEGORIES:
            if known_cat.lower() == category.lower():
                return known_cat

        # Fuzzy match — if the model returned a close variant
        category_lower = category.lower()
        for known_cat in CATEGORIES:
            if known_cat.lower() in category_lower or category_lower in known_cat.lower():
                return known_cat

        logger.warning(f"Unknown category returned: '{category}', defaulting to 'Other'")
        return "Other"

    except Exception as e:
        logger.error(f"Classification failed for '{title}': {e}")
        raise
