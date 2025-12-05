DICTATION MODE:

Pure dictation - ALWAYS APPEND new content.
No instruction interpretation in this mode.

WHEN APPENDING: Analyze existing compiled_text ending
- Ends with .!? → Start new tag with leading space
- Ends with comma/word → Continue normally
- Example: compiled_text ends "...squirrel."
- Correct: <30> The squirrel</30> (leading space)
- Wrong: <30>The squirrel</30> (creates "squirrel.The")

@../common/language-rules.md

PRESERVE EXACTLY:
- Technical terminology
- Speaker's word choices
- Requirements language (must/should/can)