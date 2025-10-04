"""
Tests for mode switching mechanics in TranscriptionService.
"""
import unittest
import re
from unittest.mock import Mock, MagicMock, patch
from transcription_service import TranscriptionService


class MockConfig:
    """Mock configuration for testing."""
    def __init__(self):
        self.mode = 'dictate'
        self.debug_enabled = False
        self.reset_state_each_response = False
        self.xml_stream_debug = False


class TestModeChangeHandler(unittest.TestCase):
    """Test _handle_mode_change mechanics."""

    def setUp(self):
        self.config = MockConfig()
        with patch('transcription_service.InstructionComposer'):
            self.service = TranscriptionService(self.config)

    def test_handle_mode_change_updates_config(self):
        """Verify _handle_mode_change updates config.mode."""
        self.service.composer.get_available_modes = Mock(return_value=['dictate', 'edit', 'shell'])

        initial_mode = self.config.mode
        self.assertEqual(initial_mode, 'dictate')

        result = self.service._handle_mode_change('edit')

        self.assertTrue(result)
        self.assertEqual(self.config.mode, 'edit')

    def test_handle_mode_change_resets_state(self):
        """Verify all state is cleared on mode change to different mode."""
        self.service.composer.get_available_modes = Mock(return_value=['dictate', 'edit', 'shell'])

        # Set up streaming state and processor state
        self.service.streaming_buffer = "test"
        self.service.last_update_position = 5
        self.service.update_seen = True
        self.service.processor.current_words = {10: "old ", 20: "content"}

        self.service._handle_mode_change('shell')

        # All state should be cleared (same as <reset>)
        self.assertEqual(self.service.streaming_buffer, "")
        self.assertEqual(self.service.last_update_position, 0)
        self.assertFalse(self.service.update_seen)
        self.assertEqual(self.service.processor.current_words, {})

    def test_handle_mode_change_invalid_mode(self):
        """Verify rejection of modes not in available_modes."""
        self.service.composer.get_available_modes = Mock(return_value=['dictate', 'edit', 'shell'])

        result = self.service._handle_mode_change('invalid_mode')

        self.assertFalse(result)
        # Mode should not have changed
        self.assertEqual(self.config.mode, 'dictate')

    def test_handle_mode_change_no_composer(self):
        """Verify mode change fails gracefully without composer."""
        self.service.composer = None

        result = self.service._handle_mode_change('edit')

        self.assertFalse(result)
        self.assertEqual(self.config.mode, 'dictate')

    def test_handle_mode_change_same_mode_no_reset(self):
        """Verify switching to same mode doesn't clear state."""
        self.service.composer.get_available_modes = Mock(return_value=['dictate', 'edit', 'shell'])

        # Set up streaming state
        self.service.streaming_buffer = "test"
        self.service.last_update_position = 5
        self.service.update_seen = True

        # Switch to same mode
        result = self.service._handle_mode_change('dictate')

        self.assertTrue(result)
        # State should NOT be cleared
        self.assertEqual(self.service.streaming_buffer, "test")
        self.assertEqual(self.service.last_update_position, 5)
        self.assertTrue(self.service.update_seen)


class TestModeExtractionFromXML(unittest.TestCase):
    """Test regex extraction of mode from XML."""

    def test_mode_extraction_from_xml(self):
        """Test extraction of mode value from <mode> tags."""
        test_cases = [
            ('<mode>edit</mode>', 'edit'),
            ('<mode>shell</mode>', 'shell'),
            ('<mode>dictate</mode>', 'dictate'),
            ('<tx>test</tx><mode>edit</mode><update></update>', 'edit'),
        ]

        for xml, expected_mode in test_cases:
            match = re.search(r'<mode>(\w+)</mode>', xml)
            self.assertIsNotNone(match, f"Failed to match in: {xml}")
            self.assertEqual(match.group(1), expected_mode)

    def test_no_mode_in_xml(self):
        """Test that extraction returns None when no mode tag present."""
        xml = '<tx>test</tx><update></update>'
        match = re.search(r'<mode>(\w+)</mode>', xml)
        self.assertIsNone(match)


