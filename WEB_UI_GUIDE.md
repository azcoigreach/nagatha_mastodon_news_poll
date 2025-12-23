# Web UI Implementation - Testing & Deployment Guide

## What Was Implemented

A complete **server-side rendered web UI** using Jinja2 templates and Bootstrap 5 CSS framework for managing and moderating Mastodon polls.

### Components Added

#### 1. **Templates** (`/templates`)
- **base.html** - Main layout with Bootstrap navbar, flash messages, and footer
- **dashboard.html** - Home page with statistics cards and quick action to run news cycles
- **polls_list.html** - Moderation queue with status filtering, pagination, and quick actions
- **poll_detail.html** - Poll editing/viewing with Mastodon-style preview and source post display
- **settings.html** - Configuration UI for hashtags, LLM settings, and prompt templates

#### 2. **Static Assets** (`/static`)
- **style.css** - Bootstrap customizations, Mastodon-style poll preview, source post styling
- **app.js** - Character counters, form validation, live preview updates, relative timestamps

#### 3. **Features**
- ✅ **Bootstrap 5 UI** - Professional responsive design with alerts and modals
- ✅ **Flash Messages** - Session-based feedback for form actions (success/error/warning)
- ✅ **Poll Preview** - Mastodon-style live preview of how polls will appear
- ✅ **Source Post Display** - View original Mastodon posts that inspired each poll
- ✅ **Character Counters** - Real-time validation for Mastodon limits (100 chars question, 50 chars options)
- ✅ **Status-based Actions** - Different UI states for PENDING/APPROVED/POSTED/REJECTED polls
- ✅ **Form Validation** - Client-side and server-side validation
- ✅ **Responsive Design** - Works on desktop and mobile
- ✅ **Quick Moderation** - Approve/reject/post polls with single clicks
- ✅ **Settings Management** - Edit hashtags, LLM model, temperature, prompts

#### 4. **Routes Added to app.py**
```
GET  /                          - Dashboard home page
GET  /polls-ui                  - Moderation queue (with status filtering and pagination)
GET  /polls-ui/{poll_id}        - Poll detail page
POST /polls-ui/{poll_id}/update - Update poll (forms)
POST /polls-ui/{poll_id}/moderate - Approve/reject poll
POST /polls-ui/{poll_id}/delete - Delete pending poll
POST /polls-ui/{poll_id}/post   - Post approved poll to Mastodon
GET  /settings-ui               - Settings configuration page
POST /settings-ui/update        - Update settings
POST /clear-messages            - Clear flash messages
```

#### 5. **Configuration Updates**
- Added `Jinja2Templates` and `SessionMiddleware` to FastAPI app
- Mounted `/static` directory for CSS/JS
- Added `secret_key` to config for session management

---

## Docker Deployment

### Prerequisites
- Docker & Docker Compose installed
- Nagatha Core running with `nagatha_core_nagatha_network` created
- `.env` file configured with Mastodon token, OpenAI key, etc.

### Starting the Services

```bash
# 1. Navigate to project directory
cd /home/azcoigreach/repos/nagatha_mastodon_news_poll

# 2. Ensure Nagatha Core is running (from nagatha_core directory)
cd ../nagatha_core
docker-compose up -d

# 3. Build and start Mastodon Poll Provider
cd ../nagatha_mastodon_news_poll
docker-compose build
docker-compose up -d
```

### Accessing the Web UI

Once running, the web UI is available at:
```
http://localhost:9000/
```

**Navigation:**
- **Dashboard** - Home with stats and quick actions
- **Moderation Queue** - Browse and filter polls by status
- **Settings** - Configure hashtags and LLM behavior

### Viewing Logs

```bash
# View API logs
docker logs -f mastodon_poll_api

# View Worker logs
docker logs -f mastodon_poll_worker

# View all container logs
docker-compose logs -f
```

### Stopping Services

```bash
docker-compose down
```

