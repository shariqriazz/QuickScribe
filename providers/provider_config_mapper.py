"""
Abstract base for mapping generic configuration to provider-specific formats.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class ProviderConfigMapper(ABC):
    """Abstract base class for provider-specific configuration mapping."""

    @abstractmethod
    def map_reasoning_params(self, enable_reasoning: str, thinking_budget: int) -> Dict[str, Any]:
        """
        Map generic reasoning configuration to provider-specific parameters.

        Args:
            enable_reasoning: 'none', 'low', 'medium', 'high'
            thinking_budget: Token budget for reasoning (0 = disabled)

        Returns:
            Dictionary of provider-specific parameters to add to completion call
        """
        pass

    @abstractmethod
    def supports_reasoning(self, model_name: str) -> bool:
        """Check if the given model supports reasoning parameters."""
        pass

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
