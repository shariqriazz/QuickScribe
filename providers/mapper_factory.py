"""
Factory for creating provider-specific configuration mappers.
"""
from .provider_config_mapper import ProviderConfigMapper
from .openrouter_mapper import OpenRouterMapper
from .anthropic_mapper import AnthropicMapper
from .openai_mapper import OpenAIMapper
from .gemini_mapper import GeminiMapper
from .groq_mapper import GroqMapper


class MapperFactory:
    """Factory for instantiating provider-specific mappers."""

    _mappers = {
        'openrouter': OpenRouterMapper,
        'anthropic': AnthropicMapper,
        'openai': OpenAIMapper,
        'gemini': GeminiMapper,
        'google': GeminiMapper,
        'groq': GroqMapper,
    }

    @classmethod
    def get_mapper(cls, provider: str) -> ProviderConfigMapper:
        """
        Get configuration mapper for provider.

        Args:
            provider: Provider name (lowercase)

        Returns:
            Provider-specific mapper instance

        Raises:
            ValueError: If provider not supported
        """
        provider_lower = provider.lower()
        mapper_class = cls._mappers.get(provider_lower)

        if mapper_class is None:
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Supported providers: {', '.join(cls._mappers.keys())}"
            )

        return mapper_class()
