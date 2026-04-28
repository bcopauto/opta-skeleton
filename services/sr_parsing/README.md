# Scraper Service

A production-grade web scraping and SERP analysis microservice. Provides tiered HTTP fetching (httpx, XHR sniffing, Playwright fallback), structured SEO data extraction via 20 extractors, PageSpeed Insights integration, and multiple output sinks (JSON, CSV, MySQL, debug dumps). Mountable as a FastAPI router or usable as a standalone Python library.

## Docker Quick-Start

Prerequisites: [Docker](https://docs.docker.com/get-docker/) and Docker Compose (included with Docker Desktop).

```bash
# 1. Copy the example env file and fill in your API keys
cp .env.example .env

# 2. Build and start the scraper + MySQL
docker compose up --build

# 3. Verify the service is running
curl http://localhost:8000/health
```

The service is available at `http://localhost:8000` once both containers are healthy.

To stop the service:

```bash
# Stop containers (MySQL data persists in the mysql_data volume)
docker compose down

# Full reset -- stop containers and delete MySQL data
docker compose down -v
```

## Local Install

Prerequisites: Python 3.12+, a running MySQL server (or use the MySQL container from docker-compose).

```bash
# 1. Install the package
pip install -e ./scraper_service

# 2. Install the Chromium browser binary for Playwright
playwright install chromium

# 3. Copy .env.example to .env and configure your settings
cp .env.example .env

# 4. Start the server
uvicorn scraper_service.app:app --host 0.0.0.0 --port 8000
```

When running locally without Docker, update `SCRAPER_MYSQL_CONNECTION_STRING` in your `.env` to point at your MySQL host (e.g., `localhost` instead of `mysql`).

## API Reference

All endpoints are served at `http://localhost:8000` by default.

### POST /scrape

Synchronous scrape. Fetches the provided URLs, extracts structured data, writes to any configured sinks, and returns results inline.

```bash
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://example.com"]}'
```

### POST /scrape/async

Asynchronous scrape. Accepts the job immediately and processes it in the background. Returns a `job_id` for polling.

```bash
curl -X POST http://localhost:8000/scrape/async \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://example.com", "https://example.org"]}'
```

Response:

```json
{"job_id": "550e8400-e29b-41d4-a716-446655440000", "status": "pending"}
```

### GET /scrape/{job_id}

Check the status of an async scrape job. Returns the job state and results when complete.

```bash
curl http://localhost:8000/scrape/550e8400-e29b-41d4-a716-446655440000
```

### GET /health

Liveness check. Also probes whether Playwright can launch Chromium.

```bash
curl http://localhost:8000/health
```

Response:

```json
{"status": "healthy", "playwright": true}
```

### POST /serp

Run a SERP search via SerpAPI. Fetches Google results, extracts 19 SERP features (including AI Overview, Featured Snippet, PAA, Twitter/X cards, Discussions & Forums, FAQ rich results, Instant Answer, Calculator), computes a difficulty score (0-100), and returns cost metadata. Requires `SERPAPI_API_KEY` to be set.

```bash
curl -X POST http://localhost:8000/serp \
  -H "Content-Type: application/json" \
  -d '{"keyword": "best coffee machines", "market": "us", "language": "en"}'
```

Optional fields: `num` (results count, default 10), `target_url` (highlight a specific URL in results).

### GET /serp/{snapshot_id}

Retrieve a stored SERP snapshot by its ID (returned from POST /serp).

```bash
curl http://localhost:8000/serp/550e8400-e29b-41d4-a716-446655440000
```

### POST /pagespeed

Run Google PageSpeed Insights for one or more URLs. Returns Core Web Vitals (LCP, CLS, INP, FCP, TTFB) and a performance score (0-100). The Google PSI API is free for low volume; set `SCRAPER_PAGESPEED_API_KEY` for higher rate limits.

```bash
curl -X POST http://localhost:8000/pagespeed \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://example.com"], "strategy": "mobile"}'
```

`strategy` can be `"mobile"` (default) or `"desktop"`. Multiple URLs are fetched concurrently.

Response:

```json
[
  {
    "url": "https://example.com",
    "strategy": "mobile",
    "performance_score": 85.0,
    "lcp_ms": 1200.5,
    "cls": 0.1,
    "inp_ms": null,
    "fcp_ms": 800.0,
    "ttfb_ms": 350.5,
    "speed_index": 1500.0,
    "total_blocking_time": 150.0,
    "error": null,
    "raw_json": null
  }
]
```

### Output Sinks

You can configure output sinks in the scrape request body. Sinks run in parallel and one failure does not affect others.

```json
{
  "urls": ["https://example.com"],
  "sinks": [
    {"type": "json", "config": {"path": "/tmp/output.json"}},
    {"type": "csv", "config": {"path": "/tmp/output.csv"}},
    {"type": "database", "config": {}},
    {"type": "debug_dump", "config": {}}
  ]
}
```

Available sink types: `json`, `csv`, `database` (MySQL), `debug_dump` (raw HTML + screenshots to `SCRAPER_DEBUG_DUMP_DIR`).

## Programmatic API

Use the `Scraper` class as an async context manager for direct Python integration:

```python
from scraper_service import Scraper, SinkConfig, SinkType

async with Scraper() as scraper:
    results = await scraper.scrape(
        urls=["https://example.com", "https://example.org"],
        sinks=[SinkConfig(type=SinkType.JSON, config={"path": "output.json"})],
    )
    for page in results:
        print(f"{page.page_data.url}: {page.page_data.status_code}")
        if page.extraction_result:
            print(f"  Title: {page.extraction_result.title.title}")
```

Mount the service as a sub-router in an existing FastAPI application:

```python
from fastapi import FastAPI
from scraper_service import scraper_router

app = FastAPI()
app.include_router(scraper_router, prefix="/scraper")
```

All endpoints are then available under `/scraper/scrape`, `/scraper/health`, etc.

## SERP Search

The SERP pipeline takes a keyword, fetches Google results via SerpAPI, extracts SERP features, and scores keyword difficulty on a 0-100 scale.

### Usage

```bash
curl -X POST http://localhost:8000/serp \
  -H "Content-Type: application/json" \
  -d '{"keyword": "best coffee machines", "market": "us", "language": "en"}'
```

The response includes organic results, ads, featured snippets, People Also Ask items, knowledge panel data, and a difficulty score with a per-component breakdown.

### Difficulty Score Components

The difficulty score is the sum of 5 additive components, capped at 100:

- **AI Overview** (+30) -- Google AI Overview is present in the SERP.
- **Featured Snippet** (+10) -- A featured snippet occupies position zero.
- **Feature Saturation** (+2 per unique SERP feature, max +20) -- Counts ads, snippets, AI overview, knowledge panel, top stories, People Also Ask, Twitter/X cards, Discussions & Forums, Instant Answer, Calculator, FAQ rich results.
- **Brand Dominance** (+5 per brand in top 5 organic results, max +20) -- For branded keywords, +20 if the brand's domain appears in the top 3.
- **Major Site Competition** (+4 per authority domain in top 5, max +20) -- Counts high-authority domains and .gov/.edu/.ac.uk TLDs.

Higher scores mean harder keywords. A score of 80+ indicates the SERP is dominated by major players and Google features.

### Requirements

The SERP endpoint requires the `SERPAPI_API_KEY` environment variable. This key is read directly from `os.environ` (not via the `SCRAPER_` prefix used by other settings).

## Configuration Reference

All `SCRAPER_*` variables are loaded by pydantic-settings from the environment or a `.env` file. The `SCRAPER_` prefix is stripped automatically.

| Variable | Default | Description |
|----------|---------|-------------|
| `SERPAPI_API_KEY` | *(required for SERP endpoints)* | SerpAPI access key for Google search results. Not prefixed with SCRAPER_. |
| `SCRAPER_TIMEOUT` | `30` | HTTP request timeout in seconds |
| `SCRAPER_MAX_RETRIES` | `3` | Max retry attempts for failed requests |
| `SCRAPER_RETRY_BACKOFF` | `1.0` | Base backoff multiplier for retries (seconds) |
| `SCRAPER_MAX_PAGES_PER_JOB` | `100` | Max URLs per single scrape job |
| `SCRAPER_MAX_CONCURRENT_REQUESTS` | `10` | Concurrent request limit (semaphore) |
| `SCRAPER_PROXY_URL` | *(empty)* | HTTP/SOCKS proxy URL for requests |
| `SCRAPER_USE_PROXY` | `false` | Enable proxy fallback on 403/429/network errors |
| `SCRAPER_ROBOTS_TIMEOUT` | `10` | Timeout for robots.txt fetches (seconds) |
| `SCRAPER_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `SCRAPER_DEBUG_DUMP_DIR` | *(empty)* | Directory for debug dumps (HTML, screenshots, JSON) |
| `SCRAPER_MIN_BODY_CHARS` | `500` | Min body text chars before content is considered insufficient |
| `SCRAPER_HEADLESS` | `true` | Run Chromium in headless mode |
| `SCRAPER_MYSQL_CONNECTION_STRING` | *(empty)* | MySQL async connection string (`mysql+aiomysql://user:pass@host:3306/db`) |
| `SCRAPER_PAGESPEED_API_KEY` | *(empty)* | Google PageSpeed Insights API key (optional — free tier works without a key at low volume) |

## Architecture

The service is organized as a pipeline with several layers, each handling a distinct concern.

**API Layer.** A FastAPI router accepts scrape and SERP requests and manages async jobs via BackgroundTasks. Job state is held in memory (lost on restart). The router is mountable into any FastAPI app via `include_router`.

**Orchestration.** The `Scraper` class coordinates the full pipeline: URL validation and deduplication, tiered fetching, extraction, and sink output. It manages the httpx client, concurrency semaphore, and Playwright browser lifecycle as an async context manager.

**Tiered Fetching.** Three fetch tiers run in order, escalating only when the prior tier's content is insufficient (body text below `SCRAPER_MIN_BODY_CHARS`):

1. **httpx** -- Fast HTTP client for static HTML. Handles retries with exponential backoff and 429 Retry-After support.
2. **XHR sniffing** -- Parses embedded framework data from the httpx response (`__NEXT_DATA__`, `__NUXT__`, `apolloState`) and reconstructs HTML without launching a browser.
3. **Playwright** -- Full Chromium render for JS-heavy pages. Uses per-URL browser contexts, waits for `networkidle`, and captures XHR JSON responses.

**Extraction Pipeline.** 20 pure-function extractors run against fetched HTML: title, meta description, headings, body text, tables, lists, FAQ, videos, TOC, comparison tables, callout boxes, step-by-step guides, JSON-LD/structured data, images, links, technical signals, pagination, meta tags, content freshness (date signals from JSON-LD, OG meta, `<time>` elements, URL patterns, HTTP headers), and E-E-A-T signals (author byline, reviewed-by attributions, author bio, contact/about links, citations, expertise credentials). Each extractor never raises -- failures are recorded in the `errors` dict without affecting other extractors.

**Output Sinks.** Four sink types (JSON, CSV, MySQL, debug dump) implement a common `BaseSink` interface. Sinks run in parallel via `asyncio.gather`; one sink's failure does not block the others. The MySQL sink uses SQLAlchemy 2.0 async with aiomysql and supports upsert-on-URL.

**SERP Pipeline.** A separate pipeline handles keyword research: the SerpAPI client fetches Google results, an extractor pulls 19 feature flags (ads, featured snippets, AI overview, knowledge panel, PAA, Twitter/X cards, Discussions & Forums, FAQ rich results, Instant Answer, Calculator, and more), and a scorer computes difficulty from 0 to 100 using 5 weighted components. Each SERP call returns cost metadata (API credits used, timing) for usage tracking.

**PageSpeed Insights.** An async client for Google's PageSpeed Insights API v5. Fetches Core Web Vitals (LCP, CLS, INP, FCP, TTFB) and performance scores for any URL. Multiple URLs are fetched concurrently. Never raises -- errors are captured in the result.

**Resilience.** The fetcher includes a domain-level circuit breaker (trips after 5 consecutive failures for a domain, resets on success), robots.txt checking with per-domain caching, 429 Retry-After header support (capped at 60s), and proxy fallback on 403/429/network errors when `SCRAPER_USE_PROXY` is enabled.
