# --- Stage 1: Build Python dependencies ---
FROM python:3.12-slim-bookworm AS build

WORKDIR /build
COPY pyproject.toml README.md ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install .

# --- Stage 2: Runtime ---
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers

# Copy Python packages from build stage
COPY --from=build /install /usr/local

# Install Chromium and its system dependencies (libnss3, libatk, libgbm, fonts, etc.)
# --with-deps handles the apt-get calls for all required system libraries.
RUN playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for container security
RUN useradd -m -u 1000 scraper \
    && chmod -R o+rx ${PLAYWRIGHT_BROWSERS_PATH}

USER scraper
WORKDIR /app

# Copy source into scraper_service/ so 'scraper_service.router' is importable from /app
COPY --chown=scraper:scraper . ./scraper_service/

EXPOSE 8001

CMD ["uvicorn", "scraper_service.app:app", "--host", "0.0.0.0", "--port", "8001"]
