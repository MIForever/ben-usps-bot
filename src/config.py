import os
import logging
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Telegram Bot Configuration
    BOT_TOKEN: str = Field(..., env='BOT_TOKEN')
    TELEGAM_CHANNEL_ID: str = Field(..., env='TELEGAM_CHANNEL_ID')

    DB_PATH: str = Field(..., env='DB_PATH')
    MAX_LOADS: int = Field(..., env='MAX_LOADS')
    
    CITIES_FILE: str = Field(..., env='CITIES_FILE')
    
    # Optional settings with defaults
    MAX_RETRIES: int = Field(default=3, env='MAX_RETRIES')

    # Error notification settings
    ADMIN_IDS: list[int] = Field(default=[], env='ADMIN_IDS')
    ERROR_NOTIFICATION_ENABLED: bool = Field(default=True, env='ERROR_NOTIFICATION_ENABLED')
    ERROR_NOTIFICATION_DELAY: int = Field(default=60, env='ERROR_NOTIFICATION_DELAY')
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = True
    
    @validator('TELEGAM_CHANNEL_ID')
    def validate_channel_id(cls, v):
        """Ensure TELEGAM_CHANNEL_ID starts with @ or is a valid numeric ID."""
        if not (v.startswith('@') or v.lstrip('-').isdigit()):
            raise ValueError('TELEGAM_CHANNEL_ID must start with @ or be a numeric ID')
        return v

def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()