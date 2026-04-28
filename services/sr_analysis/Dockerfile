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

# Copy Python packages from build stage
COPY --from=build /install /usr/local

# Install curl for Docker health check
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for container security
RUN useradd -m -u 1000 analysis

USER analysis
WORKDIR /app

# Copy source into analysis_service/ so 'analysis_service.app:app' is importable from /app
COPY --chown=analysis:analysis . ./analysis_service/

EXPOSE 6969

CMD ["uvicorn", "analysis_service.app:app", "--host", "0.0.0.0", "--port", "6969"]
