# Setup Notes

## ✅ Configuration Complete

Your environment is now configured to use nagatha_core's existing services.

### Credentials Configured

- **Mastodon**: `https://stranger.social` with access token loaded
- **OpenAI**: API key configured for `gpt-4o-mini`
- **Hashtags**: Monitoring `#uspol`
- **Post Limit**: 100 posts per cycle

### Services Configuration

**Using nagatha_core's infrastructure:**
- RabbitMQ: `nagatha_rabbitmq:5672` ✅
- Redis: `nagatha_redis:6379` ✅
- No duplicate services ✅

### Network Setup

Connected to `nagatha_core_nagatha_network` external network.

## 🚀 Ready to Deploy

```bash
# Ensure nagatha_core is running
cd /path/to/nagatha_core
docker-compose ps

# Deploy this provider
cd /home/azcoigreach/repos/nagatha_mastodon_news_poll
docker-compose up -d

# Watch logs
docker-compose logs -f
```

## 📊 Verify

```bash
# Check provider health
curl http://localhost:9000/health

# Check registered with core
curl http://localhost:8000/api/v1/providers

# Run a test cycle
curl -X POST http://localhost:9000/run-cycle
```

## 💾 Memory Optimized

This configuration shares RabbitMQ and Redis with nagatha_core, saving significant memory:
- No duplicate RabbitMQ (~250MB saved)
- No duplicate Redis (~50MB saved)
- Total savings: ~300MB

Perfect for low-memory environments!
