# Nagatha Mastodon News Poll

> **Automated poll generation from Mastodon news posts** – A Nagatha Core provider that monitors Mastodon hashtags, uses AI to generate poll ideas, and provides human moderation before posting.

![Python Version](https://img.shields.io/badge/python-3.13%2B-blue)
![Nagatha Core](https://img.shields.io/badge/nagatha-core%20provider-green)
![Status](https://img.shields.io/badge/status-Alpha-yellow)

## 🎯 Overview

This is the first application built on the [nagatha_core](https://github.com/azcoigreach/nagatha_core) infrastructure. It demonstrates how to:

- Register as a provider with Nagatha Core
- Leverage Nagatha's task queue system (Celery + RabbitMQ)
- Use Redis for state management
- Implement human-in-the-loop workflows
- Integrate with external APIs (Mastodon, OpenAI)

## 🚀 Features

- ✅ **Automated News Monitoring** - Fetch posts from Mastodon hashtags (#uspol, etc.)
- ✅ **AI Poll Generation** - Use OpenAI to analyze posts and create engaging polls
- ✅ **Human Moderation** - Review, edit, approve/reject polls via REST API
- ✅ **Mastodon Integration** - Post approved polls directly to Mastodon
- ✅ **Configurable** - All settings manageable through API (hashtags, LLM params, prompts)
- ✅ **Task-Based Architecture** - Leverages Nagatha Core's queue system
- ✅ **Redis Storage** - Stateful poll tracking and management

## 📋 Prerequisites

1. **Nagatha Core** running (REQUIRED - provides RabbitMQ and Redis)
   ```bash
   git clone https://github.com/azcoigreach/nagatha_core
   cd nagatha_core
   docker-compose up -d
   ```
   
   **Important**: This application uses nagatha_core's RabbitMQ and Redis services. Do not run duplicate services.

2. **Mastodon Access Token**
   - Create an application in your Mastodon instance settings
   - Get your access token

3. **OpenAI API Key**
   - Sign up at https://platform.openai.com
   - Generate an API key

## 🔧 Setup

### 1. Clone and Configure

```bash
git clone <this-repo>
cd nagatha_mastodon_news_poll

# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

Required environment variables:
```env
# Mastodon
MASTODON_ACCESS_TOKEN=your_token_here
MASTODON_INSTANCE_URL=https://stranger.social
MASTODON_HASHTAGS=#uspol

# OpenAI
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
```

### 2. Deploy with Docker Compose

**Note**: This deployment connects to nagatha_core's existing RabbitMQ and Redis. Make sure nagatha_core is running first.

```bash
# Make entrypoint executable
chmod +x docker-entrypoint.sh

# Start services (connects to nagatha_core network)
docker-compose up -d

# View logs
docker-compose logs -f
```

**For standalone deployment** (includes own RabbitMQ/Redis - NOT recommended in low-memory environments):
```bash
docker-compose -f docker-compose.standalone.yml up -d
```

### 3. Verify Registration

```bash
# Check provider is registered with Nagatha Core
curl http://localhost:8000/api/v1/providers

# Check this provider's health
curl http://localhost:9000/health

# View available tasks
curl http://localhost:8000/api/v1/tasks/catalog
```

## 📖 Usage

### Running a News Cycle

Fetch posts and generate poll ideas:

```bash
curl -X POST http://localhost:9000/run-cycle \
  -H "Content-Type: application/json" \
  -d '{
    "hashtags": ["#uspol", "#news"],
    "post_limit": 100
  }'
```

Or trigger via Nagatha Core:

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

### Moderating Polls

**List pending polls:**
```bash
curl http://localhost:9000/polls?status_filter=pending
```

**Get poll details:**
```bash
curl http://localhost:9000/polls/{poll_id}
```

**Edit a poll:**
```bash
curl -X PUT http://localhost:9000/polls/{poll_id} \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Updated question?",
    "options": ["Option A", "Option B", "Option C"],
    "duration_hours": 48
  }'
```

**Approve and post:**
```bash
# Approve
curl -X POST http://localhost:9000/polls/{poll_id}/moderate \
  -H "Content-Type: application/json" \
  -d '{
    "approved": true,
    "moderator_notes": "Looks good!"
  }'

# Queue for posting
curl -X POST http://localhost:9000/post-poll \
  -H "Content-Type: application/json" \
  -d '{"poll_id": "{poll_id}"}'
```

**Reject:**
```bash
curl -X POST http://localhost:9000/polls/{poll_id}/moderate \
  -H "Content-Type: application/json" \
  -d '{
    "approved": false,
    "moderator_notes": "Not relevant"
  }'
```

### Configuring Settings

**View current settings:**
```bash
curl http://localhost:9000/settings
```

**Update settings:**
```bash
curl -X PUT http://localhost:9000/settings \
  -H "Content-Type: application/json" \
  -d '{
    "hashtags": ["#uspol", "#politics", "#news"],
    "post_limit": 150,
    "llm_model": "gpt-4o-mini",
    "llm_temperature": 0.8,
    "poll_prompt_template": "Your custom prompt..."
  }'
