"""
Abstract base for mapping generic configuration to provider-specific formats.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class ProviderConfigMapper(ABC):
    """Abstract base class for provider-specific configuration mapping."""

    def map_reasoning_params(self, enable_reasoning: str, thinking_budget: int) -> Dict[str, Any]:
        """
        Map generic reasoning configuration to provider-specific parameters.

        Default implementation uses Anthropic-style thinking format.
        Override in subclasses for provider-specific formats.

        Args:
            enable_reasoning: 'none', 'low', 'medium', 'high'
            thinking_budget: Token budget for reasoning (0 = disabled)

        Returns:
            Dictionary of provider-specific parameters to add to completion call
        """
        params = {}

        if enable_reasoning != 'none' and thinking_budget > 0:
            params['thinking'] = {
                'type': 'enabled',
                'budget_tokens': thinking_budget
            }

        return params

    def supports_reasoning(self, model_name: str) -> bool:
        """
        Check if the given model supports reasoning parameters.

        Default implementation returns True for all models.
        Override in subclasses to exclude specific models.
        """
        return True

    def uses_transcription_endpoint(self, model_name: str) -> bool:
        """Check if model uses transcription endpoint (not chat completions)."""
        return False

    def map_audio_params(self, audio_base64: str, audio_format: str) -> Dict[str, Any]:
        """
        Map audio input to provider-specific format.
        Default implementation uses OpenAI-compatible format.

        Returns:
            Dictionary with audio content structure
        """
        return {
            "type": "input_audio",
            "input_audio": {
                "data": audio_base64,
                "format": audio_format
            }
        }
