"""
Gemini-specific configuration mapper.
Maps generic configuration to Gemini API format.
"""
from typing import Dict, Any
from .provider_config_mapper import ProviderConfigMapper


class GeminiMapper(ProviderConfigMapper):
    """Configuration mapper for Gemini provider."""

    def map_reasoning_params(self, enable_reasoning: str, thinking_budget: int) -> Dict[str, Any]:
        """
        Map reasoning configuration to Gemini format.

        Gemini does not support reasoning parameters - return empty dict.
        """
        return {}

    def supports_reasoning(self, model_name: str) -> bool:
        """Gemini does not support reasoning parameters."""
        return False
