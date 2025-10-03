"""
Instruction composer for loading and combining instruction files.
"""
import re
from pathlib import Path
from importlib.resources import files
from typing import Optional


class InstructionComposer:
    """Composes system instructions from modular files."""

    def __init__(self):
        self._cache = {}

    def _load_file(self, file_path: Path) -> Optional[str]:
        """Load a file from filesystem."""
        try:
            return file_path.read_text()
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"Warning: Failed to load file '{file_path}': {e}")
            return None

    def _resolve_imports(self, content: str, file_path: Path) -> str:
        """Recursively resolve @import statements using standard filesystem semantics."""
        # Get directory of the current file
        current_dir = file_path.parent

        def replace_import(match):
            import_path = match.group(1)

            # Resolve path using standard filesystem semantics
            if import_path.startswith('/'):
                # Absolute path from filesystem root
                resolved_path = Path(import_path)
            else:
                # Relative to current file's directory
                resolved_path = (current_dir / import_path).resolve()

            # Load and recursively resolve
            imported = self._load_file(resolved_path)
            if imported is None:
                raise RuntimeError(f"Import not found: @{import_path}")

            # Recursively resolve imports in imported file
            return self._resolve_imports(imported, resolved_path)

        # Replace all @import lines
        return re.sub(r'^@(.+)$', replace_import, content, flags=re.MULTILINE)

    def _load(self, path: str) -> Optional[str]:
        """Load instruction file with caching and import resolution."""
        if path in self._cache:
            return self._cache[path]

        try:
            instruction_files = files('instructions')
            # Get the actual filesystem path if possible
            if hasattr(instruction_files, '_path'):
                base_path = Path(instruction_files._path)
            else:
                # Fallback for package resources
                base_path = Path('instructions')

            file_path = base_path / path
            content = (instruction_files / path).read_text()

            # Resolve imports with standard filesystem semantics
            content = self._resolve_imports(content, file_path)
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
