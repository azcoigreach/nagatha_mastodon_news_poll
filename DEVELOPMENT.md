# Development Guide

## Local Development Setup

### Prerequisites

- Python 3.13+
- Docker & Docker Compose
- Git

### Initial Setup

1. **Clone and configure**
   ```bash
   git clone <repo-url>
   cd nagatha_mastodon_news_poll
   cp .env.example .env
   # Edit .env with your credentials
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Start dependencies**
   ```bash
   # Option 1: Use Nagatha Core's infrastructure
   cd /path/to/nagatha_core
   docker-compose up -d
   
   # Option 2: Start local RabbitMQ and Redis
   docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:3.13-management
   docker run -d -p 6379:6379 redis:7-alpine
   ```

4. **Update .env for local development**
   ```env
   BROKER_URL=amqp://guest:guest@localhost:5672//
   RESULT_BACKEND=redis://localhost:6379/0
   PROVIDER_BASE_URL=http://localhost:9000
   ```

### Running Services Locally

**Terminal 1 - FastAPI App:**
```bash
source venv/bin/activate
python -m uvicorn app:app --reload --port 9000
```

**Terminal 2 - Celery Worker:**
```bash
source venv/bin/activate
celery -A tasks.app worker --loglevel=info --queues=mastodon_polls
```

**Terminal 3 - Registration (optional):**
```bash
source venv/bin/activate
python register.py
```

### Testing API Locally

```bash
# Health check
curl http://localhost:9000/health

# Run cycle
curl -X POST http://localhost:9000/run-cycle

# List polls
curl http://localhost:9000/polls
```

## Code Structure

### Core Components

```
app.py              # FastAPI routes and endpoints
├── Provider endpoints (health, manifest, tasks)
├── Poll management (CRUD operations)
├── Moderation endpoints
├── Settings management
└── Workflow triggers

tasks.py            # Celery task definitions
├── fetch_mastodon_posts
├── generate_poll_ideas
├── post_poll_to_mastodon
└── process_news_cycle

storage.py          # Redis data layer
├── PollStorage class
├── CRUD operations
├── Status management
└── Statistics

models.py           # Pydantic data models
├── PollStatus enum
├── PollData, PollRecord
├── AppSettings
└── Request/Response models

config.py           # Configuration management
└── Settings class (environment variables)

register.py         # Provider registration
├── Wait for services
├── Register with core
└── Heartbeat loop
```

## Adding New Features

### Adding a New Task

1. **Define task in tasks.py**
   ```python
   @app.task(name="mastodon_poll_provider.tasks.my_new_task")
   def my_new_task(param1: str, param2: int) -> Dict[str, Any]:
       """Task description."""
       try:
           # Task logic here
           return {
               "success": True,
               "result": "data"
           }
       except Exception as e:
           logger.error(f"Error: {e}")
           return {
               "success": False,
               "error": str(e)
           }
   ```

2. **Add to manifest in app.py**
   ```python
   {
       "name": "mastodon_poll.my_task",
       "description": "Task description",
       "version": "1.0.0",
       "celery_name": "mastodon_poll_provider.tasks.my_new_task",
       "queue": settings.queue_name,
       "timeout_s": 60,
       "retries": 1,
       "input_schema": {...},
       "output_schema": {...}
   }
   ```

3. **Add endpoint (optional)**
   ```python
   @app.post("/my-endpoint")
   async def my_endpoint(request: MyRequest) -> Dict[str, Any]:
       task = my_new_task.delay(...)
       return {"task_id": task.id}
   ```

### Adding a New Data Model

1. **Define in models.py**
   ```python
   class MyModel(BaseModel):
       field1: str
       field2: int
       created_at: datetime = Field(default_factory=datetime.utcnow)
   ```

2. **Add storage methods in storage.py**
   ```python
   def save_my_model(self, model: MyModel) -> bool:
       key = f"my_model:{model.id}"
       data = model.model_dump_json()
       self.redis_client.set(key, data)
       return True
   ```

3. **Add API endpoints in app.py**

### Adding New Settings

1. **Add to AppSettings in models.py**
   ```python
   class AppSettings(BaseModel):
       # ... existing settings ...
       new_setting: str = "default_value"
   ```

2. **Settings are automatically available via API**
   ```bash
   curl -X PUT http://localhost:9000/settings \
     -d '{"new_setting": "value"}'
   ```

## Testing

### Manual Testing

```bash
# Test Mastodon connection
python -c "
from mastodon import Mastodon
from config import settings
m = Mastodon(
    access_token=settings.mastodon_access_token,
    api_base_url=settings.mastodon_instance_url
)
print(m.instance())
"

