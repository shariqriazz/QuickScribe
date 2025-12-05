"""
OpenAI-specific configuration mapper.
Maps generic configuration to OpenAI API format.
"""
from typing import Dict, Any
from .provider_config_mapper import ProviderConfigMapper


class OpenAIMapper(ProviderConfigMapper):
    """Configuration mapper for OpenAI provider."""

    def map_reasoning_params(self, enable_reasoning: str, thinking_budget: int) -> Dict[str, Any]:
        """
        Map reasoning configuration to OpenAI's reasoning_effort format.

        OpenAI uses: reasoning_effort = str (low/medium/high)
        """
        params = {}

        if enable_reasoning in ['low', 'medium', 'high']:
            params['reasoning_effort'] = enable_reasoning

        return params

    def supports_reasoning(self, model_name: str) -> bool:
        """OpenAI supports reasoning on o1/o3 models, but not audio models."""
        model_lower = model_name.lower()
        if 'audio' in model_lower:
            return False
        return True

    def uses_transcription_endpoint(self, model_name: str) -> bool:
        """OpenAI Whisper models use transcription endpoint."""
        model_lower = model_name.lower()
        return 'whisper' in model_lower
