"""
Configuration management for Companion Agent
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Centralized configuration management"""
    
    # Supabase Configuration
    SUPABASE_URL: Optional[str] = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_ANON_KEY: Optional[str] = os.getenv("SUPABASE_ANON_KEY")
    
    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    
    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_ENABLED: bool = os.getenv("REDIS_ENABLED", "true").lower() == "true"
    
    # Uplift TTS Configuration
    UPLIFTAI_BASE_URL: str = os.getenv("UPLIFTAI_BASE_URL", "wss://api.upliftai.org")
    UPLIFTAI_API_KEY: Optional[str] = os.getenv("UPLIFTAI_API_KEY")
    
    # RAG Configuration
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    
    # Memory Configuration
    MAX_MEMORIES_TO_LOAD: int = 500
    
    # Conversation Configuration
    TIME_DECAY_HOURS: int = 24
    RECENCY_WEIGHT: float = 0.3
    
    # Testing/Development Configuration
    TEST_USER_ID: Optional[str] = os.getenv("TEST_USER_ID", "4e3efa3d-d8fe-431e-a78f-4efffb0cf43a")
    USE_TEST_USER: bool = os.getenv("USE_TEST_USER", "false").lower() == "true"
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration"""
        required = [
            ("SUPABASE_URL", cls.SUPABASE_URL),
            ("OPENAI_API_KEY", cls.OPENAI_API_KEY),
        ]
        
        missing = [name for name, value in required if not value]
        
        if missing:
            print(f"[CONFIG ERROR] Missing required configuration: {', '.join(missing)}")
            return False
        
        return True
    
    @classmethod
    def get_supabase_key(cls) -> Optional[str]:
        """Get the appropriate Supabase key"""
        return cls.SUPABASE_SERVICE_ROLE_KEY or cls.SUPABASE_ANON_KEY

