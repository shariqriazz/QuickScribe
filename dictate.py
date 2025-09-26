"""
Main dictation application entry point.
"""
import sys
from dictation_app import DictationApp


def main():
    """Main entry point for the dictation application."""
    app = DictationApp()
    return app.run()


if __name__ == "__main__":
    # Configure gRPC environment variables before any imports
    import os
    os.environ['GRPC_VERBOSITY'] = 'ERROR'
    os.environ['GRPC_ENABLE_FORK_SUPPORT'] = '0'

    sys.exit(main())