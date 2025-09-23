from typing import Optional, Union
from .groq_provider import GroqProvider
from .gemini_provider import GeminiProvider


class ProviderFactory:
    """Factory for creating transcription providers."""
    
    @staticmethod
    def create_provider(provider_name: str, model_id: str, language: Optional[str] = None) -> Union[GroqProvider, GeminiProvider, None]:
        """Create and return a provider instance."""
        provider_name = provider_name.lower()
        
        if provider_name == 'groq':
            return GroqProvider(model_id=model_id, language=language)
        elif provider_name == 'gemini':
            return GeminiProvider(model_id=model_id, language=language)
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")
    
    @staticmethod
    def get_supported_providers():
        """Return list of supported provider names."""
        return ['groq', 'gemini']