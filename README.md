# Orchestrator (Django + Microservices)

## Overview

This project is a **containerized orchestration system** built around a central Django application that coordinates multiple services.

Architecture:

- **Django** → orchestrator (entry point for users)
- **Python services** → data processing / logic
- **Go services** → high-performance workers
- **PostgreSQL** → primary database
- **Redis** → cache / future task queue

---

## Current Services

| Service        | Type   | Port | Description                |
|----------------|--------|------|----------------------------|
| django         | Python | 8000 | Main orchestrator          |
| sr_parsing     | Python | 8001 | Parsing service (FastAPI)  |
| sr_psi_go      | Go     | 8003 | PSI service (Go HTTP API)  |
| postgres       | DB     | 5432 | PostgreSQL database        |
| redis          | Cache  | —    | Internal Redis instance    |

---

## Architecture

User → Django → Services → (Future: LLM Agents)
↓
PostgreSQL
↓
Redis

- Django is the **only public entry point**
- Services communicate over **internal Docker network**
- Each service is independently deployable

---

## Project Structure

├── django_app/
├── services/
│ ├── sr_parsing/
│ ├── sr_psi_go/
│ ├── sr_agents/
│ ├── sr_gsc/
│ ├── sr_ahrefs_monolith/
│ └── sr_serp_monolith/
├── docker-compose.yml
├── .env.example
├── infra/
└── docs/

## Requirements

- Docker
- Docker Compose
- (optional) Python 3.12 + pyenv for local development

---

## Environment Setup

Create local environment file:

```bash
cp .env.example .env


DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

POSTGRES_DB=orchestrator_db
POSTGRES_USER=orchestrator_user
POSTGRES_PASSWORD=orchestrator_pass
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

REDIS_URL=redis://redis:6379/0

SR_PARSING_URL=http://sr_parsing:8001
SR_PSI_GO_URL=http://sr_psi_go:8003

Running the Project

docker compose up --build

## Health Checks
curl http://127.0.0.1:8000/health/

## Python Service 
curl http://127.0.0.1:8001/health

## Go Service
curl http://127.0.0.1:8003/health


## NOTES
Each service has its own environment and dependencies
Python services use Python 3.12
Go services follow idiomatic Go structure (cmd/, internal/)
Services are designed to run:
independently (for development)
internally (in production)

## Future Work
Service orchestration from Django
LLM agent integration
Async processing (Celery / Redis)
Service authentication layer
CI/CD pipelines
Production deployment (Nginx, Supervisor, ASGI)


## Key Principles
Modular architecture
Service isolation
Container-first development
Internal-only service communication
Clear separation between orchestration and execution
