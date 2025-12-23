"""Configuration management for Mastodon Poll Provider."""
import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Nagatha Core Settings
    core_url: str = Field(default="http://nagatha_core:8000/api/v1")
    provider_id: str = Field(default="mastodon_poll_provider")
    provider_base_url: str = Field(default="http://mastodon_poll_provider:9000")
    queue_name: str = Field(default="mastodon_polls")
    
    # Celery Settings
    broker_url: str = Field(default="amqp://guest:guest@rabbitmq:5672//")
    result_backend: str = Field(default="redis://redis:6379/0")
    
    # Mastodon Settings
    mastodon_access_token: str = Field(default="")
    mastodon_instance_url: str = Field(default="https://stranger.social")
    mastodon_hashtags: str = Field(default="#uspol")
    mastodon_post_limit: int = Field(default=100)
    
    # OpenAI Settings
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o-mini")
    openai_max_tokens: int = Field(default=1500)
    openai_temperature: float = Field(default=0.7)
    
    # Application Settings
    log_level: str = Field(default="INFO")
    environment: str = Field(default="development")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def hashtag_list(self) -> List[str]:
        """Parse hashtags into a list."""
        return [tag.strip() for tag in self.mastodon_hashtags.split(",")]


# Global settings instance
settings = Settings()
