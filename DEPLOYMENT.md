# Deployment Guide

## Deployment Options

### Option 1: Deploy with Nagatha Core (Recommended)

This option connects to an existing Nagatha Core instance, sharing its RabbitMQ and Redis infrastructure.

**Prerequisites:**
- Nagatha Core running on the same Docker network

**Steps:**

1. **Start Nagatha Core**
   ```bash
   cd /path/to/nagatha_core
   docker-compose up -d
   ```

2. **Configure this provider**
   ```bash
   cd /home/azcoigreach/repos/nagatha_mastodon_news_poll
   cp .env.example .env
   nano .env  # Add your tokens
   ```

3. **Start provider services**
   ```bash
   docker-compose up -d
   ```

4. **Verify registration**
   ```bash
   # Check provider registered with core
   curl http://localhost:8000/api/v1/providers
   
   # Should show mastodon_poll_provider
   ```

### Option 2: Standalone Deployment

This option includes its own RabbitMQ and Redis instances.

**Steps:**

1. **Configure**
   ```bash
   cp .env.example .env
   nano .env
   ```

2. **Start services**
   ```bash
   docker-compose -f docker-compose.standalone.yml up -d
   ```

3. **Access**
   - API: http://localhost:9000
   - RabbitMQ Management: http://localhost:15672
   - Redis: localhost:6379

## Configuration

### Required Environment Variables

```env
# Mastodon (REQUIRED)
MASTODON_ACCESS_TOKEN=your_token_here
MASTODON_INSTANCE_URL=https://stranger.social

# OpenAI (REQUIRED)
OPENAI_API_KEY=your_key_here
```

### Optional Settings

These can be changed via the API after deployment:

```env
MASTODON_HASHTAGS=#uspol,#news
MASTODON_POST_LIMIT=100
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.7
```

## Obtaining Credentials

### Mastodon Access Token

1. Log into your Mastodon instance
2. Go to **Settings → Development → New Application**
3. Name: "Nagatha Poll Bot"
4. Scopes: `read:statuses`, `write:statuses`
5. Click **Submit**
6. Copy the **Access Token**

### OpenAI API Key

1. Visit https://platform.openai.com
2. Sign up or log in
3. Go to **API Keys**
4. Click **Create new secret key**
5. Copy the key (you won't see it again!)

## Monitoring

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f worker
docker-compose logs -f registration
```

### Check Health

```bash
curl http://localhost:9000/health
```

### View Statistics

```bash
curl http://localhost:9000/stats
```

## Troubleshooting

### Provider not registering

**Check logs:**
```bash
docker-compose logs registration
```

**Verify Nagatha Core is accessible:**
```bash
docker-compose exec api curl http://nagatha_core:8000/api/v1/ping
```

### Tasks not executing

**Check worker logs:**
```bash
docker-compose logs -f worker
```

**Verify queue connection:**
```bash
docker-compose exec worker celery -A tasks.app inspect active
```

### Mastodon API errors

**Common issues:**
- Invalid access token → Check token in .env
- Rate limiting → Reduce MASTODON_POST_LIMIT
- Invalid hashtags → Check hashtag format in settings

**Test connection:**
```bash
docker-compose exec api python -c "
from mastodon import Mastodon
from config import settings
m = Mastodon(access_token=settings.mastodon_access_token, api_base_url=settings.mastodon_instance_url)
print(m.account_verify_credentials())
"
```

### OpenAI API errors

**Common issues:**
- Invalid API key → Check OPENAI_API_KEY in .env
- Quota exceeded → Check usage at platform.openai.com
- Model not available → Use gpt-4o-mini or gpt-3.5-turbo

**Test connection:**
```bash
docker-compose exec api python -c "
import openai
from config import settings
openai.api_key = settings.openai_api_key
response = openai.models.list()
print('OpenAI connection successful')
"
```

### Redis connection issues

**Check Redis:**
```bash
docker-compose exec redis redis-cli ping
# Should return: PONG
```

**View stored polls:**
```bash
docker-compose exec redis redis-cli
> KEYS mastodon_poll:*
> GET mastodon_poll:settings
```

## Scaling

### Scale Workers

```bash
docker-compose up -d --scale worker=3
```

### Production Considerations

1. **Add authentication** to moderation endpoints
2. **Set up monitoring** (Prometheus, Grafana)
3. **Configure rate limiting**
4. **Enable HTTPS** via reverse proxy
5. **Set up backup** for Redis data
6. **Configure log rotation**

## Updating

```bash
# Pull latest changes
git pull

# Rebuild images
docker-compose build

# Restart services
docker-compose up -d
```

## Backup and Restore

### Backup Redis Data

```bash
docker-compose exec redis redis-cli BGSAVE
docker cp mastodon_poll_redis:/data/dump.rdb ./backup_$(date +%Y%m%d).rdb
```

### Restore Redis Data

```bash
docker-compose down
docker cp backup_20231215.rdb mastodon_poll_redis:/data/dump.rdb
docker-compose up -d
```

## Security Checklist

- [ ] `.env` file is not committed to git
- [ ] API endpoints have authentication (production)
- [ ] Tokens are rotated regularly
- [ ] HTTPS is enabled (production)
- [ ] Rate limiting is configured
- [ ] Logs don't expose sensitive data
- [ ] Redis is not publicly accessible
- [ ] RabbitMQ has strong credentials

## Support

For issues or questions:
1. Check the logs
2. Review this guide
3. Check Nagatha Core documentation
4. Open an issue on GitHub
