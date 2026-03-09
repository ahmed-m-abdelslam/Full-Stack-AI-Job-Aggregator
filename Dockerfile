FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements-core.txt .
RUN pip install --no-cache-dir -r requirements-core.txt

# Copy application
COPY . .

# Create logs directory
RUN mkdir -p logs

# Railway بيحدد الـ PORT تلقائي
ENV PORT=8050
EXPOSE 8050

CMD ["python", "main.py", "serve"]
