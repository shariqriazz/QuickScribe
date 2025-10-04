"""Tests for signal mode configuration."""
import pytest
import sys
from unittest.mock import Mock, patch
from config_manager import ConfigManager


class TestSignalModeConfiguration:
    """Test signal mode configuration defaults and argument parsing."""

    def test_default_signal_modes(self):
        """Verify default signal modes are set correctly."""
        config = ConfigManager()
        assert config.sigusr1_mode == "dictate"
        assert config.sigusr2_mode == "shell"

    def test_sigusr1_argument_parsing(self):
        """Verify --sigusr1 argument sets mode correctly."""
        sys.argv = ['test', '--sigusr1', 'edit']
        config = ConfigManager()
        config.parse_configuration()
        assert config.sigusr1_mode == "edit"

    def test_sigusr2_argument_parsing(self):
        """Verify --sigusr2 argument sets mode correctly."""
        sys.argv = ['test', '--sigusr2', 'dictate']
        config = ConfigManager()
        config.parse_configuration()
        assert config.sigusr2_mode == "dictate"

    def test_both_signal_arguments(self):
        """Verify both signal mode arguments work together."""
        sys.argv = ['test', '--sigusr1', 'shell', '--sigusr2', 'edit']
        config = ConfigManager()
        config.parse_configuration()
        assert config.sigusr1_mode == "shell"
        assert config.sigusr2_mode == "edit"

    def test_signal_modes_with_no_trigger_key(self):
        """Verify signal modes work with --no-trigger-key."""
        sys.argv = ['test', '--no-trigger-key', '--sigusr1', 'edit', '--sigusr2', 'shell']
        config = ConfigManager()
        config.parse_configuration()
        assert config.trigger_key_name == "none"
        assert config.sigusr1_mode == "edit"
        assert config.sigusr2_mode == "shell"
