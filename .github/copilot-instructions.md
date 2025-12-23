# Copilot Instructions for Nagatha Mastodon Poll Provider

## Architecture Overview

This is a **Nagatha Core provider** application—not standalone. It depends on nagatha_core's RabbitMQ, Redis, and API infrastructure.

**Data flow**: FastAPI endpoints → Celery tasks (via RabbitMQ) → Redis storage → External APIs (Mastodon, OpenAI)

**Key insight**: All heavy lifting happens in async Celery tasks (`tasks.py`), not in HTTP request handlers. Endpoints mostly queue tasks or read from Redis. This design supports nagatha_core's distributed orchestration model.

## Critical Developer Workflows

### Local Development (3-Terminal Setup)
1. **Prerequisites**: Python 3.13+, Docker, nagatha_core running (`cd ../nagatha_core && docker-compose up -d`)
2. **Terminal 1 - FastAPI App**: `python -m uvicorn app:app --reload --port 9000`
3. **Terminal 2 - Celery Worker**: `celery -A tasks.app worker --loglevel=info --queues=mastodon_polls`
4. **Terminal 3 - Optional Registration**: `python register.py`

### Configuration Pattern
- All settings in `.env` (never commit) → loaded by [config.py](config.py) as `Settings` object
- **Runtime settings** (hashtags, LLM params) stored in Redis via [storage.py](storage.py) → editable via `PUT /settings` API
- This dual approach allows both deployment config + user-configurable behavior

### Testing API
```bash
# Full workflow
curl -X POST http://localhost:9000/run-cycle -H "Content-Type: application/json" -d '{"hashtags": ["#test"]}'
# Polling for results
curl http://localhost:9000/polls?status_filter=pending
# Moderate
curl -X POST http://localhost:9000/polls/{poll_id}/moderate -d '{"approved": true}' -H "Content-Type: application/json"
```

## Project-Specific Patterns

### Poll Status Machine
Polls follow a strict workflow: `PENDING` → `APPROVED` or `REJECTED` → (if approved) `POSTED` or `FAILED`

Key constraints:
- Only `PENDING` polls can be edited or deleted
- `POST /post-poll` requires `APPROVED` status
- `POSTED` polls cannot be deleted (audit trail)

### Task Design Pattern
Every task in [tasks.py](tasks.py) returns `{"success": bool, "data": {...}}` structure. This is **not** FastAPI's built-in response validation—it's a **manual pattern** for consistency with nagatha_core expectations. Always follow this.

### Pydantic Models as Source of Truth
- [models.py](models.py) defines all data contracts (`PollRecord`, `AppSettings`, etc.)
- Storage layer serializes/deserializes to JSON strings
- FastAPI uses `.model_dump()` to return models as JSON
- When adding fields: update model → storage methods → API schemas simultaneously

## Integration Points & External Dependencies

### Mastodon API (`mastodon.py` library)
- Authenticated via token in config; requires instance URL
- `Mastodon.timeline_hashtag()` fetches posts; `status_post()` creates polls
- Polls require JSON structure: `poll={'options': [...], 'expires_in': seconds}`
- **Error handling**: Token expiry or network failures caught in task try-except blocks, stored as `FAILED` status

### OpenAI API
- Configured globally: `openai.api_key = settings.openai_api_key`
- Used in [generate_poll_ideas()](tasks.py) with `response_format={"type": "json_object"}` for structured output
- **Important**: Prompt template in `AppSettings.poll_prompt_template` must explicitly ask for JSON array format
- Model and temperature configurable via settings

### Redis (`redis.Redis`)
- Initialized from connection string in [config.py](config.py) (parses `redis://host:port/db`)
- No persistence required; polls stored as JSON strings with prefixes like `mastodon_poll:poll_{id}`
- Status sets (`mastodon_poll:status:pending`) enable fast filtering
- **Convention**: All operations in [storage.py](storage.py); don't access Redis directly elsewhere

## Common Tasks & What Changes Are Needed

**Adding a new task**:
1. Define function in [tasks.py](tasks.py) with `@app.task(name="...")` decorator
2. Add schema to manifest in [app.py](app.py) (includes input/output schemas for nagatha_core)
3. Add endpoint in [app.py](app.py) or wire via `process_news_cycle` (main orchestrator task)

**Adding a configurable setting**: Add field to `AppSettings` in [models.py](models.py); automatically accessible via `PUT /settings` endpoint.

**Adding a data field to polls**: Update `PollRecord` or `PollData` in [models.py](models.py); storage layer handles serialization automatically.

## Known Constraints & Gotchas

- **Mastodon limits**: Question max 100 chars, each option max 50 chars, 2-4 options per poll
- **Task isolation**: Workers can't access app instance state; pass all data as task parameters
- **LLM token limits**: Posts limited to 50 before sending to OpenAI (see `fetch_mastodon_posts` in tasks.py)
- **Concurrent moderation**: No locking on poll updates; last-write-wins (acceptable for single moderator but flag if needed)

## Reference Files by Responsibility

| Responsibility | File |
|---|---|
| HTTP routes & moderation UI | [app.py](app.py) |
| Async workflows & LLM/Mastodon integration | [tasks.py](tasks.py) |
| Redis CRUD & statistics | [storage.py](storage.py) |
| Data validation & serialization | [models.py](models.py) |
| Environment & deployment config | [config.py](config.py) |
| Nagatha registration heartbeat | [register.py](register.py) |

