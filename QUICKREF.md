# Quick Reference

## 🚀 Quick Start

```bash
# 1. Setup
./setup.sh

# 2. Run a news cycle
curl -X POST http://localhost:9000/run-cycle

# 3. View pending polls
curl http://localhost:9000/polls?status_filter=pending

# 4. Approve a poll
curl -X POST http://localhost:9000/polls/{poll_id}/moderate \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'

# 5. Post to Mastodon
curl -X POST http://localhost:9000/post-poll \
  -H "Content-Type: application/json" \
  -d '{"poll_id": "{poll_id}"}'
```

## 📋 Common Commands

### Service Management

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Restart services
docker-compose restart

# View service status
docker-compose ps
```

### Poll Operations

```bash
# List all polls
curl http://localhost:9000/polls

# List pending polls
curl http://localhost:9000/polls?status_filter=pending

# Get specific poll
curl http://localhost:9000/polls/{poll_id}

# Edit poll
curl -X PUT http://localhost:9000/polls/{poll_id} \
  -H "Content-Type: application/json" \
  -d '{"question": "New question?", "options": ["A", "B", "C"]}'

# Delete poll
curl -X DELETE http://localhost:9000/polls/{poll_id}
```

### Settings

```bash
# View settings
curl http://localhost:9000/settings

# Update hashtags
curl -X PUT http://localhost:9000/settings \
  -H "Content-Type: application/json" \
  -d '{"hashtags": ["#uspol", "#news"]}'

# Update LLM settings
curl -X PUT http://localhost:9000/settings \
  -H "Content-Type: application/json" \
  -d '{"llm_model": "gpt-4o-mini", "llm_temperature": 0.8}'
```

### Monitoring

```bash
# Health check
curl http://localhost:9000/health

# Statistics
curl http://localhost:9000/stats

# View worker tasks
docker-compose exec worker celery -A tasks.app inspect active
```

## 🔧 Make Commands

```bash
make help      # Show available commands
make setup     # Initial setup
make up        # Start services
make down      # Stop services
make logs      # View logs
make restart   # Restart services
make clean     # Remove all data
make shell     # Open shell in container
make example   # Run example workflow
make stats     # View statistics
make health    # Check health
make pending   # List pending polls
```

## 📂 File Locations

| File | Purpose |
|------|---------|
| `.env` | Configuration & secrets |
| `app.py` | FastAPI application |
| `tasks.py` | Celery task definitions |
| `config.py` | Configuration loader |
| `models.py` | Data models |
| `storage.py` | Redis storage layer |
| `register.py` | Provider registration |

## 🔑 Environment Variables

### Required
```env
MASTODON_ACCESS_TOKEN=your_token
OPENAI_API_KEY=your_key
```

### Optional (configurable via API)
```env
MASTODON_HASHTAGS=#uspol
MASTODON_POST_LIMIT=100
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.7
```

## 🌐 Service URLs

- **Provider API**: http://localhost:9000
- **API Docs**: http://localhost:9000/docs
- **Nagatha Core**: http://localhost:8000
- **RabbitMQ UI**: http://localhost:15672 (guest/guest)

## 🐛 Troubleshooting

### Service not starting
```bash
docker-compose logs api
docker-compose logs worker
```

### Tasks not running
```bash
# Check worker
docker-compose logs worker

# Check queue
docker-compose exec worker celery -A tasks.app inspect active
```

### Can't connect to Mastodon
```bash
# Test connection
docker-compose exec api python -c "
from mastodon import Mastodon
from config import settings
m = Mastodon(access_token=settings.mastodon_access_token, 
             api_base_url=settings.mastodon_instance_url)
print(m.account_verify_credentials())
"
```

### Redis issues
```bash
# Check Redis
docker-compose exec redis redis-cli ping

# View keys
docker-compose exec redis redis-cli KEYS "mastodon_poll:*"
```

## 📊 Workflow States

```
┌─────────┐
│ PENDING │ ──── Polls generated, awaiting moderation
└────┬────┘
     │
     ├──► APPROVED ──── Ready to post
     │
     └──► REJECTED ──── Not suitable for posting

APPROVED ──► POSTED ──── Successfully posted to Mastodon
         └─► FAILED ──── Posting failed
```

## 💡 Tips

1. **Run cycles regularly** - Use cron or scheduler
2. **Monitor pending count** - Keep queue manageable
3. **Review prompts** - Adjust for better poll quality
4. **Check stats** - Monitor success rates
5. **Rotate tokens** - Regular security practice

## 📚 Documentation

- **[README.md](README.md)** - Full documentation
- **[API.md](API.md)** - Complete API reference
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Deployment guide
- **[example_workflow.py](example_workflow.py)** - Example usage

## 🆘 Getting Help

1. Check logs: `docker-compose logs -f`
2. Review documentation
3. Run example: `python example_workflow.py`
4. Check Nagatha Core status
5. Verify credentials in `.env`
