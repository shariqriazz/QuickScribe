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
    sys.exit(main())