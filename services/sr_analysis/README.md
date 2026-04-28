# Analysis Service

SEO analysis microservice that scores a target page against its actual SERP competitors. Accepts pre-scraped ExtractionResult data and returns scores across 9 analysis modules (5 deterministic + 4 Gemini-powered).

## Quick Start

### Docker Compose (recommended)

```bash
# 1. Copy and configure environment variables
cp .env.example .env
# Edit .env — set ANALYSIS_GEMINI_API_KEY to your Google Gemini API key

# 2. Start all services
docker compose up -d

# 3. Verify health
curl http://localhost:6969/health
# {"status":"ok","gemini":"reachable"}
```

### Local Development

```bash
cd analysis_service
pip install -e .
ANALYSIS_GEMINI_API_KEY=your-key ANALYSIS_GEMINI_MODEL=gemini-2.5-flash ANALYSIS_PORT=6969 \
  uvicorn analysis_service.app:app --host 0.0.0.0 --port 6969
```

## API Reference

### POST /analyze

Synchronous analysis — blocks until all 9 modules complete.

**Request:**
```bash
curl -X POST http://localhost:6969/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "target": { "body_text": { "word_count": 1500, "text": "..." }, "headings": { "h1_texts": ["Best Betting Sites"] } },
    "competitors": [],
    "keyword": "best betting sites",
    "market": "UK",
    "page_type": "comparator"
  }'
```

**Response:** `200 OK` with full `AnalysisResult` (all 9 module fields populated).

### POST /analyze/async

Asynchronous analysis — returns immediately with a job ID.

**Request:** Same body as POST /analyze.

```bash
curl -X POST http://localhost:6969/analyze/async \
  -H "Content-Type: application/json" \
  -d '{
    "target": {},
    "competitors": [],
    "keyword": "best betting sites",
    "market": "UK",
    "page_type": "comparator"
  }'
```

**Response:** `202 Accepted`
```json
{"job_id": "550e8400-e29b-41d4-a716-446655440000"}
```

### GET /analyze/{job_id}

Poll for job status and partial results. Completed modules are populated; pending modules are null.

```bash
curl http://localhost:6969/analyze/550e8400-e29b-41d4-a716-446655440000
```

**Response:** `200 OK`
```json
{
  "job_id": "550e8400-...",
  "status": "running",
  "completed_modules": ["html_element_gap", "serp_feature_opportunity", "h1_meta_optimization", "schema_markup"],
  "result": {
    "html_element_gap": { "score": 72.0 },
    "h1_meta_optimization": { "score": 85.0 },
    "serp_feature_opportunity": { "score": 60.0 },
    "schema_markup": { "score": 33.0 },
    "information_gap": null,
    "content_best_practices": null,
    "schema_json_ld": null,
    "llm_optimization": null,
    "overall_score": null,
    "priority_modules": ["schema_markup", "serp_feature_opportunity", "html_element_gap", "h1_meta_optimization"]
  },
  "error": null
}
```

**Status values:** `pending` | `running` | `completed` | `failed`

Returns `404` if job_id is not found. Returns `429` on POST /analyze/async if max concurrent jobs reached.

### GET /health

```bash
curl http://localhost:6969/health
```

**Response:** `200 OK`
```json
{"status": "ok", "gemini": "reachable"}
```

Returns `{"status": "degraded", "gemini": "unreachable"}` if Gemini API is down.

## Environment Variables

All variables use the `ANALYSIS_` prefix and are loaded via pydantic-settings.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANALYSIS_GEMINI_API_KEY` | Yes | — | Google Gemini API key |
| `ANALYSIS_GEMINI_MODEL` | Yes | — | Gemini model name (e.g. `gemini-2.5-flash`) |
| `ANALYSIS_PORT` | Yes | — | Port the service listens on |
| `ANALYSIS_MAX_CONCURRENT_GEMINI_CALLS` | No | `3` | Max parallel Gemini API calls per analysis |
| `ANALYSIS_TOKEN_CEILING_PER_MODULE` | No | `100000` | Max tokens per Gemini module call (aborts if exceeded) |
| `ANALYSIS_LOG_LEVEL` | No | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `ANALYSIS_MAX_CONCURRENT_JOBS` | No | `10` | Max async jobs running simultaneously (429 when exceeded) |
| `ANALYSIS_JOB_TTL_MINUTES` | No | `60` | Minutes before completed/failed jobs are evicted from memory |

## Configuration: bc_best_practices.yaml

The service loads `bc_best_practices.yaml` at startup for Content Best Practices L2 scoring. The file is mounted as a read-only Docker volume:

```yaml
# docker-compose.yml
volumes:
  - ./config:/app/config:ro
```

The file lives at `config/bc_best_practices.yaml` in the project root. Edit it to update compliance rules without rebuilding the Docker image. The service validates the YAML schema at startup and fails fast if the file is missing or invalid.

## Analysis Modules

| # | Module | Type | Score Range | In Overall Score |
|---|--------|------|-------------|-----------------|
| 1 | HTML Element Gap | Deterministic | 0-100 | Yes (15%) |
| 2 | SERP Feature Opportunity | Deterministic | 0-100 | Yes (20%) |
| 3 | H1 + Meta Optimization | Deterministic | 0-100 | Yes (20%) |
| 4 | Schema/Markup | Deterministic | 0-100 | Yes (15%) |
| 5 | Content Best Practices L2 | Deterministic | 0-100 | No |
| 6 | Information Gap | Gemini | 0-100 | Yes (30%) |
| 7 | Content Best Practices L1 | Gemini | 0-100 | No |
| 8 | Schema JSON-LD Generation | Gemini | — | No |
| 9 | LLM Optimization | Gemini | 0-100 | No |

**Overall Score** = weighted composite of the 5 modules marked "Yes". Null until all 5 are available.

## Architecture

```
docker-compose
├── scraper_service  (port 8000) — data collection
├── analysis_service (port 6969) — scoring + Gemini
└── mysql            (port 3307) — shared database
```

The analysis service is stateless — all job state is in-memory. Jobs are evicted after the TTL expires. The service accepts pre-scraped `ExtractionResult` objects and never fetches pages itself.
