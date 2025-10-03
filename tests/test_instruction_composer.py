"""
Tests for InstructionComposer - static cache and mode discovery mechanics.
"""
import unittest
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from instruction_composer import InstructionComposer


class TestStaticCache(unittest.TestCase):
    """Test static cache sharing across instances."""

    def test_static_cache_sharing(self):
        """Verify multiple instances share the same cache."""
        composer1 = InstructionComposer()
        composer2 = InstructionComposer()

        # Both instances should reference the same cache
        self.assertIs(composer1._cache, composer2._cache)
        self.assertIs(composer1._cache_mtimes, composer2._cache_mtimes)

    def test_cache_persistence_across_instances(self):
        """Verify cache persists across instance creation."""
        # Clear cache for clean test
        InstructionComposer._cache.clear()
        InstructionComposer._cache_mtimes.clear()

        composer1 = InstructionComposer()

        # Mock the file reading to track calls
        with patch('instruction_composer.Path.stat') as mock_stat, \
             patch('instruction_composer.Path.read_text') as mock_read:

            mock_stat.return_value = MagicMock(st_mtime=1000.0)
            mock_read.return_value = "test content"

            # First load
            with patch('instruction_composer.files') as mock_files:
                mock_files.return_value._path = '/fake/instructions'
                mock_files.return_value.__truediv__.return_value.read_text.return_value = "test content"
                result1 = composer1._load('test.md')

            read_count_first = mock_read.call_count

            # Create new instance and load same file
            composer2 = InstructionComposer()
            with patch('instruction_composer.files') as mock_files:
                mock_files.return_value._path = '/fake/instructions'
                result2 = composer2._load('test.md')

            # Second instance should use cache, not read again
            self.assertEqual(result1, result2)
            self.assertEqual(mock_read.call_count, read_count_first)

    def test_mtime_cache_invalidation(self):
        """Verify cache updates when file mtime changes."""
        InstructionComposer._cache.clear()
        InstructionComposer._cache_mtimes.clear()

        composer = InstructionComposer()

        with patch('instruction_composer.Path.stat') as mock_stat, \
             patch('instruction_composer.files') as mock_files:

            mock_files.return_value._path = '/fake/instructions'

            # First load with mtime=1000
            mock_stat.return_value = MagicMock(st_mtime=1000.0)
            mock_files.return_value.__truediv__.return_value.read_text.return_value = "original content"

            result1 = composer._load('test.md')
            self.assertEqual(result1, "original content")

            # Second load with same mtime (should use cache)
            mock_files.return_value.__truediv__.return_value.read_text.return_value = "should not see this"
            result2 = composer._load('test.md')
            self.assertEqual(result2, "original content")

            # Third load with different mtime (should reload)
            mock_stat.return_value = MagicMock(st_mtime=2000.0)
            mock_files.return_value.__truediv__.return_value.read_text.return_value = "updated content"
            result3 = composer._load('test.md')
            self.assertEqual(result3, "updated content")


class TestModeDiscovery(unittest.TestCase):
    """Test dynamic mode discovery from filesystem."""

    def test_get_available_modes(self):
        """Verify mode discovery from modes/ directory."""
        composer = InstructionComposer()

        with patch('instruction_composer.files') as mock_files:
            # Mock modes_path and file iteration
            mock_modes_path = MagicMock()

            # Create file-like objects with name attribute
            class MockFile:
                def __init__(self, name):
                    self.name = name

            mock_modes_path.iterdir.return_value = [
                MockFile('dictate.md'),
                MockFile('edit.md'),
                MockFile('shell.md'),
                MockFile('README.txt')  # Should be ignored
            ]

            mock_files.return_value.__truediv__.return_value = mock_modes_path
            mock_files.return_value._path = '/fake/instructions'

            # Mock the stat call on the base_path
            mock_stat = MagicMock()
            mock_stat.st_mtime = 1000.0

            with patch('pathlib.Path.stat', return_value=mock_stat):
                modes = composer.get_available_modes()

            self.assertEqual(sorted(modes), ['dictate', 'edit', 'shell'])

    def test_mode_discovery_error_propagates(self):
        """Test that discovery errors propagate instead of falling back."""
        composer = InstructionComposer()

        with patch('instruction_composer.files', side_effect=Exception("Filesystem error")):
            with self.assertRaises(Exception):
                composer.get_available_modes()


class TestTemplateInjection(unittest.TestCase):
    """Test template variable replacement."""

    def test_template_injection(self):
        """Verify {{AVAILABLE_MODES}} is replaced correctly."""
        InstructionComposer._cache.clear()
        InstructionComposer._cache_mtimes.clear()

        composer = InstructionComposer()

        with patch.object(composer, 'get_available_modes', return_value=['dictate', 'edit', 'shell']), \
             patch.object(composer, '_load') as mock_load:

            mock_load.side_effect = lambda path: {
                'core.md': 'Current: {{CURRENT_MODE}}, Available: {{AVAILABLE_MODES}}',
                'modes/dictate.md': 'Dictate mode content'
            }.get(path)

            result = composer.compose('dictate')

            # Should show current mode
            self.assertIn('Current: dictate', result)
            # Should show other modes (not current)
            self.assertIn('Available: edit|shell', result)
            # Should not show dictate in available (it's current)
            self.assertNotIn('Available: dictate', result)
            self.assertNotIn('{{AVAILABLE_MODES}}', result)
            self.assertNotIn('{{CURRENT_MODE}}', result)


class TestComposeDifferentModes(unittest.TestCase):
    """Test composition with different modes."""

    def test_compose_with_different_modes(self):
        """Verify composition returns different content for different modes."""
        InstructionComposer._cache.clear()
        InstructionComposer._cache_mtimes.clear()

        composer = InstructionComposer()

        with patch.object(composer, 'get_available_modes', return_value=['dictate', 'edit']), \
             patch.object(composer, '_load') as mock_load:

            mock_load.side_effect = lambda path: {
                'core.md': 'Core instructions {{AVAILABLE_MODES}}',
                'modes/dictate.md': 'DICTATE MODE',
                'modes/edit.md': 'EDIT MODE'
            }.get(path)

            result_dictate = composer.compose('dictate')
            result_edit = composer.compose('edit')

            self.assertIn('DICTATE MODE', result_dictate)
            self.assertNotIn('EDIT MODE', result_dictate)

            self.assertIn('EDIT MODE', result_edit)
            self.assertNotIn('DICTATE MODE', result_edit)


if __name__ == '__main__':
    unittest.main()
