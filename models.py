"""Data models for Mastodon Poll Provider."""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class PollStatus(str, Enum):
    """Status of a poll in the moderation workflow."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    POSTED = "posted"
    FAILED = "failed"


class MastodonPost(BaseModel):
    """Represents a Mastodon post."""
    id: str
    content: str
    created_at: datetime
    url: str
    account_username: str
    hashtags: List[str] = []
    
    
class PollOption(BaseModel):
    """A single option in a poll."""
    text: str
    votes: int = 0


class PollData(BaseModel):
    """Data structure for a poll."""
    question: str
    options: List[PollOption]
    duration_hours: int = Field(default=24, ge=1, le=168)  # 1 hour to 7 days
    

class PollRecord(BaseModel):
    """Complete poll record with metadata."""
    id: str
    poll_data: PollData
    status: PollStatus = PollStatus.PENDING
    source_posts: List[str] = []  # List of Mastodon post IDs
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    moderated_at: Optional[datetime] = None
    moderator_notes: str = ""
    mastodon_poll_id: Optional[str] = None
    mastodon_post_url: Optional[str] = None
    
    
class AppSettings(BaseModel):
    """Configurable application settings via API."""
    hashtags: List[str] = ["#uspol"]
    post_limit: int = Field(default=100, ge=10, le=500)
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=1500, ge=100, le=4000)
    poll_prompt_template: str = Field(
        default="""Analyze the following Mastodon posts about current events and news:

{posts}

Based on these posts, generate poll topics that would engage the community. For each poll:
1. Create a clear, concise question (max 100 characters)
2. Provide 2-4 answer options
3. Focus on current events, news, or political topics mentioned in the posts
4. Make the poll balanced and non-partisan

Return your response as a JSON array of poll objects with this structure:
[
  {{
    "question": "Poll question here?",
    "options": ["Option 1", "Option 2", "Option 3"],
    "reasoning": "Brief explanation of why this poll is relevant"
  }}
]

Generate up to 5 poll ideas.
"""
    )
    

class ModerationRequest(BaseModel):
    """Request to moderate a poll."""
    approved: bool
    edited_question: Optional[str] = None
    edited_options: Optional[List[str]] = None
    moderator_notes: Optional[str] = None


class NotificationSettings(BaseModel):
    """Settings for notifications (future use)."""
    webhook_url: Optional[str] = None
    email: Optional[str] = None
    enabled: bool = False