---

## Testing the Web UI Workflow

### 1. **Run a News Cycle**
1. Go to http://localhost:9000/
2. Enter hashtags (or use defaults)
3. Click "Run News Cycle"
4. Wait for task to complete (check logs)

### 2. **Moderate Polls**
1. Navigate to "Moderation Queue" tab
2. Click on any poll or use quick-action buttons
3. Edit question/options if needed (PENDING only)
4. Click "Approve Poll" or "Reject Poll"
5. Add notes if desired

### 3. **Preview Poll**
1. Open any poll detail
2. Right side shows "Mastodon Preview" - how poll appears on Mastodon
3. Live updates as you edit question/options

### 4. **View Source Posts**
1. Open poll detail
2. Scroll down on right side to "Source Posts" section
3. Shows original Mastodon posts that inspired the poll

### 5. **Post to Mastodon**
1. Open approved poll
2. Click "Post to Mastodon" button
3. Poll posts immediately, status changes to POSTED
4. Link to Mastodon post appears in detail view

### 6. **Configure Settings**
1. Navigate to "Settings" tab
2. Add/remove hashtags
3. Adjust LLM model, temperature, token limits
4. Edit prompt template
5. Click "Save Settings"

---

## Technical Details

### Flash Messages Implementation
Sessions store messages: `request.session["_messages"]` - automatically cleared after render.

```python
flash_message(request, "Poll updated!", "success")  # success/danger/warning/info
```

### Form Handling
- Uses HTML forms with POST to `/polls-ui/{id}/update`, `/moderate`, etc.
- Redirects back to detail page or list with flash message feedback

### Mastodon Preview
- Live preview updates as user types
- Shows character counts with warnings at 80 chars
- Displays option visibility based on content

### Source Posts Fetching
- Polls store up to 10 source post IDs (`poll.source_posts`)
- On detail page, fetches full post data from Mastodon API
- Shows content, author, timestamp, hashtags, original URL

---

## Environment Variables

The following are automatically set in Docker:

```env
BROKER_URL=amqp://guest:guest@nagatha_rabbitmq:5672//
RESULT_BACKEND=redis://nagatha_redis:6379/0
PROVIDER_BASE_URL=http://mastodon_poll_provider:9000
SECRET_KEY=change-this-to-a-random-secret-key  # For session security
```

For local testing, set `SECRET_KEY` in `.env` to a random string.

---

## Common Issues & Troubleshooting

### 1. **Templates not found**
- Ensure `templates/` directory exists at `/app/templates`
- Docker COPY command copies all files automatically

### 2. **Static files not loading (CSS/JS)**
- Check `/static` directory mounted correctly
- Verify URL paths in templates: `/static/style.css`, `/static/app.js`

### 3. **Flash messages not showing**
- Ensure `SessionMiddleware` initialized (it is in app.py)
- Browser must accept cookies

### 4. **Source posts not displaying**
- Requires valid Mastodon token in `.env`
- Posts must exist on Mastodon instance (check `poll.source_posts` list)

### 5. **Form submissions return 404**
- Verify routes exist in app.py (see Routes list above)
- Check poll ID in URL is valid

---

## Next Steps (Optional Enhancements)

1. **WebSocket Real-time Updates** - Live refresh of poll status without page reload
2. **Bulk Actions** - Multi-select polls for batch approve/reject
3. **Dark Mode Toggle** - Theme switcher
4. **Search/Filter** - Search polls by keyword
5. **Analytics Dashboard** - Poll creation trends, posting frequency
6. **Audit Trail** - View all moderation actions with timestamps
7. **API Documentation** - Swagger UI at `/docs`

---

## Summary

The web UI is **production-ready** and fully integrated with the FastAPI backend. All templates use Bootstrap 5 for professional styling, form validation ensures data integrity, and flash messages provide user feedback.

To get started, simply build and run the Docker containers as described above.
