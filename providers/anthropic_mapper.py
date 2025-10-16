"""
Anthropic-specific configuration mapper.
Maps generic configuration to Anthropic API format.
"""
from .provider_config_mapper import ProviderConfigMapper


class AnthropicMapper(ProviderConfigMapper):
    """Configuration mapper for Anthropic provider."""
    pass
