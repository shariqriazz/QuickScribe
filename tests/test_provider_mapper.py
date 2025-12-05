"""
Test provider mapper integration.
"""
from providers.mapper_factory import MapperFactory
from providers.base_provider import BaseProvider
from config_manager import ConfigManager


def test_openrouter_mapper_token_budget_precedence():
    """Test OpenRouter mapper: token budget takes precedence over effort."""
    mapper = MapperFactory.get_mapper('openrouter')

    params = mapper.map_reasoning_params('medium', 2048)
    assert 'reasoning' in params
    assert params['reasoning'].get('max_tokens') == 2048
    assert 'effort' not in params['reasoning'], "Both effort and max_tokens cannot be set"


def test_openrouter_mapper_effort_only():
    """Test OpenRouter mapper: effort only when no budget specified."""
    mapper = MapperFactory.get_mapper('openrouter')

    params = mapper.map_reasoning_params('low', 0)
    assert 'reasoning' in params
    assert params['reasoning'].get('effort') == 'low'
    assert 'max_tokens' not in params['reasoning']


def test_anthropic_mapper():
    """Test Anthropic mapper instantiation and parameter mapping."""
    mapper = MapperFactory.get_mapper('anthropic')
    params = mapper.map_reasoning_params('low', 1024)

    assert 'thinking' in params
    assert params['thinking']['type'] == 'enabled'
    assert params['thinking']['budget_tokens'] == 1024


def test_gemini_mapper():
    """Test Gemini mapper uses default thinking format."""
    mapper = MapperFactory.get_mapper('gemini')
    params = mapper.map_reasoning_params('high', 4096)

    assert 'thinking' in params
    assert params['thinking']['type'] == 'enabled'
    assert params['thinking']['budget_tokens'] == 4096


def test_base_provider_integration():
    """Test BaseProvider uses mapper correctly."""
    config = ConfigManager()
    config.model_id = 'openrouter/google/gemini-2.5-pro'
    config.enable_reasoning = 'medium'
    config.thinking_budget = 2048
    config.litellm_debug = False
    config.api_key = None
    config.audio_source = 'raw'
    config.mode = 'dictate'

    class MockAudio:
        pass

    provider = BaseProvider(config, MockAudio())

    assert provider.provider == 'openrouter'
    assert provider.mapper is not None


def test_routing_provider_extraction():
    """Test @routing_provider suffix handling in model_id."""
    config = ConfigManager()
    config.model_id = 'openrouter/google/gemini-2.5-flash@vertex'
    config.enable_reasoning = 'low'
    config.thinking_budget = 0
    config.litellm_debug = False
    config.api_key = None
    config.audio_source = 'raw'
    config.mode = 'dictate'

    class MockAudio:
        pass

    provider = BaseProvider(config, MockAudio())

    assert provider.provider == 'openrouter'
    assert provider.mapper is not None
    assert config.model_id == 'openrouter/google/gemini-2.5-flash@vertex'
