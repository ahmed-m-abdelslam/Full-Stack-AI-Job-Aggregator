FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install requirements first (cached layer)
COPY requirements-core.txt .
RUN pip install --no-cache-dir -r requirements-core.txt

# Clean up pip cache and unnecessary files
RUN rm -rf /root/.cache /tmp/*

COPY . .
RUN mkdir -p logs

# Remove unnecessary files to reduce size
RUN rm -rf .git tests/ __pycache__/ *.md .env.example

EXPOSE 8050
CMD ["python", "main.py", "serve", "--host", "0.0.0.0", "--port", "8050"]
