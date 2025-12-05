"""
Test to verify LiteLLM streaming response has close() method.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_litellm_response_type():
    """Verify the LiteLLM response object type and available methods."""
    try:
        import litellm
    except ImportError:
        print("litellm not installed, skipping test")
        return

    print("Creating mock streaming response to inspect type...")

    # We need to actually get a response object to inspect it
    # Use a minimal model that should work
    try:
        # This will fail auth but we just need the object type
        response = litellm.completion(
            model='gpt-3.5-turbo',
            messages=[{'role': 'user', 'content': 'test'}],
            stream=True,
            api_key='test-key-for-type-inspection'
        )

        print(f"Response type: {type(response)}")
        print(f"Response class: {response.__class__.__name__}")
        print(f"Response module: {response.__class__.__module__}")
        print(f"Has close method: {hasattr(response, 'close')}")

        if hasattr(response, 'close'):
            print(f"close method type: {type(response.close)}")
            print(f"close is callable: {callable(response.close)}")

        # List all public methods
        methods = [m for m in dir(response) if not m.startswith('_')]
        print(f"\nAvailable public methods: {methods}")

        # Check iterator protocol
        print(f"\nHas __iter__: {hasattr(response, '__iter__')}")
        print(f"Has __next__: {hasattr(response, '__next__')}")

    except Exception as e:
        print(f"Error creating response (expected): {type(e).__name__}: {e}")
        print("This is expected if auth fails, but we may have gotten type info")

if __name__ == '__main__':
    test_litellm_response_type()
