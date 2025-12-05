"""
Groq-specific configuration mapper.
Maps generic configuration to Groq API format.
"""
from .provider_config_mapper import ProviderConfigMapper


class GroqMapper(ProviderConfigMapper):
    """Configuration mapper for Groq provider."""
    pass
