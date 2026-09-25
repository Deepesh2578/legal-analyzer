import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Legal Contract Analyzer"
    VERSION: str = "0.1.0"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@postgres:5432/legal_db")
    
    # Add Gemini API key field
    gemini_api_key: str = ""

    class Config:
        env_file = ".env"
        extra = "allow"  # Allow extra fields in case we add more later

settings = Settings()
