"""Redis-based storage for polls and settings."""
import json
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
import redis

from config import settings
from models import PollRecord, AppSettings, PollStatus


class PollStorage:
    """Manage poll storage in Redis."""
    
    def __init__(self):
        """Initialize Redis connection."""
        # Extract Redis host and port from result_backend URL
        # Format: redis://host:port/db
        url_parts = settings.result_backend.replace('redis://', '').split('/')
        host_port = url_parts[0].split(':')
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 6379
        db = int(url_parts[1]) if len(url_parts) > 1 else 0
        
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True
        )
        
        # Key prefixes
        self.POLL_PREFIX = "mastodon_poll:"
        self.SETTINGS_KEY = "mastodon_poll:settings"
        self.POLL_LIST_KEY = "mastodon_poll:list"
        self.USED_POSTS_KEY = "mastodon_poll:used_posts"
    
    def generate_poll_id(self) -> str:
        """Generate a unique poll ID."""
        return f"poll_{uuid.uuid4().hex[:12]}"
    
    def save_poll(self, poll: PollRecord) -> bool:
        """
        Save a poll to Redis.
        
        Args:
            poll: PollRecord to save
            
        Returns:
            True if successful
        """
        try:
            key = f"{self.POLL_PREFIX}{poll.id}"
            data = poll.model_dump_json()
            
            # Save poll data
            self.redis_client.set(key, data)
            
            # Add to poll list
            self.redis_client.sadd(self.POLL_LIST_KEY, poll.id)
            
            # Add to status-specific set for easy querying
            status_key = f"{self.POLL_PREFIX}status:{poll.status.value}"
            self.redis_client.sadd(status_key, poll.id)
            
            return True
        except Exception as e:
            print(f"Error saving poll: {e}")
            return False
    
    def get_poll(self, poll_id: str) -> Optional[PollRecord]:
        """
        Get a poll by ID.
        
        Args:
            poll_id: ID of the poll
            
        Returns:
            PollRecord if found, None otherwise
        """
        try:
            key = f"{self.POLL_PREFIX}{poll_id}"
            data = self.redis_client.get(key)
            
            if data:
                return PollRecord.model_validate_json(data)
            return None
        except Exception as e:
            print(f"Error getting poll: {e}")
            return None
    
    def get_polls_by_status(self, status: PollStatus) -> List[PollRecord]:
        """
        Get all polls with a specific status.
        
        Args:
            status: Status to filter by
            
        Returns:
            List of PollRecords
        """
        try:
            status_key = f"{self.POLL_PREFIX}status:{status.value}"
            poll_ids = self.redis_client.smembers(status_key)
            
            polls = []
            for poll_id in poll_ids:
                poll = self.get_poll(poll_id)
                if poll:
                    polls.append(poll)
            
            return polls
        except Exception as e:
            print(f"Error getting polls by status: {e}")
            return []
    
    def update_poll_status(self, poll_id: str, old_status: PollStatus, new_status: PollStatus) -> bool:
        """
        Update a poll's status and move it between status sets.
        
        Args:
            poll_id: ID of the poll
            old_status: Current status
            new_status: New status
            
        Returns:
            True if successful
        """
        try:
            # Remove from old status set
            old_key = f"{self.POLL_PREFIX}status:{old_status.value}"
            self.redis_client.srem(old_key, poll_id)
            
            # Add to new status set
            new_key = f"{self.POLL_PREFIX}status:{new_status.value}"
            self.redis_client.sadd(new_key, poll_id)
            
            return True
        except Exception as e:
            print(f"Error updating poll status: {e}")
            return False
    
    def delete_poll(self, poll_id: str) -> bool:
        """
        Delete a poll from storage.
        
        Args:
            poll_id: ID of the poll to delete
            
        Returns:
            True if successful
        """
        try:
            # Get poll to find its status
            poll = self.get_poll(poll_id)
            if poll:
                # Remove from status set
                status_key = f"{self.POLL_PREFIX}status:{poll.status.value}"
                self.redis_client.srem(status_key, poll_id)
            
            # Remove from main list
            self.redis_client.srem(self.POLL_LIST_KEY, poll_id)
            
            # Delete poll data
            key = f"{self.POLL_PREFIX}{poll_id}"
            self.redis_client.delete(key)
            
            return True
        except Exception as e:
            print(f"Error deleting poll: {e}")
            return False
    
    def get_all_polls(self, limit: int = 100, offset: int = 0) -> List[PollRecord]:
        """
        Get all polls with pagination.
        
        Args:
            limit: Maximum number of polls to return
            offset: Number of polls to skip
            
        Returns:
            List of PollRecords
        """
        try:
            poll_ids = list(self.redis_client.smembers(self.POLL_LIST_KEY))
            poll_ids = poll_ids[offset:offset + limit]
            
            polls = []
            for poll_id in poll_ids:
                poll = self.get_poll(poll_id)
                if poll:
                    polls.append(poll)
            
            # Sort by created_at descending
            polls.sort(key=lambda x: x.created_at, reverse=True)
            
            return polls
        except Exception as e:
            print(f"Error getting all polls: {e}")
            return []
    
    def list_polls_paginated(self, status_filter: Optional[str] = None, page: int = 1, page_size: int = 50) -> List[PollRecord]:
        """
        Get polls with pagination and optional status filtering.
        
        Args:
            status_filter: Optional status to filter by (e.g., 'pending', 'approved', 'posted')
            page: Page number (1-indexed)
            page_size: Number of polls per page
            
        Returns:
            List of PollRecords for the requested page
        """
        try:
            if status_filter:
                # Get polls for specific status
                status_key = f"{self.POLL_PREFIX}status:{status_filter}"
                poll_ids = list(self.redis_client.smembers(status_key))
            else:
                # Get all polls
                poll_ids = list(self.redis_client.smembers(self.POLL_LIST_KEY))
            
            # Fetch all polls to sort by created_at
            all_polls = []
            for poll_id in poll_ids:
                poll = self.get_poll(poll_id)
                if poll:
                    all_polls.append(poll)
            
            # Sort by created_at (newest first)
            all_polls.sort(key=lambda p: p.created_at, reverse=True)
            
            # Calculate pagination
            offset = (page - 1) * page_size
            paginated_polls = all_polls[offset:offset + page_size]
            
            return paginated_polls
        except Exception as e:
            print(f"Error listing polls: {e}")
            return []
    
    def update_poll(self, poll: PollRecord) -> bool:
        """
        Update an existing poll.
        
        Args:
            poll: PollRecord to update
            
        Returns:
            True if successful
        """
        try:
            key = f"{self.POLL_PREFIX}{poll.id}"
            data = poll.model_dump_json()
            
            # Update poll data
            self.redis_client.set(key, data)
            
            # Update status sets - remove from old status, add to new status
            for status in PollStatus:
                status_key = f"{self.POLL_PREFIX}status:{status.value}"
                if status.value == poll.status.value:
                    # Add to current status set
                    self.redis_client.sadd(status_key, poll.id)
                else:
                    # Remove from other status sets
                    self.redis_client.srem(status_key, poll.id)
            
            return True
        except Exception as e:
            print(f"Error updating poll: {e}")
            return False
    
    def get_settings(self) -> AppSettings:
        """
        Get application settings from Redis.
        
        Returns:
            AppSettings object
        """
        try:
            data = self.redis_client.get(self.SETTINGS_KEY)
            if data:
                return AppSettings.model_validate_json(data)
            else:
                # Return default settings
                return AppSettings()
        except Exception as e:
            print(f"Error getting settings: {e}")
            return AppSettings()
    
    def save_settings(self, app_settings: AppSettings) -> bool:
        """
        Save application settings to Redis.
        
        Args:
            app_settings: AppSettings to save
            
        Returns:
            True if successful
        """
        try:
            data = app_settings.model_dump_json()
            self.redis_client.set(self.SETTINGS_KEY, data)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about polls.
        
        Returns:
            Dictionary with statistics
        """
        try:
            stats = {
                "total_polls": self.redis_client.scard(self.POLL_LIST_KEY),
                "by_status": {}
            }
            
            for status in PollStatus:
                status_key = f"{self.POLL_PREFIX}status:{status.value}"
                count = self.redis_client.scard(status_key)
                stats["by_status"][status.value] = count
            
            return stats
        except Exception as e:
            print(f"Error getting statistics: {e}")
            return {"error": str(e)}

    # --- Post usage tracking ---
    def mark_posts_used(self, post_ids: List[str]) -> bool:
        """Mark Mastodon post IDs as used to avoid re-processing.

        Args:
            post_ids: List of Mastodon status IDs

        Returns:
            True if successful
        """
        try:
            if not post_ids:
                return True
            # Use Redis set for deduplication
            self.redis_client.sadd(self.USED_POSTS_KEY, *post_ids)
            return True
        except Exception as e:
            print(f"Error marking posts used: {e}")
            return False

    def get_used_posts(self) -> List[str]:
        """Return list of Mastodon post IDs previously used for polls."""
        try:
            return list(self.redis_client.smembers(self.USED_POSTS_KEY))
        except Exception:
            return []

    def clear_used_posts(self) -> bool:
        """Clear the used posts set (maintenance)."""
        try:
            self.redis_client.delete(self.USED_POSTS_KEY)
            return True
        except Exception as e:
            print(f"Error clearing used posts: {e}")
            return False
