# Quick Start: Testing Web UI in Docker

## 1. Prepare Environment

```bash
cd /home/azcoigreach/repos/nagatha_mastodon_news_poll

# Verify .env file has required keys
cat .env
# Should have: MASTODON_ACCESS_TOKEN, OPENAI_API_KEY, etc.
```

## 2. Start Nagatha Core (if not running)

```bash
cd ../nagatha_core
docker-compose up -d

# Wait for services to start
sleep 10
docker-compose ps
```

## 3. Build and Start Mastodon Poll Provider

```bash
cd ../nagatha_mastodon_news_poll

# Build images (this installs all dependencies including Jinja2)
docker-compose build

# Start all services
docker-compose up -d
```

## 4. Verify Services are Running

```bash
# Check containers
docker-compose ps

# Check API logs
docker logs -f mastodon_poll_api

# Wait for "Application startup complete" message
```

## 5. Access the Web UI

Open browser to:
```
http://localhost:9000/
```

You should see:
- Bootstrap-styled navigation bar
- Dashboard with statistics cards
- "Run News Cycle" button
- Links to "Moderation Queue" and "Settings"

## 6. Test the Workflow

### Test 1: Run News Cycle
1. Click "Run News Cycle" on dashboard
2. Enter hashtags (e.g., `#test, #news`)
3. Click "Run News Cycle" button
4. Should show success message with task ID
5. Navigate to "Moderation Queue" - wait for polls to appear

### Test 2: Moderate a Poll
1. Go to "Moderation Queue"
2. Click on any poll or use quick-action buttons
3. Try:
   - ✓ Edit question/options (if PENDING)
   - ✓ Click "Approve Poll" button
   - ✓ Add moderator notes
4. Poll status should change to APPROVED

### Test 3: View Details
1. Click on approved poll
2. See:
   - Mastodon preview on right (question + options)
   - Character counters
   - Source posts below preview
   - Post to Mastodon button

### Test 4: Post to Mastodon
1. From approved poll detail
2. Click "Post to Mastodon"
3. Poll status should change to POSTED
4. URL to Mastodon post should appear

### Test 5: Settings
1. Go to "Settings" tab
2. Modify:
   - Add/remove hashtags
   - Change LLM model
   - Adjust temperature slider
   - Edit prompt template
3. Click "Save Settings"
4. Should show success message

## 7. View Logs

```bash
# API server logs
docker logs mastodon_poll_api -f

# Celery worker logs  
docker logs mastodon_poll_worker -f

# All logs
docker-compose logs -f
```

## 8. Stop Services

```bash
docker-compose down

# Stop Nagatha Core too
cd ../nagatha_core
docker-compose down
```

---

## File Structure Created

```
nagatha_mastodon_news_poll/
├── templates/
│   ├── base.html          # Main layout (Bootstrap navbar, flash messages)
│   ├── dashboard.html     # Home page (stats, quick actions)
│   ├── polls_list.html    # Moderation queue (filtering, pagination)
│   ├── poll_detail.html   # Poll view/edit (preview, source posts)
│   └── settings.html      # Configuration (hashtags, LLM settings)
├── static/
│   ├── style.css          # Bootstrap customizations
│   └── app.js             # Form validation, live preview, etc.
└── app.py                 # Updated with HTML routes and handlers
```

---

## Key Implementation Details

### Templates Use:
- ✅ Bootstrap 5 CDN (no build step needed)
- ✅ HTMX CDN (for dynamic updates)
- ✅ Jinja2 template syntax
- ✅ Flask-style flash messages

### Routes Added:
- GET `/` → Dashboard
- GET `/polls-ui` → Queue
- GET `/polls-ui/{id}` → Detail
- POST `/polls-ui/{id}/update` → Update poll
- POST `/polls-ui/{id}/moderate` → Approve/reject
- POST `/polls-ui/{id}/post` → Post to Mastodon
- GET `/settings-ui` → Settings form
- POST `/settings-ui/update` → Save settings

### Form Validation:
- Client-side: Character counters, option count validation
- Server-side: Pydantic models + manual checks

### Dependencies (already in requirements.txt):
- ✅ fastapi
- ✅ jinja2 (already installed)
- ✅ python-multipart (for form parsing)
- ✅ starlette (included with FastAPI)

---

## Troubleshooting

### Issue: Templates not found (TemplateNotFound error)
**Solution**: Rebuild Docker image
```bash
docker-compose build --no-cache
docker-compose up -d
```

### Issue: Static files not loading (404 on /static/*)
**Solution**: Check Docker logs and ensure templates reference correct paths
```bash
docker logs mastodon_poll_api
# Look for errors in mount or file access
```

### Issue: Form submissions not working
**Solution**: Verify SessionMiddleware is initialized (it is in app.py)
```bash
# Check logs for middleware errors
docker logs mastodon_poll_api
```

### Issue: Mastodon post previews show no source posts
**Solution**: Ensure Mastodon token is valid and source_posts list is populated
```bash
docker logs mastodon_poll_api | grep -i source
```

---

## Next: Production Deployment

For production, consider:
1. Set `SECRET_KEY` to random string in .env
2. Enable HTTPS (use nginx proxy)
3. Add authentication (if sharing with team)
4. Set up CSRF protection
5. Configure logging/monitoring
