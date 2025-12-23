"""FastAPI application for Mastodon Poll Provider."""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, status, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel

from config import settings

# Setup logging
logger = logging.getLogger(__name__)
from models import (
    PollRecord,
    PollStatus,
    ModerationRequest,
    AppSettings,
    PollData,
    PollOption
)
from storage import PollStorage


app = FastAPI(
    title="Mastodon Poll Provider",
    description="Nagatha Core provider for generating and moderating Mastodon polls from news content",
    version="1.0.0"
)

# Add session middleware for flash messages
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key or "default-secret-key-change-in-production")

# Initialize storage
storage = PollStorage()

# Setup templates and static files
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# Health check
@app.get("/health")
async def health() -> Dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "ok",
        "provider_id": settings.provider_id,
        "timestamp": datetime.utcnow().isoformat()
    }


# Provider manifest
@app.get("/.well-known/nagatha/manifest")
async def manifest() -> Dict[str, Any]:
    """Return provider manifest for Nagatha Core registration."""
    return {
        "manifest_version": 1,
        "provider_id": settings.provider_id,
        "base_url": settings.provider_base_url,
        "version": "1.0.0",
        "tasks": [
            {
                "name": "mastodon_poll.fetch_posts",
                "description": "Fetch posts from Mastodon by hashtags",
                "version": "1.0.0",
                "celery_name": "mastodon_poll_provider.tasks.fetch_mastodon_posts",
                "queue": settings.queue_name,
                "timeout_s": 120,
                "retries": 2,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "hashtags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of hashtags to search"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of posts to fetch"
                        }
                    }
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "posts": {"type": "array"},
                        "count": {"type": "integer"}
                    }
                }
            },
            {
                "name": "mastodon_poll.generate_polls",
                "description": "Generate poll ideas using AI from Mastodon posts",
                "version": "1.0.0",
                "celery_name": "mastodon_poll_provider.tasks.generate_poll_ideas",
                "queue": settings.queue_name,
                "timeout_s": 180,
                "retries": 1,
                "input_schema": {
                    "type": "object",
                    "required": ["posts"],
                    "properties": {
                        "posts": {
                            "type": "array",
                            "description": "List of Mastodon posts to analyze"
                        },
                        "settings_override": {
                            "type": "object",
                            "description": "Optional settings overrides"
                        }
                    }
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "polls": {"type": "array"},
                        "count": {"type": "integer"}
                    }
                }
            },
            {
                "name": "mastodon_poll.post_poll",
                "description": "Post an approved poll to Mastodon",
                "version": "1.0.0",
                "celery_name": "mastodon_poll_provider.tasks.post_poll_to_mastodon",
                "queue": settings.queue_name,
                "timeout_s": 60,
                "retries": 2,
                "input_schema": {
                    "type": "object",
                    "required": ["poll_id"],
                    "properties": {
                        "poll_id": {
                            "type": "string",
                            "description": "ID of the poll to post"
                        }
                    }
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "poll_id": {"type": "string"},
                        "mastodon_post_url": {"type": "string"}
                    }
                }
            },
            {
                "name": "mastodon_poll.process_cycle",
                "description": "Complete workflow: fetch posts, generate polls, queue for moderation",
                "version": "1.0.0",
                "celery_name": "mastodon_poll_provider.tasks.process_news_cycle",
                "queue": settings.queue_name,
                "timeout_s": 300,
                "retries": 1,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "hashtags": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "post_limit": {"type": "integer"}
                    }
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "posts_fetched": {"type": "integer"},
                        "polls_generated": {"type": "integer"},
                        "poll_ids": {"type": "array"}
                    }
                }
            }
        ]
    }


# Task listing
@app.get("/tasks")
async def tasks_list() -> Dict[str, Any]:
    """List available tasks."""
    return {
        "tasks": [
            "mastodon_poll.fetch_posts",
            "mastodon_poll.generate_polls",
            "mastodon_poll.post_poll",
            "mastodon_poll.process_cycle"
        ],
        "queue": settings.queue_name
    }


# ========== Moderation Endpoints ==========

