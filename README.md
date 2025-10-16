# QuickScribe

Real-time AI-powered dictation application with multiple audio source options and intelligent text processing. Record audio with configurable triggers, transcribe using local models or cloud APIs, and automatically inject professionally formatted text into any application.

**⚠️ Privacy Notice:** All processing modes send data to remote AI models. Raw audio mode sends audio directly to the LLM. Transcription mode sends audio to transcription service, then sends text to LLM for formatting.

## Features

- **Audio Sources**
  - Raw microphone (default): Direct audio to LLM
  - Transcription: Audio → transcription model → text → LLM
- **LLM Providers**
  - Groq, Google Gemini, OpenAI, Anthropic, OpenRouter
- **Transcription Models** (when using transcription audio source)
  - HuggingFace Wav2Vec2 (local, phoneme-based)
  - OpenAI Whisper (cloud API)
  - Groq Whisper (cloud API)
  - VOSK (local, offline)
- **Text Processing**
  - Real-time streaming with incremental updates
  - Grammar correction, punctuation, technical term formatting
  - Conversation context across recordings
- **Input Control**
  - Keyboard triggers (configurable key)
  - POSIX signals (SIGUSR1/SIGUSR2)
- **Output**
  - macOS: Native keyboard injection via Accessibility API
  - Linux: xdotool with configurable keystroke rate

## Requirements

### Dependencies
```bash
pip install -r requirements.txt
```

### System Dependencies
**Linux**: `sudo apt-get install xdotool`

### Permissions
- Microphone access (all modes)
- Accessibility/input monitoring (keyboard triggers and text injection)
- **macOS**: System Settings → Privacy & Security → Accessibility

## Installation

1. **Clone and install dependencies:**
   ```bash
   git clone <repository-url>
   cd QuickScribe
   pip install -r requirements.txt
   ```

2. **Configure API keys:**
   ```bash
   # Create .env file with your API keys
   echo "GROQ_API_KEY=your_groq_key_here" > .env
   echo "GOOGLE_API_KEY=your_google_key_here" >> .env
   ```

## Configuration Options

### Core Arguments

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--model` | | None | Model in format `provider/model` (e.g., `groq/llama-3.3-70b-versatile`) |
| `--audio-source` | `-a` | `raw` | Audio source: `raw` (audio→LLM) or `transcribe`/`trans` (audio→transcription→LLM) |
| `--transcription-model` | `-T` | `huggingface/...` | Transcription model when using `-a transcribe` (format: `provider/model`) |

### Model Format

Both `--model` and `--transcription-model` use format: `provider/identifier`

**LLM providers**: `groq`, `gemini`, `openai`, `anthropic`, `openrouter`
**Transcription providers**: `huggingface`, `openai`, `groq`, `vosk`

### Other Options

| Option | Default | Description |
|--------|---------|-------------|
| `--trigger-key` | `alt_r` | Keyboard trigger key |
| `--no-trigger-key` | disabled | Use SIGUSR1/SIGUSR2 signals instead of keyboard |
| `--xdotool-hz` | None | Keystroke rate for xdotool (Linux) |
| `--enable-reasoning` | `low` | Reasoning level: `none`, `low`, `medium`, `high` |
| `--temperature` | `0.2` | LLM temperature (0.0-2.0) |
| `--debug` / `-D` | disabled | Debug output |

## Usage

### Interactive Mode
```bash
python dictate.py
```

### Specify Model
```bash
# Raw audio → LLM
python dictate.py --model groq/llama-3.3-70b-versatile

# Transcription → LLM
python dictate.py -a transcribe -T openai/whisper-1 --model anthropic/claude-3-5-sonnet-20241022
```

### Signal Control (background mode)
```bash
python dictate.py --model groq/llama-3.3-70b-versatile --no-trigger-key &
PID=$!
kill -USR1 $PID  # Start recording
kill -USR2 $PID  # Stop recording
```

## How It Works

1. Hold trigger key (or send SIGUSR1 signal)
2. Audio captured → processed (raw or transcribed) → sent to LLM
3. Text streamed back and injected into active application
4. Conversation context maintained across recordings

## Audio Sources Explained

### Raw Audio (`-a raw`, default)
Audio sent directly to LLM for transcription and formatting.

**When to use:** LLM supports audio input (Gemini, OpenAI, Anthropic)
**Note:** Groq LLMs do not support audio; use transcription mode

### Transcription Mode (`-a transcribe`)
Two-stage: audio → transcription model → text → LLM → formatted text

**When to use:**
- LLM lacks audio support (Groq)
- Lower cost (cheap transcription + expensive LLM)
- Local/offline transcription (VOSK, Wav2Vec2)

**Example:** "their are too errors hear" → transcription → "their are too errors hear" → LLM → "There are two errors here."

LLM corrects: homophones, grammar, punctuation, technical terms

### Transcription Models

**HuggingFace Wav2Vec2** (local, phoneme-based)
```bash
python dictate.py -a transcribe -T huggingface/facebook/wav2vec2-lv-60-espeak-cv-ft --model groq/llama-3.3-70b-versatile
```

**OpenAI Whisper** (cloud API)
```bash
python dictate.py -a transcribe -T openai/whisper-1 --model anthropic/claude-3-5-sonnet-20241022
```

**VOSK** (local, offline)
```bash
python dictate.py -a transcribe -T vosk/~/.vosk/model-en-us --model groq/llama-3.3-70b-versatile
```

## Troubleshooting

- **No microphone**: Check system permissions
- **macOS text injection fails**: Grant accessibility permissions (System Settings → Privacy & Security)
- **Linux text injection fails**: Install xdotool
- **High latency**: Set `--enable-reasoning none`, lower `--temperature`
