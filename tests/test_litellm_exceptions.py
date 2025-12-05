"""Test to verify litellm exception classes exist."""
import sys


def test_internal_server_error_exists():
    """Verify InternalServerError exception exists in litellm.exceptions."""
    try:
        from litellm import exceptions
        assert hasattr(exceptions, 'InternalServerError')
        print(f"✓ InternalServerError exists")
        print(f"Available exceptions: {[attr for attr in dir(exceptions) if 'Error' in attr or 'Exception' in attr]}")
    except ImportError as e:
        print(f"✗ Failed to import litellm: {e}")
        sys.exit(1)
    except AssertionError:
        print(f"✗ InternalServerError not found in litellm.exceptions")
        print(f"Available: {dir(exceptions)}")
        sys.exit(1)


if __name__ == '__main__':
    test_internal_server_error_exists()