@app.get("/polls")
async def list_polls(
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """
    List polls with optional status filter.
    
    Args:
        status_filter: Filter by status (pending, approved, rejected, posted)
        limit: Maximum number of polls to return
        offset: Number of polls to skip
        
    Returns:
        Dictionary with polls and metadata
    """
    try:
        if status_filter:
            try:
                poll_status = PollStatus(status_filter)
                polls = storage.get_polls_by_status(poll_status)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}. Valid values: {[s.value for s in PollStatus]}"
                )
        else:
            polls = storage.get_all_polls(limit=limit, offset=offset)
        
        return {
            "success": True,
            "polls": [poll.model_dump() for poll in polls],
            "count": len(polls),
            "filter": status_filter,
            "limit": limit,
            "offset": offset
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing polls: {str(e)}"
        )


@app.get("/polls/{poll_id}")
async def get_poll(poll_id: str) -> Dict[str, Any]:
    """
    Get details of a specific poll.
    
    Args:
        poll_id: ID of the poll
        
    Returns:
        Poll details
    """
    poll = storage.get_poll(poll_id)
    if not poll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Poll {poll_id} not found"
        )
    
    return {
        "success": True,
        "poll": poll.model_dump()
    }


class PollUpdateRequest(BaseModel):
    """Request to update a poll."""
    question: Optional[str] = None
    options: Optional[List[str]] = None
    duration_hours: Optional[int] = None


@app.put("/polls/{poll_id}")
async def update_poll(poll_id: str, update: PollUpdateRequest) -> Dict[str, Any]:
    """
    Update a poll's question and/or options.
    
    Args:
        poll_id: ID of the poll
        update: Updated poll data
        
    Returns:
        Updated poll
    """
    poll = storage.get_poll(poll_id)
    if not poll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Poll {poll_id} not found"
        )
    
    # Only allow editing pending polls
    if poll.status != PollStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit poll with status {poll.status.value}. Only pending polls can be edited."
        )
    
    # Update fields
    if update.question is not None:
        poll.poll_data.question = update.question[:100]  # Mastodon limit
    
    if update.options is not None:
        if len(update.options) < 2 or len(update.options) > 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Polls must have 2-4 options"
            )
        poll.poll_data.options = [PollOption(text=opt[:50]) for opt in update.options]
    
    if update.duration_hours is not None:
        if update.duration_hours < 1 or update.duration_hours > 168:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duration must be between 1 and 168 hours"
            )
        poll.poll_data.duration_hours = update.duration_hours
    
    poll.updated_at = datetime.utcnow()
    storage.save_poll(poll)
    
    return {
        "success": True,
        "poll": poll.model_dump(),
        "message": "Poll updated successfully"
    }


@app.post("/polls/{poll_id}/moderate")
async def moderate_poll(poll_id: str, moderation: ModerationRequest) -> Dict[str, Any]:
    """
    Approve or reject a poll.
    
    Args:
        poll_id: ID of the poll
        moderation: Moderation decision
        
    Returns:
        Updated poll status
    """
    poll = storage.get_poll(poll_id)
    if not poll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Poll {poll_id} not found"
        )
    
    # Update poll based on moderation
    old_status = poll.status
    
    if moderation.approved:
        # Apply edits if provided
        if moderation.edited_question:
            poll.poll_data.question = moderation.edited_question[:100]
        
        if moderation.edited_options:
            if len(moderation.edited_options) < 2 or len(moderation.edited_options) > 4:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Polls must have 2-4 options"
                )
            poll.poll_data.options = [PollOption(text=opt[:50]) for opt in moderation.edited_options]
        
        poll.status = PollStatus.APPROVED
    else:
        poll.status = PollStatus.REJECTED
    
    if moderation.moderator_notes:
        poll.moderator_notes = moderation.moderator_notes
    
    poll.moderated_at = datetime.utcnow()
    poll.updated_at = datetime.utcnow()
    
    # Update in storage
    storage.update_poll_status(poll_id, old_status, poll.status)
    storage.save_poll(poll)
    
    return {
        "success": True,
        "poll": poll.model_dump(),
        "message": f"Poll {'approved' if moderation.approved else 'rejected'} successfully"
    }


