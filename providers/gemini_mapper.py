"""
Gemini-specific configuration mapper.
Maps generic configuration to Gemini API format.
"""
from .provider_config_mapper import ProviderConfigMapper


class GeminiMapper(ProviderConfigMapper):
    """Configuration mapper for Gemini provider."""
    pass
