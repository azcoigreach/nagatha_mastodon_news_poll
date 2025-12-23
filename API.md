# API Reference

## Base URL

- Local Development: `http://localhost:9000`
- Production: `https://your-domain.com`

## Provider Endpoints

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "provider_id": "mastodon_poll_provider",
  "timestamp": "2025-12-23T10:30:00.000000"
}
```

### GET /.well-known/nagatha/manifest

Provider manifest for Nagatha Core registration.

**Response:**
```json
{
  "manifest_version": 1,
  "provider_id": "mastodon_poll_provider",
  "base_url": "http://mastodon_poll_provider:9000",
  "version": "1.0.0",
  "tasks": [...]
}
```

### GET /tasks

List available tasks.

**Response:**
```json
{
  "tasks": [
    "mastodon_poll.fetch_posts",
    "mastodon_poll.generate_polls",
    "mastodon_poll.post_poll",
    "mastodon_poll.process_cycle"
  ],
  "queue": "mastodon_polls"
}
```

## Poll Management

### GET /polls

List polls with optional filtering and pagination.

**Query Parameters:**
- `status_filter` (optional): Filter by status - `pending`, `approved`, `rejected`, `posted`
- `limit` (optional, default: 50): Maximum polls to return
- `offset` (optional, default: 0): Number of polls to skip

**Example:**
```bash
curl "http://localhost:9000/polls?status_filter=pending&limit=10"
```

**Response:**
```json
{
  "success": true,
  "polls": [
    {
      "id": "poll_abc123",
      "poll_data": {
        "question": "Should we increase funding for renewable energy?",
        "options": [
          {"text": "Yes", "votes": 0},
          {"text": "No", "votes": 0},
          {"text": "Maybe", "votes": 0}
        ],
        "duration_hours": 24
      },
      "status": "pending",
      "source_posts": ["12345", "67890"],
      "created_at": "2025-12-23T10:00:00",
      "updated_at": "2025-12-23T10:00:00"
    }
  ],
  "count": 1,
  "filter": "pending",
  "limit": 10,
  "offset": 0
}
```

### GET /polls/{poll_id}

Get details of a specific poll.

**Example:**
```bash
curl http://localhost:9000/polls/poll_abc123
```

**Response:**
```json
{
  "success": true,
  "poll": {
    "id": "poll_abc123",
    "poll_data": {...},
    "status": "pending",
    "created_at": "2025-12-23T10:00:00",
    ...
  }
}
```

**Error Responses:**
- `404 Not Found`: Poll does not exist

### PUT /polls/{poll_id}

Update a poll's question, options, or duration. Only works for pending polls.

**Request Body:**
```json
{
  "question": "Updated question text?",
  "options": ["Option A", "Option B", "Option C"],
  "duration_hours": 48
}
```

**Example:**
```bash
curl -X PUT http://localhost:9000/polls/poll_abc123 \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Updated question?",
    "options": ["Yes", "No", "Unsure"]
  }'
```

**Response:**
```json
{
  "success": true,
  "poll": {...},
  "message": "Poll updated successfully"
}
```

**Error Responses:**
- `404 Not Found`: Poll does not exist
- `400 Bad Request`: Poll is not pending or invalid data

### POST /polls/{poll_id}/moderate

Approve or reject a poll.

**Request Body:**
```json
{
  "approved": true,
  "edited_question": "Optional: override question",
  "edited_options": ["Optional", "Override", "Options"],
  "moderator_notes": "Optional notes"
}
```

**Example (Approve):**
```bash
curl -X POST http://localhost:9000/polls/poll_abc123/moderate \
  -H "Content-Type: application/json" \
  -d '{
    "approved": true,
    "moderator_notes": "Looks good!"
  }'
```

**Example (Reject):**
```bash
curl -X POST http://localhost:9000/polls/poll_abc123/moderate \
  -H "Content-Type: application/json" \
  -d '{
    "approved": false,
    "moderator_notes": "Not relevant to current events"
  }'
```

**Response:**
```json
{
  "success": true,
  "poll": {...},
  "message": "Poll approved successfully"
}
```

**Error Responses:**
- `404 Not Found`: Poll does not exist
- `400 Bad Request`: Invalid options (must be 2-4)

### DELETE /polls/{poll_id}

Delete a poll. Cannot delete posted polls.

**Example:**
```bash
curl -X DELETE http://localhost:9000/polls/poll_abc123
```

**Response:**
```json
{
  "success": true,
  "message": "Poll poll_abc123 deleted successfully"
}
```

**Error Responses:**
- `404 Not Found`: Poll does not exist
- `400 Bad Request`: Cannot delete posted polls

## Workflow Endpoints

### POST /run-cycle

Trigger a news cycle: fetch posts and generate poll ideas.

**Request Body:**
```json
{
  "hashtags": ["#uspol", "#news"],
  "post_limit": 100
}
```

**Example:**
```bash
curl -X POST http://localhost:9000/run-cycle \
  -H "Content-Type: application/json" \
  -d '{
    "hashtags": ["#uspol"],
    "post_limit": 50
  }'
