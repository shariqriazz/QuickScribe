"""Test pr_log functionality."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lib.pr_log import (
    pr_emerg, pr_alert, pr_crit, pr_err, pr_warn, pr_notice, pr_info, pr_debug,
    get_streaming_handler, set_log_level,
    PR_EMERG, PR_ALERT, PR_CRIT, PR_ERR, PR_WARN, PR_NOTICE, PR_INFO, PR_DEBUG
)


def test_basic_logging():
    """Test basic pr_* functions display correctly."""
    print("Testing basic logging functions:")
    print("-" * 60)

    pr_emerg("System unusable test")
    pr_alert("Action required test")
    pr_crit("Critical condition test")
    pr_err("Error condition test")
    pr_warn("Warning condition test")
    pr_notice("Notice test")
    pr_info("Info test")
    pr_debug("Debug test")

    print("-" * 60)


def test_streaming_with_queueing():
    """Test that non-critical messages queue during streaming."""
    print("\nTesting streaming with message queueing:")
    print("-" * 60)

    pr_info("Before streaming starts")

    with get_streaming_handler() as stream:
        stream.write("Streaming: ")
        pr_info("This should queue (info)")
        pr_debug("This should queue (debug)")
        pr_warn("This should queue (warning)")
        stream.write("content ")
        pr_err("This should display immediately (error)")
        stream.write("here")

    print("-" * 60)
    print("After streaming, queued messages should appear above")


def test_streaming_cleanup():
    """Test that streaming handler cleans up when going out of scope."""
    print("\nTesting streaming cleanup on scope exit:")
    print("-" * 60)

    def create_handler():
        h = get_streaming_handler()
        h.__enter__()
        h.write("Test streaming")
        pr_info("Queued message")
        return h

    handler = create_handler()
    handler.__exit__(None, None, None)

    print("-" * 60)


def test_log_level_filtering():
    """Test that log level filtering works correctly."""
    print("\nTesting log level filtering:")
    print("-" * 60)

    print("Setting log level to PR_WARN (4) - should only show WARN and above:")
    set_log_level(PR_WARN)

    pr_err("Should show (ERROR)")
    pr_warn("Should show (WARNING)")
    pr_notice("Should NOT show (NOTICE)")
    pr_info("Should NOT show (INFO)")
    pr_debug("Should NOT show (DEBUG)")

    print("\nResetting to PR_INFO for remaining tests")
    set_log_level(PR_INFO)

    print("-" * 60)


if __name__ == '__main__':
    test_basic_logging()
    test_streaming_with_queueing()
    test_streaming_cleanup()
    test_log_level_filtering()

    print("\nAll tests completed.")