# Test OpenAI connection
python -c "
import openai
from config import settings
openai.api_key = settings.openai_api_key
models = openai.models.list()
print('OK')
"

# Test Redis connection
python -c "
from storage import PollStorage
storage = PollStorage()
print(storage.redis_client.ping())
"
```

### Integration Testing

```bash
# Run full workflow
python example_workflow.py

# Or step by step
curl -X POST http://localhost:9000/run-cycle
# Wait for completion
curl http://localhost:9000/polls?status_filter=pending
```

### Unit Tests (TODO)

Create `tests/` directory:

```python
# tests/test_storage.py
import pytest
from storage import PollStorage
from models import PollRecord, PollData, PollOption, PollStatus

def test_save_and_get_poll():
    storage = PollStorage()
    poll = PollRecord(
        id="test_123",
        poll_data=PollData(
            question="Test?",
            options=[PollOption(text="Yes"), PollOption(text="No")]
        )
    )
    assert storage.save_poll(poll)
    retrieved = storage.get_poll("test_123")
    assert retrieved.id == poll.id
```

## Debugging

### Enable Debug Logging

```env
LOG_LEVEL=DEBUG
```

### Debug Worker Tasks

```bash
# List active tasks
celery -A tasks.app inspect active

# List scheduled tasks
celery -A tasks.app inspect scheduled

# List registered tasks
celery -A tasks.app inspect registered
```

### Debug Redis

```bash
# Connect to Redis
docker-compose exec redis redis-cli

# List all keys
KEYS *

# Get poll
GET mastodon_poll:poll_abc123

# Get settings
GET mastodon_poll:settings

# View all polls
SMEMBERS mastodon_poll:list
```

### Debug Logs

```bash
# View all logs
docker-compose logs -f

# Filter by service
docker-compose logs -f api
docker-compose logs -f worker

# Follow logs for specific container
docker logs -f mastodon_poll_worker
```

## Performance Optimization

### Scaling Workers

```bash
# Scale to 3 workers
docker-compose up -d --scale worker=3
```

### Redis Optimization

```python
# Use pipeline for bulk operations
pipe = storage.redis_client.pipeline()
for poll in polls:
    key = f"{storage.POLL_PREFIX}{poll.id}"
    pipe.set(key, poll.model_dump_json())
pipe.execute()
```

### Task Optimization

```python
# Use task routing
@app.task(
    name="...",
    queue="high_priority",  # Separate queue
    priority=9  # Higher priority
)
```

## Code Style

### Python Style Guide

- Follow PEP 8
- Use type hints
- Document functions with docstrings
- Use meaningful variable names

### Example:

```python
def fetch_mastodon_posts(
    hashtags: List[str] = None,
    limit: int = None
) -> Dict[str, Any]:
    """
    Fetch posts from Mastodon for specified hashtags.
    
    Args:
        hashtags: List of hashtags to search (default: from settings)
        limit: Maximum number of posts to fetch (default: from settings)
        
    Returns:
        Dictionary with posts and metadata
        
    Raises:
        ValueError: If credentials are invalid
    """
    # Implementation
    pass
```

## Git Workflow

```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes
git add .
git commit -m "feat: add new feature"

# Push
git push origin feature/my-feature

# Create pull request
```

### Commit Message Format

```
feat: add new feature
fix: fix bug in poll generation
docs: update API documentation
refactor: reorganize storage layer
test: add unit tests for tasks
```

## Deployment Checklist

- [ ] Update version in manifest
- [ ] Test all endpoints
- [ ] Run example workflow
- [ ] Check logs for errors
- [ ] Update documentation
- [ ] Tag release
- [ ] Deploy to production
- [ ] Monitor logs
- [ ] Verify health checks

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Celery Documentation](https://docs.celeryproject.org)
- [Pydantic Documentation](https://docs.pydantic.dev)
- [Mastodon.py Documentation](https://mastodonpy.readthedocs.io)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Redis Documentation](https://redis.io/docs)
