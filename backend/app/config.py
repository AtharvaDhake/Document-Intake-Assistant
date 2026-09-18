"""
Application configuration — read from .env file and environment variables.

LLM_PROVIDER controls which LLM client is used:
  - "mock"   → deterministic keyword-based client (no API key needed)
  - "gemini" → real Gemini 3.5 Flash Lite via google-genai SDK
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (one level above backend/)
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)


class Config:
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    @classmethod
    def validate(cls) -> None:
        """Fail fast if config is invalid — called at app startup."""
        if cls.LLM_PROVIDER != "gemini":
            raise ValueError(
                f"LLM_PROVIDER must be 'gemini', got '{cls.LLM_PROVIDER}'"
            )
        if not cls.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY must be set in environment variables."
            )