@app.delete("/polls/{poll_id}")
async def delete_poll(poll_id: str) -> Dict[str, Any]:
    """
    Delete a poll.
    
    Args:
        poll_id: ID of the poll
        
    Returns:
        Success message
    """
    poll = storage.get_poll(poll_id)
    if not poll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Poll {poll_id} not found"
        )
    
    # Don't allow deleting posted polls
    if poll.status == PollStatus.POSTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete posted polls"
        )
    
    success = storage.delete_poll(poll_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete poll"
        )
    
    return {
        "success": True,
        "message": f"Poll {poll_id} deleted successfully"
    }


# ========== Settings Endpoints ==========

@app.get("/settings")
async def get_settings() -> Dict[str, Any]:
    """Get current application settings."""
    app_settings = storage.get_settings()
    return {
        "success": True,
        "settings": app_settings.model_dump()
    }


@app.put("/settings")
async def update_settings(new_settings: AppSettings) -> Dict[str, Any]:
    """
    Update application settings.
    
    Args:
        new_settings: New settings to apply
        
    Returns:
        Updated settings
    """
    try:
        success = storage.save_settings(new_settings)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save settings"
            )
        
        return {
            "success": True,
            "settings": new_settings.model_dump(),
            "message": "Settings updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating settings: {str(e)}"
        )


# ========== Statistics Endpoints ==========

@app.get("/stats")
async def get_statistics() -> Dict[str, Any]:
    """Get statistics about polls."""
    stats = storage.get_statistics()
    return {
        "success": True,
        "statistics": stats,
        "timestamp": datetime.utcnow().isoformat()
    }


# ========== Workflow Endpoints ==========

class RunCycleRequest(BaseModel):
    """Request to run a news cycle."""
    hashtags: Optional[List[str]] = None
    post_limit: Optional[int] = None


@app.post("/run-cycle")
async def run_news_cycle(request: RunCycleRequest = None) -> Dict[str, Any]:
    """
    Trigger a news cycle: fetch posts and generate poll ideas.
    
    This endpoint queues the task through Nagatha Core rather than
    executing it directly.
    
    Args:
        request: Optional parameters for the cycle
        
    Returns:
        Information about the queued task
    """
    from tasks import process_news_cycle
    
    hashtags = request.hashtags if request else None
    post_limit = request.post_limit if request else None
    
    # Queue the task
    task = process_news_cycle.delay(hashtags=hashtags, post_limit=post_limit)
    
    return {
        "success": True,
        "task_id": task.id,
        "message": "News cycle task queued",
        "status": "pending"
    }


class PostPollRequest(BaseModel):
    """Request to post a poll."""
    poll_id: str


@app.post("/post-poll")
async def queue_post_poll(request: PostPollRequest) -> Dict[str, Any]:
    """
    Queue an approved poll for posting to Mastodon.
    
    Args:
        request: Poll ID to post
        
    Returns:
        Task information
    """
    from tasks import post_poll_to_mastodon
    
    # Verify poll exists and is approved
    poll = storage.get_poll(request.poll_id)
    if not poll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Poll {request.poll_id} not found"
        )
    
    if poll.status != PollStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Poll must be approved before posting (current status: {poll.status.value})"
        )
    
    # Queue the task
    task = post_poll_to_mastodon.delay(poll_id=request.poll_id)
    
    return {
        "success": True,
        "task_id": task.id,
        "poll_id": request.poll_id,
        "message": "Post poll task queued",
        "status": "pending"
    }


# ========== Web UI Routes ==========

def flash_message(request: Request, message: str, message_type: str = "info"):
    """Add a flash message to the session."""
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append({"text": message, "type": message_type})


def clear_flash_messages(request: Request):
    """Clear flash messages from the session."""
    if "_messages" in request.session:
        del request.session["_messages"]


