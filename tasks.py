"""Celery tasks for Mastodon Poll Provider."""
import os
import json
import logging
import re
from datetime import datetime, timedelta, timezone
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

# Simple text helpers for relevance scoring
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "by",
    "is",
    "it",
    "this",
    "that",
    "at",
    "as",
    "from",
    "be",
    "are",
    "was",
    "were",
}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "")


def _tokenize(text: str) -> set:
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {t for t in tokens if len(t) > 1 and t not in STOPWORDS}


def _normalize_hashtag(tag: str) -> str:
    tag = (tag or "").strip().lstrip("#")
    return f"#{tag}" if tag else ""


def _score_post_for_poll(question: str, options: List[str], post: Dict[str, Any]) -> int:
    query_tokens = _tokenize(question + " " + " ".join(options))
    post_body = _strip_html(post.get("content", ""))
    post_tags = post.get("hashtags", []) or []
    post_text = post_body + " " + " ".join(post_tags)
    post_tokens = _tokenize(post_text)
    if not query_tokens or not post_tokens:
        return 0
    return len(query_tokens & post_tokens)


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
        # Load app settings for ingestion filters
        app_settings = storage.get_settings()
        time_window_hours = getattr(app_settings, 'time_window_hours', 72) or 72
        exclude_used = getattr(app_settings, 'exclude_used_posts', True)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)
        
        # Get bot's own account info to exclude self-posts
        bot_account = mastodon.account_verify_credentials()
        bot_username = bot_account['username'].lower()
        logger.info(f"Bot account: @{bot_username}")
        
        # Load excluded accounts from settings
        app_settings = storage.get_settings()
        excluded_usernames = {acc.lower().lstrip('@') for acc in app_settings.excluded_accounts}
        # Always exclude bot's own account
        excluded_usernames.add(bot_username)
        logger.info(f"Excluding accounts: {excluded_usernames}")
        
        all_posts = []
        # Exclude posts we've already used in previous polls
        used_post_ids = set(storage.get_used_posts())
        logger.info(f"Used post IDs loaded: {len(used_post_ids)}")
        filtered_count = 0
        
        for hashtag in hashtags:
            # Remove # if present
            tag = hashtag.lstrip('#')
            
            # Fetch timeline for hashtag
            timeline = mastodon.timeline_hashtag(tag, limit=limit)
            
            for status in timeline:
                account_username = status['account']['username'].lower()
                
                # Skip if from excluded account or bot itself
                if account_username in excluded_usernames:
                    filtered_count += 1
                    logger.debug(f"Filtered post from excluded account: @{account_username}")
                    continue
                
                # Skip if outside time window
                try:
                    created_at = status['created_at']
                    created_at_utc = None
                    if isinstance(created_at, datetime):
                        if created_at.tzinfo is None:
                            created_at_utc = created_at.replace(tzinfo=timezone.utc)
                        else:
                            created_at_utc = created_at.astimezone(timezone.utc)
                    elif isinstance(created_at, str):
                        try:
                            # Attempt ISO parsing
                            dt = datetime.fromisoformat(created_at)
                            created_at_utc = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                        except Exception:
                            created_at_utc = None
                    if created_at_utc and created_at_utc < cutoff_time:
                        filtered_count += 1
                        logger.debug(f"Filtered old post outside window: {status['id']}")
                        continue
                except Exception:
                    logger.debug("Failed to evaluate created_at for time window; skipping filter")

                # Skip if post was previously used
                if exclude_used and str(status['id']) in used_post_ids:
                    filtered_count += 1
                    logger.debug(f"Filtered previously used post: {status['id']}")
                    continue

                post = MastodonPost(
                    id=str(status['id']),
                    content=status['content'],
                    created_at=status['created_at'],
                    url=status['url'],
                    account_username=status['account']['username'],
                    hashtags=[t['name'] for t in status.get('tags', [])]
                )
                all_posts.append(post.model_dump())
        
        logger.info(f"Fetched {len(all_posts)} posts (filtered {filtered_count} from excluded/used accounts)")
        
        return {
            "success": True,
            "posts": all_posts,
            "count": len(all_posts),
            "filtered_count": filtered_count,
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
        
        fallback_hashtags = app_settings.hashtags[:3]
        
        # Prepare post content for LLM
        posts_text = "\n\n".join([
            f"Post {i+1} by @{post.get('account_username', 'unknown')}:\n{post.get('content', '')}"
            for i, post in enumerate(posts[:50])  # Limit to 50 posts to avoid token limits
        ])
        
        # Format prompt and ask for per-poll hashtags grounded in source posts
        prompt = app_settings.poll_prompt_template.format(posts=posts_text) + """

Return a JSON array of poll objects. Each object MUST include:
- question: string
- options: array of 2-4 strings
- hashtags: array of 2-3 hashtags (include the #). Prefer hashtags that appear in the posts above; if none are suitable, propose relevant ones for visibility.
"""
        
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
        
        for idea in poll_ideas:
            if not isinstance(idea, dict):
                continue
                
            question = idea.get('question', '')
            options = idea.get('options', [])
            
            if not question or not options or len(options) < 2:
                continue
            
            # Select relevant source posts for this poll
            scored_posts = []
            for post in posts[:50]:
                try:
                    score = _score_post_for_poll(question, options, post)
                except Exception:
                    score = 0
                scored_posts.append((score, post))
            scored_posts.sort(key=lambda x: x[0], reverse=True)
            top_posts = [p for score, p in scored_posts if score > 0][:10]
            if not top_posts:
                top_posts = list(posts[:5])  # Fallback to a few posts if nothing matched
            source_post_ids = [str(p.get("id")) for p in top_posts if p.get("id")][:10]

            # Derive hashtags from relevant posts - collect more for better coverage
            hashtags_from_posts = []
            for p in top_posts:
                for tag in p.get("hashtags", []) or []:
                    norm = _normalize_hashtag(tag)
                    if norm and norm not in hashtags_from_posts:
                        hashtags_from_posts.append(norm)
                    if len(hashtags_from_posts) >= 15:  # Collect more, will trim by char limit later
                        break
                if len(hashtags_from_posts) >= 15:
                    break

            # LLM-suggested hashtags (per-poll)
            llm_hashtags = []
            raw_llm_tags = idea.get("hashtags", [])
            if isinstance(raw_llm_tags, list):
                for tag in raw_llm_tags:
                    norm = _normalize_hashtag(tag)
                    if norm and norm not in llm_hashtags:
                        llm_hashtags.append(norm)

            # Hybrid merge: prefer source-post tags, then LLM, then fallback
            # Limit total hashtag length to 200 chars (including spaces and #)
            poll_hashtags = []
            total_hashtag_length = 0
            for bucket in (hashtags_from_posts, llm_hashtags, fallback_hashtags):
                for tag in bucket:
                    if tag and tag not in poll_hashtags:
                        # Calculate length with # and space: "#tag "
                        tag_length = len(tag) + 2  # +1 for #, +1 for space
                        if total_hashtag_length + tag_length <= 200:
                            poll_hashtags.append(tag)
                            total_hashtag_length += tag_length
                        else:
                            break  # Stop adding if we'd exceed 200 chars
                if total_hashtag_length >= 190:  # Close to limit, stop
                    break

            # Create poll data with per-poll hashtags
            # Get duration from LLM suggestion, validate and clamp to 1-168 hours
            suggested_duration = idea.get('duration_hours', 24)
            if isinstance(suggested_duration, (int, float)):
                duration_hours = max(1, min(168, int(suggested_duration)))
            else:
                duration_hours = 24  # Fallback if invalid
            
            poll_data = PollData(
                question=question[:300],  # Mastodon instance limit
                options=[PollOption(text=opt[:50]) for opt in options[:4]],  # Max 4 options, 50 chars each
                duration_hours=duration_hours,
                hashtags=poll_hashtags,
                reasoning=idea.get('reasoning')  # Store LLM's explanation
            )
            
            # Validate total poll text length (question + hashtags) <= 500 chars
            # Mastodon counts: question + " " + "#tag1 #tag2" etc
            hashtag_text = " ".join(poll_hashtags)
            total_poll_text_length = len(poll_data.question) + 1 + len(hashtag_text)  # +1 for space
            if total_poll_text_length > 500:
                # Trim hashtags to fit within 500 char limit
                available_for_hashtags = 500 - len(poll_data.question) - 1
                trimmed_hashtags = []
                current_length = 0
                for tag in poll_hashtags:
                    tag_with_space = tag + " "
                    if current_length + len(tag_with_space) <= available_for_hashtags:
                        trimmed_hashtags.append(tag)
                        current_length += len(tag_with_space)
                    else:
                        break
                poll_data.hashtags = trimmed_hashtags
            
            # Create poll record
            poll_id = storage.generate_poll_id()
            poll_record = PollRecord(
                id=poll_id,
                poll_data=poll_data,
                source_posts=source_post_ids,  # Store relevant source posts
                status=PollStatus.PENDING
            )
            
            # Save to storage
            storage.save_poll(poll_record)
            # Mark source posts as used to avoid recycling in future cycles
            try:
                storage.mark_posts_used(source_post_ids)
            except Exception:
                logger.warning("Failed to mark source posts as used")
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
        
        # Create poll with hashtags inline
        poll_data = poll_record.poll_data
        options = [opt.text for opt in poll_data.options]
        
        # Format hashtags inline with question to save character space
        hashtags_str = " ".join(poll_data.hashtags) if poll_data.hashtags else ""
        status_text = f"{poll_data.question} {hashtags_str}".strip()
        
        logger.info(f"Posting poll with text: {status_text}")
        
        # Post status with poll
        status = mastodon.status_post(
            status=status_text,
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


@app.task(name="mastodon_poll_provider.tasks.process_news_cycle", bind=True)
def process_news_cycle(self, hashtags: List[str] = None, post_limit: int = None) -> Dict[str, Any]:
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
        self.update_state(state='PROGRESS', meta={'stage': 'fetch', 'message': 'Fetching posts from Mastodon...'})
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
        self.update_state(state='PROGRESS', meta={'stage': 'generate', 'message': f'Generating polls from {len(posts)} posts...', 'posts_fetched': len(posts)})
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
