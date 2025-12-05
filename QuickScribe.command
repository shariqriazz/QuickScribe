#!/bin/bash
cd /Users/shariqriaz/projects/QuickScribe
source .env
export OPENROUTER_API_KEY QUICKSCRIBE_MODEL QUICKSCRIBE_TRIGGER_KEY QUICKSCRIBE_ONCE QUICKSCRIBE_DEBUG QUICKSCRIBE_REASONING QUICKSCRIBE_MAX_TOKENS
/opt/homebrew/Caskroom/miniconda/base/bin/python3 dictate.py
