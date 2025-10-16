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
        'groq': GroqMapper,
    }

    _provider_aliases = {
        'google': 'gemini',
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
        canonical_provider = cls._provider_aliases.get(provider_lower, provider_lower)
        mapper_class = cls._mappers.get(canonical_provider)

        if mapper_class is None:
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Supported providers: {', '.join(cls._mappers.keys())}"
            )

        return mapper_class()