@app.post("/clear-messages")
async def clear_messages(request: Request):
    """Clear flash messages (called by JS after display)."""
    clear_flash_messages(request)
    return {"success": True}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard home page."""
    stats = storage.get_statistics()
    current_settings = storage.get_settings()
    
    # Get recent polls
    recent_polls = storage.list_polls_paginated(page=1, page_size=10)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": stats,
        "current_settings": current_settings,
        "recent_polls": recent_polls
    })


@app.get("/polls-ui", response_class=HTMLResponse)
async def polls_list(request: Request, status: Optional[str] = None, page: int = 1):
    """Poll moderation queue page."""
    page_size = 50
    status_filter = status if status and status != "all" else None
    
    # Get polls
    polls = storage.list_polls_paginated(
        status_filter=status_filter,
        page=page,
        page_size=page_size
    )
    
    # Get statistics for tab badges
    stats = storage.get_statistics()
    total_count = stats.get("total_polls", 0)
    by_status = stats.get("by_status", {})
    
    # Calculate pagination
    if status_filter:
        total_items = by_status.get(status_filter, 0)
    else:
        total_items = total_count
    
    total_pages = (total_items + page_size - 1) // page_size
    
    # Clear flash messages from previous action
    messages = request.session.get("_messages", [])
    clear_flash_messages(request)
    # Re-add them for this render only
    if messages:
        request.session["_messages"] = messages
    
    return templates.TemplateResponse("polls_list.html", {
        "request": request,
        "polls": polls,
        "status_filter": status_filter or "all",
        "current_page": page,
        "total_pages": total_pages,
        "total_count": total_count,
        "pending_count": by_status.get("pending", 0),
        "approved_count": by_status.get("approved", 0),
        "posted_count": by_status.get("posted", 0),
        "rejected_count": by_status.get("rejected", 0),
        "failed_count": by_status.get("failed", 0),
    })


@app.get("/polls-ui/{poll_id}", response_class=HTMLResponse)
async def poll_detail(request: Request, poll_id: str):
    """Poll detail and edit page."""
    poll = storage.get_poll(poll_id)
    if not poll:
        flash_message(request, f"Poll {poll_id} not found", "danger")
        return RedirectResponse(url="/polls-ui", status_code=303)
    
    # Fetch source posts if available
    source_posts = []
    if poll.source_posts:
        from tasks import get_mastodon_client
        try:
            mastodon = get_mastodon_client()
            for post_id in poll.source_posts[:10]:  # Limit to 10 posts
                try:
                    status = mastodon.status(post_id)
                    source_posts.append({
                        "id": str(status["id"]),
                        "content": status["content"],
                        "created_at": status["created_at"].isoformat() if hasattr(status["created_at"], "isoformat") else str(status["created_at"]),
                        "url": status.get("url", ""),
                        "account_username": status["account"]["username"],
                        "hashtags": [t["name"] for t in status.get("tags", [])]
                    })
                except Exception as e:
                    logger.error(f"Error fetching source post {post_id}: {e}")
        except Exception as e:
            logger.error(f"Error initializing Mastodon client: {e}")
    
    return templates.TemplateResponse("poll_detail.html", {
        "request": request,
        "poll": poll,
        "source_posts": source_posts
    })


@app.post("/polls-ui/{poll_id}/update")
async def update_poll_ui(
    request: Request,
    poll_id: str,
    question: str = Form(...),
    option_0: str = Form(...),
    option_1: str = Form(...),
    option_2: str = Form(""),
    option_3: str = Form(""),
    duration_hours: int = Form(...)
):
    """Update poll from form submission."""
    poll = storage.get_poll(poll_id)
    if not poll:
        flash_message(request, f"Poll {poll_id} not found", "danger")
        return RedirectResponse(url="/polls-ui", status_code=303)
    
    if poll.status != PollStatus.PENDING:
        flash_message(request, "Only pending polls can be edited", "warning")
        return RedirectResponse(url=f"/polls-ui/{poll_id}", status_code=303)
    
    # Build options list
    options = []
    for opt_text in [option_0, option_1, option_2, option_3]:
        if opt_text.strip():
            options.append(PollOption(text=opt_text.strip(), votes=0))
    
    if len(options) < 2 or len(options) > 4:
        flash_message(request, "Poll must have 2-4 options", "danger")
        return RedirectResponse(url=f"/polls-ui/{poll_id}", status_code=303)
    
    # Update poll data
    poll.poll_data = PollData(
        question=question,
        options=options,
        duration_hours=duration_hours
    )
    poll.updated_at = datetime.utcnow()
    
    success = storage.update_poll(poll)
    if success:
        flash_message(request, "Poll updated successfully", "success")
    else:
        flash_message(request, "Failed to update poll", "danger")
    
    return RedirectResponse(url=f"/polls-ui/{poll_id}", status_code=303)


@app.post("/polls-ui/{poll_id}/moderate")
async def moderate_poll_ui(
    request: Request,
    poll_id: str,
    approved: str = Form(...),
    notes: str = Form("")
):
    """Moderate poll from form submission."""
    poll = storage.get_poll(poll_id)
    if not poll:
        flash_message(request, f"Poll {poll_id} not found", "danger")
        return RedirectResponse(url="/polls-ui", status_code=303)
    
    is_approved = approved.lower() == "true"
    
    if is_approved:
        poll.status = PollStatus.APPROVED
        flash_message(request, "Poll approved successfully", "success")
    else:
        poll.status = PollStatus.REJECTED
        flash_message(request, "Poll rejected", "info")
    
    poll.moderated_at = datetime.utcnow()
    poll.moderator_notes = notes
    poll.updated_at = datetime.utcnow()
    
    success = storage.update_poll(poll)
    if not success:
        flash_message(request, "Failed to update poll status", "danger")
    
    return RedirectResponse(url=f"/polls-ui/{poll_id}", status_code=303)


@app.post("/polls-ui/{poll_id}/delete")
async def delete_poll_ui(request: Request, poll_id: str):
    """Delete poll from UI."""
    poll = storage.get_poll(poll_id)
    if not poll:
        flash_message(request, f"Poll {poll_id} not found", "danger")
        return RedirectResponse(url="/polls-ui", status_code=303)
    
    if poll.status != PollStatus.PENDING:
        flash_message(request, "Only pending polls can be deleted", "warning")
        return RedirectResponse(url=f"/polls-ui/{poll_id}", status_code=303)
    
    success = storage.delete_poll(poll_id)
    if success:
        flash_message(request, "Poll deleted successfully", "success")
    else:
        flash_message(request, "Failed to delete poll", "danger")
    
    return RedirectResponse(url="/polls-ui", status_code=303)


@app.post("/polls-ui/{poll_id}/post")
async def post_poll_ui(request: Request, poll_id: str):
    """Post poll to Mastodon from UI."""
    from tasks import post_poll_to_mastodon
    
    poll = storage.get_poll(poll_id)
    if not poll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Poll {poll_id} not found"
        )
    
    if poll.status != PollStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Poll must be approved before posting (current status: {poll.status.value})"
        )
    
    # Queue the task
    task = post_poll_to_mastodon.delay(poll_id=poll_id)
    
    return {
        "success": True,
        "task_id": task.id,
        "poll_id": poll_id,
        "message": "Post poll task queued"
    }


@app.get("/settings-ui", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings configuration page."""
    settings_data = storage.get_settings()
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": settings_data
    })


@app.post("/settings-ui/update")
async def update_settings_ui(
    request: Request,
    hashtags: List[str] = Form(...),
    post_limit: int = Form(...),
    llm_model: str = Form(...),
    llm_temperature: float = Form(...),
    llm_max_tokens: int = Form(...),
    poll_prompt_template: str = Form(...)
):
    """Update settings from form submission."""
    # Clean hashtags
    clean_hashtags = [tag.strip().lstrip('#') for tag in hashtags if tag.strip()]
    
    new_settings = AppSettings(
        hashtags=[f"#{tag}" if not tag.startswith('#') else tag for tag in clean_hashtags],
        post_limit=post_limit,
        llm_model=llm_model,
        llm_temperature=llm_temperature,
        llm_max_tokens=llm_max_tokens,
        poll_prompt_template=poll_prompt_template
    )
    
    success = storage.save_settings(new_settings)
    if success:
        flash_message(request, "Settings updated successfully", "success")
    else:
        flash_message(request, "Failed to update settings", "danger")
    
    return RedirectResponse(url="/settings-ui", status_code=303)
