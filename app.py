"""FastAPI application for Mastodon Poll Provider."""
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config import settings
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

# Initialize storage
storage = PollStorage()


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
