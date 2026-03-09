# ============================================================
# Stage 1: Base — بدون Selenium (أسرع بكتير)
# ============================================================
FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-core.txt .
RUN pip install --no-cache-dir -r requirements-core.txt

COPY . .
RUN mkdir -p logs

EXPOSE 8050


# ============================================================
# Stage 2: Full — مع Selenium + Chromium (لو محتاج Glassdoor)
# ============================================================
FROM base AS full

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libasound2t64 \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

COPY requirements-selenium.txt .
RUN pip install --no-cache-dir -r requirements-selenium.txt

ENTRYPOINT ["python", "main.py"]
CMD ["serve"]


# ============================================================
# Stage 3: Light — بدون Selenium (الافتراضي)
# ============================================================
FROM base AS light

ENTRYPOINT ["python", "main.py"]
CMD ["serve"]
