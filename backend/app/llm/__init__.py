from .llm_client import LLMClient
from .gemini_client import GeminiLLMClient


def create_llm_client(provider: str = "gemini", **kwargs) -> LLMClient:
    """Factory: return the LLM client."""
    if provider == "gemini":
        return GeminiLLMClient(**kwargs)
    raise ValueError(f"Unknown LLM provider: {provider}")