```

### Statistics

```bash
curl http://localhost:9000/stats
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Nagatha Core                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ RabbitMQ │  │  Redis   │  │   API    │         │
│  └──────────┘  └──────────┘  └──────────┘         │
└─────────────────┬───────────────────────────────────┘
                  │ Task Queue & Results
                  │
┌─────────────────┴───────────────────────────────────┐
│         Mastodon Poll Provider                      │
│                                                     │
│  ┌──────────────────┐  ┌──────────────────┐       │
│  │   FastAPI App    │  │  Celery Worker   │       │
│  │  - Moderation    │  │  - Fetch Posts   │       │
│  │  - Settings      │  │  - Generate      │       │
│  │  - Manifest      │  │  - Post Polls    │       │
│  └────────┬─────────┘  └────────┬─────────┘       │
│           │                     │                  │
│           └──────────┬──────────┘                  │
│                      │                             │
│           ┌──────────▼─────────┐                   │
│           │   Redis Storage    │                   │
│           │  - Polls           │                   │
│           │  - Settings        │                   │
│           └────────────────────┘                   │
└─────────────────────────────────────────────────────┘
         │                            │
         │                            │
    ┌────▼────┐                  ┌───▼────┐
    │ Mastodon│                  │ OpenAI │
    └─────────┘                  └────────┘
```

## 📁 Project Structure

```
nagatha_mastodon_news_poll/
├── app.py                      # FastAPI application
├── tasks.py                    # Celery tasks
├── config.py                   # Configuration management
├── models.py                   # Data models
├── storage.py                  # Redis storage layer
├── register.py                 # Provider registration
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container definition
├── docker-compose.yml          # Compose for nagatha_core network
├── docker-compose.standalone.yml # Standalone deployment
├── docker-entrypoint.sh        # Container entrypoint
├── .env.example                # Environment template
└── README.md                   # This file
```

## 🔌 API Endpoints

### Provider Endpoints
- `GET /health` - Health check
- `GET /.well-known/nagatha/manifest` - Provider manifest
- `GET /tasks` - List available tasks

### Poll Management
- `GET /polls` - List polls (with optional status filter)
- `GET /polls/{poll_id}` - Get poll details
- `PUT /polls/{poll_id}` - Update poll
- `POST /polls/{poll_id}/moderate` - Approve/reject poll
- `DELETE /polls/{poll_id}` - Delete poll

### Workflows
- `POST /run-cycle` - Fetch posts and generate polls
- `POST /post-poll` - Queue poll for posting

### Settings & Stats
- `GET /settings` - Get current settings
- `PUT /settings` - Update settings
- `GET /stats` - Get statistics

## 🧪 Development

```bash
# Install dependencies locally
pip install -r requirements.txt

# Run locally (requires RabbitMQ and Redis)
python -m uvicorn app:app --reload --port 9000

# Run worker
celery -A tasks.app worker --loglevel=info --queues=mastodon_polls

# Run tests (TODO)
pytest tests/ -v
```

## 🔒 Security Notes

- **Never commit `.env`** - Contains sensitive tokens
- **Human moderation required** - No polls posted without approval
- **Rate limiting** - Consider implementing for production
- **Token rotation** - Regularly rotate API tokens
- **Access control** - Add authentication to moderation endpoints for production

## 🚦 Workflow Example

1. **Schedule or trigger news cycle**
   ```bash
   POST /run-cycle
   ```

2. **System fetches Mastodon posts** (task: `fetch_mastodon_posts`)

3. **AI generates poll ideas** (task: `generate_poll_ideas`)
   - Polls created with status `PENDING`

4. **Human moderator reviews**
   ```bash
   GET /polls?status_filter=pending
   ```

5. **Moderator edits and approves**
   ```bash
   PUT /polls/{id}  # Optional edits
   POST /polls/{id}/moderate  # Approve
   ```

6. **Queue poll for posting**
   ```bash
   POST /post-poll
   ```

7. **System posts to Mastodon** (task: `post_poll_to_mastodon`)
   - Poll status updated to `POSTED`

## 📝 License

MIT License - See LICENSE file for details

## 🔗 Links

- [Nagatha Core](https://github.com/azcoigreach/nagatha_core)
- [Mastodon API](https://docs.joinmastodon.org/api/)
- [OpenAI API](https://platform.openai.com/docs)

## 🤝 Contributing

This is the first Nagatha Core provider application. Feedback and contributions welcome!

---

**Built with ❤️ using Nagatha Core**