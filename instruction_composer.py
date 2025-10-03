"""
Instruction composer for loading and combining instruction files.
"""
from importlib.resources import files
from typing import Optional


class InstructionComposer:
    """Composes system instructions from modular files."""

    def __init__(self):
        self._cache = {}

    def _load(self, path: str) -> Optional[str]:
        """Load instruction file with caching."""
        if path in self._cache:
            return self._cache[path]

        try:
            instruction_files = files('instructions')
            content = (instruction_files / path).read_text()
            self._cache[path] = content
            return content
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"Warning: Failed to load instruction file '{path}': {e}")
            return None

    def compose(self, mode: str, audio_source: Optional[str] = None, provider: Optional[str] = None) -> str:
        """
        Compose instructions from core, mode, audio source, and provider files.

        Args:
            mode: Operation mode (dictate, edit, etc.)
            audio_source: Optional audio source name (microphone, wav2vec2, etc.)
            provider: Optional provider name (anthropic, openai, gemini, etc.)

        Returns:
            Composed instruction string
        """
        parts = []

        # Load core instructions (required)
        core = self._load('core.md')
        if core is None:
            raise RuntimeError("Core instructions not found")
        parts.append(core)

        # Load mode instructions (required)
        mode_content = self._load(f'modes/{mode}.md')
        if mode_content is None:
            raise RuntimeError(f"Mode instructions not found for '{mode}'")
        parts.append(mode_content)

        # Load audio source instructions (optional)
        if audio_source:
            audio_content = self._load(f'audio_sources/{audio_source}.md')
            if audio_content is not None:
                parts.append(audio_content)

        # Load provider instructions (optional)
        if provider:
            provider_content = self._load(f'providers/{provider}.md')
            if provider_content is not None:
                parts.append(provider_content)

        return '\n\n'.join(parts)
