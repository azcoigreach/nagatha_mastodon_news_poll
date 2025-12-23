"""Celery tasks for Mastodon Poll Provider."""
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any
from celery import Celery
from mastodon import Mastodon
import openai

from config import settings
from models import (
    MastodonPost,
    PollData,
    PollOption,
    PollRecord,
    PollStatus,
    AppSettings
)
from storage import PollStorage


# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize Celery app
app = Celery("mastodon_poll_provider")
app.conf.update(
    broker_url=settings.broker_url,
    result_backend=settings.result_backend,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue=settings.queue_name or "mastodon_polls",
)

# Initialize storage
storage = PollStorage()


def get_mastodon_client() -> Mastodon:
    """Get configured Mastodon client."""
    if not settings.mastodon_access_token:
        raise ValueError("Mastodon access token not configured")
    
    return Mastodon(
        access_token=settings.mastodon_access_token,
        api_base_url=settings.mastodon_instance_url
    )


def get_openai_client():
    """Get configured OpenAI client."""
    if not settings.openai_api_key:
        raise ValueError("OpenAI API key not configured")
    
    openai.api_key = settings.openai_api_key
    return openai


@app.task(name="mastodon_poll_provider.tasks.fetch_mastodon_posts")
def fetch_mastodon_posts(hashtags: List[str] = None, limit: int = None) -> Dict[str, Any]:
    """
    Fetch posts from Mastodon for specified hashtags.
    
    Args:
        hashtags: List of hashtags to search (default: from settings)
        limit: Maximum number of posts to fetch (default: from settings)
        
    Returns:
        Dictionary with posts and metadata
    """
    try:
        hashtags = hashtags or settings.hashtag_list
        limit = limit or settings.mastodon_post_limit
        
        logger.info(f"Fetching Mastodon posts for hashtags: {hashtags}, limit: {limit}")
        
        mastodon = get_mastodon_client()
        all_posts = []
        
        for hashtag in hashtags:
            # Remove # if present
            tag = hashtag.lstrip('#')
            
            # Fetch timeline for hashtag
            timeline = mastodon.timeline_hashtag(tag, limit=limit)
            
            for status in timeline:
                post = MastodonPost(
                    id=str(status['id']),
                    content=status['content'],
                    created_at=status['created_at'],
                    url=status['url'],
                    account_username=status['account']['username'],
                    hashtags=[t['name'] for t in status.get('tags', [])]
                )
                all_posts.append(post.model_dump())
        
        logger.info(f"Fetched {len(all_posts)} posts")
        
        return {
            "success": True,
            "posts": all_posts,
            "count": len(all_posts),
            "hashtags": hashtags,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching Mastodon posts: {e}")
        return {
            "success": False,
            "error": str(e),
            "posts": [],
            "count": 0
        }


@app.task(name="mastodon_poll_provider.tasks.generate_poll_ideas")
def generate_poll_ideas(posts: List[Dict[str, Any]], settings_override: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Use OpenAI to generate poll ideas from Mastodon posts.
    
    Args:
        posts: List of Mastodon posts
        settings_override: Optional settings to override defaults
        
    Returns:
        Dictionary with generated poll ideas
    """
    try:
        logger.info(f"Generating poll ideas from {len(posts)} posts")
        
        # Load app settings
        app_settings = storage.get_settings()
        if settings_override:
            for key, value in settings_override.items():
                if hasattr(app_settings, key):
                    setattr(app_settings, key, value)
        
        # Prepare post content for LLM
        posts_text = "\n\n".join([
            f"Post {i+1} by @{post.get('account_username', 'unknown')}:\n{post.get('content', '')}"
            for i, post in enumerate(posts[:50])  # Limit to 50 posts to avoid token limits
        ])
        
        # Format prompt
        prompt = app_settings.poll_prompt_template.format(posts=posts_text)
        
        # Call OpenAI
        get_openai_client()
        response = openai.chat.completions.create(
            model=app_settings.llm_model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes social media posts and generates engaging poll questions."},
                {"role": "user", "content": prompt}
            ],
            temperature=app_settings.llm_temperature,
            max_tokens=app_settings.llm_max_tokens,
            response_format={"type": "json_object"}
        )
        
        # Parse response
        content = response.choices[0].message.content
        poll_ideas = json.loads(content)
        
        # If the response is wrapped in a key, unwrap it
        if isinstance(poll_ideas, dict) and 'polls' in poll_ideas:
            poll_ideas = poll_ideas['polls']
        elif isinstance(poll_ideas, dict) and not isinstance(poll_ideas, list):
            # Try to find the array
            for key, value in poll_ideas.items():
                if isinstance(value, list):
                    poll_ideas = value
                    break
        
        # Create PollRecord objects for each idea
        poll_records = []
        source_post_ids = [post.get('id') for post in posts if post.get('id')]
        
        for idea in poll_ideas:
            if not isinstance(idea, dict):
                continue
                
            question = idea.get('question', '')
            options = idea.get('options', [])
            
            if not question or not options or len(options) < 2:
                continue
            
            # Create poll data
            poll_data = PollData(
                question=question[:100],  # Mastodon limit
                options=[PollOption(text=opt[:50]) for opt in options[:4]]  # Max 4 options, 50 chars each
            )
            
            # Create poll record
            poll_id = storage.generate_poll_id()
            poll_record = PollRecord(
                id=poll_id,
                poll_data=poll_data,
                source_posts=source_post_ids[:10],  # Store up to 10 source posts
                status=PollStatus.PENDING
            )
            
            # Save to storage
            storage.save_poll(poll_record)
            poll_records.append(poll_record.model_dump())
        
        logger.info(f"Generated {len(poll_records)} poll ideas")
        
        return {
            "success": True,
            "polls": poll_records,
            "count": len(poll_records),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating poll ideas: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "polls": [],
            "count": 0
        }


@app.task(name="mastodon_poll_provider.tasks.post_poll_to_mastodon")
def post_poll_to_mastodon(poll_id: str) -> Dict[str, Any]:
    """
    Post an approved poll to Mastodon.
    
    Args:
        poll_id: ID of the poll to post
        
    Returns:
        Dictionary with posting result
    """
    try:
        logger.info(f"Posting poll {poll_id} to Mastodon")
        
        # Get poll from storage
        poll_record = storage.get_poll(poll_id)
        if not poll_record:
            raise ValueError(f"Poll {poll_id} not found")
        
        # Verify poll is approved
        if poll_record.status != PollStatus.APPROVED:
            raise ValueError(f"Poll {poll_id} is not approved for posting (status: {poll_record.status})")
        
        # Get Mastodon client
        mastodon = get_mastodon_client()
        
        # Create poll
        poll_data = poll_record.poll_data
        options = [opt.text for opt in poll_data.options]
        
        # Post status with poll
        status = mastodon.status_post(
            status=poll_data.question,
            poll={
                'options': options,
                'expires_in': poll_data.duration_hours * 3600,  # Convert hours to seconds
                'multiple': False
            }
        )
        
        # Update poll record
        poll_record.status = PollStatus.POSTED
        poll_record.mastodon_poll_id = str(status['poll']['id']) if status.get('poll') else None
        poll_record.mastodon_post_url = status['url']
        poll_record.updated_at = datetime.utcnow()
        
        storage.save_poll(poll_record)
        
        logger.info(f"Successfully posted poll {poll_id} to Mastodon: {status['url']}")
        
        return {
            "success": True,
            "poll_id": poll_id,
            "mastodon_post_url": status['url'],
            "mastodon_poll_id": poll_record.mastodon_poll_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error posting poll to Mastodon: {e}", exc_info=True)
        
        # Update poll status to failed
        try:
            poll_record = storage.get_poll(poll_id)
            if poll_record:
                poll_record.status = PollStatus.FAILED
                poll_record.updated_at = datetime.utcnow()
                storage.save_poll(poll_record)
        except:
            pass
        
        return {
            "success": False,
            "error": str(e),
            "poll_id": poll_id
        }


@app.task(name="mastodon_poll_provider.tasks.process_news_cycle")
def process_news_cycle(hashtags: List[str] = None, post_limit: int = None) -> Dict[str, Any]:
    """
    Complete workflow: Fetch posts, generate polls, and queue for moderation.
    
    Args:
        hashtags: List of hashtags to monitor
        post_limit: Number of posts to fetch
        
    Returns:
        Dictionary with results of the full cycle
    """
    try:
        logger.info("Starting news cycle processing")
        
        # Step 1: Fetch posts
        fetch_result = fetch_mastodon_posts(hashtags=hashtags, limit=post_limit)
        if not fetch_result['success']:
            return {
                "success": False,
                "error": f"Failed to fetch posts: {fetch_result.get('error')}",
                "stage": "fetch"
            }
        
        posts = fetch_result['posts']
        logger.info(f"Fetched {len(posts)} posts")
        
        # Step 2: Generate poll ideas
        generate_result = generate_poll_ideas(posts=posts)
        if not generate_result['success']:
            return {
                "success": False,
                "error": f"Failed to generate polls: {generate_result.get('error')}",
                "stage": "generate",
                "posts_fetched": len(posts)
            }
        
        polls = generate_result['polls']
        logger.info(f"Generated {len(polls)} poll ideas")
        
        return {
            "success": True,
            "posts_fetched": len(posts),
            "polls_generated": len(polls),
            "poll_ids": [p['id'] for p in polls],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in news cycle processing: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "stage": "unknown"
        }
