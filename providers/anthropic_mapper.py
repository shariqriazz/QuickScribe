"""
Anthropic-specific configuration mapper.
Maps generic configuration to Anthropic API format.
"""
from typing import Dict, Any
from .provider_config_mapper import ProviderConfigMapper


class AnthropicMapper(ProviderConfigMapper):
    """Configuration mapper for Anthropic provider."""

    def map_reasoning_params(self, enable_reasoning: str, thinking_budget: int) -> Dict[str, Any]:
        """
        Map reasoning configuration to Anthropic's thinking format.

        Anthropic uses: thinking = {type: str, budget_tokens: int}
        """
        params = {}

        if enable_reasoning == 'none':
            params['thinking'] = {'type': 'disabled'}
        elif thinking_budget > 0:
            params['thinking'] = {
                'type': 'enabled',
                'budget_tokens': thinking_budget
            }

        return params

    def supports_reasoning(self, model_name: str) -> bool:
        """Anthropic supports reasoning via thinking parameter."""
        return True