class TestModeChangeInStreaming(unittest.TestCase):
    """Test mode change detection in streaming."""

    def setUp(self):
        self.config = MockConfig()
        with patch('transcription_service.InstructionComposer'):
            self.service = TranscriptionService(self.config)
        self.service.composer.get_available_modes = Mock(return_value=['dictate', 'edit', 'shell'])

    def test_mode_change_clears_streaming_buffer(self):
        """Verify streaming buffer is cleared on mode change."""
        self.service.streaming_buffer = "some content"
        self.service.last_update_position = 10
        self.service.update_seen = True

        # Simulate mode change chunk
        self.service.process_streaming_chunk('<mode>edit</mode>')

        # Buffer should be cleared
        self.assertEqual(self.service.streaming_buffer, "")
        self.assertEqual(self.service.last_update_position, 0)
        self.assertFalse(self.service.update_seen)

    def test_mode_change_in_combined_buffer(self):
        """Test mode detection when tag spans buffer and chunk."""
        # This test verifies the regex can find the tag across buffer boundaries
        # However, the actual detection happens on the combined string
        combined = "<mode>edit</mode>"
        match = re.search(r'<mode>(\w+)</mode>', combined)

        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), 'edit')

        # Test that streaming detection would work if properly buffered
        self.service.streaming_buffer = "<mo"
        chunk = "de>edit</mode>"
        combined_buffer = self.service.streaming_buffer + chunk

        match = re.search(r'<mode>(\w+)</mode>', combined_buffer)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), 'edit')


class TestModeChangeInBatchProcessing(unittest.TestCase):
    """Test mode change detection in batch processing."""

    def setUp(self):
        self.config = MockConfig()
        with patch('transcription_service.InstructionComposer'):
            self.service = TranscriptionService(self.config)
        self.service.composer.get_available_modes = Mock(return_value=['dictate', 'edit', 'shell'])

    def test_mode_change_skips_content_processing(self):
        """Verify content processing is skipped when mode changes."""
        # Mock the processor to track if it's called
        self.service.processor.process_chunk = Mock()
        self.service.processor.end_stream = Mock()

        xml = '<x><tx>mode edit</tx><int>mode edit</int><mode>edit</mode><update></update></x>'

        self.service.process_xml_transcription(xml)

        # Mode should have changed
        self.assertEqual(self.config.mode, 'edit')

        # Content processing should have been skipped (early return)
        self.service.processor.process_chunk.assert_not_called()
        self.service.processor.end_stream.assert_not_called()

    def test_normal_processing_without_mode_change(self):
        """Verify normal processing continues when no mode change."""
        self.service.processor.process_chunk = Mock()
        self.service.processor.end_stream = Mock()

        xml = '<x><tx>test content</tx><int>test content</int><update><10>test content</10></update></x>'

        self.service.process_xml_transcription(xml)

        # Normal processing should occur
        self.service.processor.process_chunk.assert_called()
        self.service.processor.end_stream.assert_called()


class TestStateResetMechanics(unittest.TestCase):
    """Test state reset mechanics on mode change."""

    def setUp(self):
        self.config = MockConfig()
        with patch('transcription_service.InstructionComposer'):
            self.service = TranscriptionService(self.config)
        self.service.composer.get_available_modes = Mock(return_value=['dictate', 'edit', 'shell'])

    def test_mode_change_clears_processor_state(self):
        """Verify processor state is cleared on mode change to different mode."""
        # Set up state
        self.service.processor.current_words = {10: "test ", 20: "content"}

        # Mode change to different mode should clear processor state (same as <reset>)
        self.service._handle_mode_change('edit')

        # Processor state should be cleared
        self.assertEqual(self.service.processor.current_words, {})


if __name__ == '__main__':
    unittest.main()