```

**Response:**
```json
{
  "success": true,
  "task_id": "abc-def-123",
  "message": "News cycle task queued",
  "status": "pending"
}
```

### POST /post-poll

Queue an approved poll for posting to Mastodon.

**Request Body:**
```json
{
  "poll_id": "poll_abc123"
}
```

**Example:**
```bash
curl -X POST http://localhost:9000/post-poll \
  -H "Content-Type: application/json" \
  -d '{"poll_id": "poll_abc123"}'
```

**Response:**
```json
{
  "success": true,
  "task_id": "xyz-789",
  "poll_id": "poll_abc123",
  "message": "Post poll task queued",
  "status": "pending"
}
```

**Error Responses:**
- `404 Not Found`: Poll does not exist
- `400 Bad Request`: Poll is not approved

## Settings

### GET /settings

Get current application settings.

**Example:**
```bash
curl http://localhost:9000/settings
```

**Response:**
```json
{
  "success": true,
  "settings": {
    "hashtags": ["#uspol"],
    "post_limit": 100,
    "llm_model": "gpt-4o-mini",
    "llm_temperature": 0.7,
    "llm_max_tokens": 1500,
    "poll_prompt_template": "..."
  }
}
```

### PUT /settings

Update application settings.

**Request Body:**
```json
{
  "hashtags": ["#uspol", "#politics", "#news"],
  "post_limit": 150,
  "llm_model": "gpt-4o-mini",
  "llm_temperature": 0.8,
  "llm_max_tokens": 2000,
  "poll_prompt_template": "Custom prompt..."
}
```

**Example:**
```bash
curl -X PUT http://localhost:9000/settings \
  -H "Content-Type: application/json" \
  -d '{
    "hashtags": ["#uspol", "#news"],
    "post_limit": 120
  }'
```

**Response:**
```json
{
  "success": true,
  "settings": {...},
  "message": "Settings updated successfully"
}
```

## Statistics

### GET /stats

Get statistics about polls.

**Example:**
```bash
curl http://localhost:9000/stats
```

**Response:**
```json
{
  "success": true,
  "statistics": {
    "total_polls": 42,
    "by_status": {
      "pending": 5,
      "approved": 10,
      "rejected": 7,
      "posted": 15,
      "failed": 5
    }
  },
  "timestamp": "2025-12-23T10:30:00"
}
```

## Task Execution via Nagatha Core

All tasks can be executed through Nagatha Core's API:

### Fetch Mastodon Posts

```bash
curl -X POST http://localhost:8000/api/v1/tasks/run \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "mastodon_poll.fetch_posts",
    "kwargs": {
      "hashtags": ["#uspol"],
      "limit": 100
    }
  }'
```

### Generate Poll Ideas

```bash
curl -X POST http://localhost:8000/api/v1/tasks/run \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "mastodon_poll.generate_polls",
    "kwargs": {
      "posts": [...],
      "settings_override": {
        "llm_temperature": 0.9
      }
    }
  }'
```

### Post Poll

```bash
curl -X POST http://localhost:8000/api/v1/tasks/run \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "mastodon_poll.post_poll",
    "kwargs": {
      "poll_id": "poll_abc123"
    }
  }'
```

### Process Complete Cycle

```bash
curl -X POST http://localhost:8000/api/v1/tasks/run \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "mastodon_poll.process_cycle",
    "kwargs": {
      "hashtags": ["#uspol"],
      "post_limit": 100
    }
  }'
```

### Check Task Status

```bash
curl http://localhost:8000/api/v1/tasks/{task_id}
```

## Data Models

### PollStatus Enum

- `pending`: Poll created, awaiting moderation
- `approved`: Poll approved by moderator
- `rejected`: Poll rejected by moderator
- `posted`: Poll successfully posted to Mastodon
- `failed`: Posting to Mastodon failed

### Poll Record

```json
{
  "id": "poll_abc123",
  "poll_data": {
    "question": "string (max 100 chars)",
    "options": [
      {"text": "string (max 50 chars)", "votes": 0}
    ],
    "duration_hours": 24
  },
  "status": "pending",
  "source_posts": ["post_id_1", "post_id_2"],
  "created_at": "2025-12-23T10:00:00",
  "updated_at": "2025-12-23T10:00:00",
  "moderated_at": "2025-12-23T11:00:00",
  "moderator_notes": "Optional notes",
  "mastodon_poll_id": "mastodon_id",
  "mastodon_post_url": "https://..."
}
```

## Error Handling

All endpoints return consistent error responses:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes:**
- `200 OK`: Success
- `400 Bad Request`: Invalid input
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

## Rate Limiting

Currently no rate limiting is implemented. For production:
- Add rate limiting middleware
- Configure per-endpoint limits
- Implement token bucket or sliding window
