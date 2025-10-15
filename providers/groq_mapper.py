"""
Groq-specific configuration mapper.
Maps generic configuration to Groq API format.
"""
from typing import Dict, Any
from .provider_config_mapper import ProviderConfigMapper


class GroqMapper(ProviderConfigMapper):
    """Configuration mapper for Groq provider."""

    def map_reasoning_params(self, enable_reasoning: str, thinking_budget: int) -> Dict[str, Any]:
        """
        Map reasoning configuration to Groq format.

        Groq does not support reasoning parameters - return empty dict.
        """
        return {}

    def supports_reasoning(self, model_name: str) -> bool:
        """Groq does not support reasoning parameters."""
        return False
