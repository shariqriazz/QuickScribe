# QuickScribe

Real-time AI-powered dictation application with multiple audio source options and intelligent text processing. Record audio with configurable triggers, transcribe using local models or cloud APIs, and automatically inject professionally formatted text into any application.

## Features

- **Multi-Source Audio Processing**
  - Raw microphone recording (default)
  - VOSK local speech recognition
  - Wav2Vec2 phoneme recognition with Hugging Face models
- **AI-Powered Transcription**
  - Groq (Whisper models): `distil-whisper-large-v3-en`, `whisper-large-v3-turbo`, `whisper-large-v3`
  - Google Gemini: `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-2.0-flash`, `gemini-2.0-flash-lite`
- **Intelligent Text Processing**
  - Real-time XML-based streaming with live updates
  - Professional copy editing with minimal intervention
  - Context-aware command detection and conversation continuity
  - Technical term formatting with backticks and proper quotation handling
- **Flexible Input Methods**
  - Configurable keyboard triggers (any key combination)
  - POSIX signal control (SIGUSR1/SIGUSR2)
  - Cross-platform compatibility (macOS, Linux, Windows)
- **Advanced Output Control**
  - Native macOS keyboard injection with accessibility integration
  - Linux xdotool support with configurable keystroke rates
  - Mock mode for testing and development

## Requirements

### Dependencies
```bash
pip install -r requirements.txt
```

### System Dependencies
- **Linux**: `sudo apt-get install xdotool` (for --use-xdotool option)

### System Permissions
- **Microphone Access**: Required for all audio recording
- **Accessibility/Input Monitoring**: Required for keyboard triggers and text injection
- **macOS**: Grant accessibility permissions in System Settings → Privacy & Security → Accessibility

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

| Option | Short | Choices/Type | Default | Description |
|--------|-------|-------------|---------|-------------|
| `--provider` | | `groq`, `gemini` | None | Transcription provider (required in non-interactive mode) |
| `--model` | | String | None | Specific model ID for chosen provider (required in non-interactive mode) |
| `--audio-source` | `-a` | `raw`, `vosk`, `phoneme`, `wav2vec` | `raw` | Audio source type |

### Audio Source Configuration

| Audio Source | Required Options | Optional Options | Description |
|-------------|------------------|------------------|-------------|
| `raw` | None | `--sample-rate`, `--channels` | Direct microphone recording |
| `vosk` | `--vosk-model` | `--vosk-lgraph` | Local VOSK speech recognition |
| `phoneme`/`wav2vec` | None | `--wav2vec2-model` | Wav2Vec2 phoneme recognition |

### Audio Processing

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--sample-rate` | Integer | `16000` | Audio sample rate in Hz |
| `--channels` | Integer | `1` | Number of audio channels (1=mono, 2=stereo) |
| `--vosk-model` | Path | None | Path to VOSK model directory |
| `--vosk-lgraph` | Path | None | Path to VOSK L-graph file for grammar constraints |
| `--wav2vec2-model` | String | `facebook/wav2vec2-lv-60-espeak-cv-ft` | Wav2Vec2 model path or Hugging Face model ID |

### Input Control

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--trigger-key` | String | `alt_r` | Key to trigger recording (`alt_r`, `ctrl_l`, `f19`, `a`, etc.) |
| `--no-trigger-key` | Flag | False | Disable keyboard trigger; use SIGUSR1/SIGUSR2 signals |
| `--language` | String | None | Language code for Groq transcription (`en`, `es`, etc.) |

### Output Control

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--use-xdotool` | Flag | False | Use xdotool for text injection (Linux only) |
| `--xdotool-hz`, `--xdotool-cps` | Float | None | Xdotool keystroke rate in Hz/CPS |

### AI Model Performance

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable-reasoning` | Flag | False | Enable chain-of-thought reasoning (increases latency) |
| `--temperature` | Float | `0.2` | Response randomness (0.0-2.0, lower = more focused) |
| `--max-tokens` | Integer | None | Maximum response length (None = provider default) |
| `--top-p` | Float | `0.9` | Nucleus sampling parameter (0.0-1.0) |

### Development & Debugging

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--debug` | `-D` | Flag | False | Enable debug output and XML processing details |

## Usage Examples

### Interactive Mode
```bash
# Auto-detect API keys and select provider/model interactively
python dictate.py

# With custom trigger key
python dictate.py --trigger-key f19
```

### Command-Line Mode

#### Basic Usage
```bash
# Groq with Whisper
python dictate.py --provider groq --model whisper-large-v3

# Gemini with custom trigger
python dictate.py --provider gemini --model gemini-2.5-flash --trigger-key ctrl_r

# With language specification (Groq only)
python dictate.py --provider groq --model whisper-large-v3 --language es
```

#### Audio Source Selection
```bash
# Default raw microphone
python dictate.py --provider groq --model whisper-large-v3

# VOSK local recognition
python dictate.py -a vosk --vosk-model ~/.vosk/model-en-us --provider groq --model whisper-large-v3

# Wav2Vec2 phoneme recognition (default model)
python dictate.py -a phoneme --provider groq --model whisper-large-v3

# Wav2Vec2 with custom model
python dictate.py -a wav2vec --wav2vec2-model facebook/wav2vec2-large-lv60-timit --provider groq --model whisper-large-v3
```

#### Advanced Configuration
```bash
# High-performance setup with xdotool
python dictate.py --provider groq --model whisper-large-v3-turbo \
  --use-xdotool --xdotool-hz 250 \
  --temperature 0.1 --top-p 0.95

# VOSK with grammar constraints and signal control
python dictate.py -a vosk \
  --vosk-model ~/.vosk/model-en-us \
  --vosk-lgraph ~/.vosk/grammar.txt \
  --no-trigger-key --provider groq --model whisper-large-v3

# Development mode with debug output
python dictate.py --provider gemini --model gemini-2.0-flash \
  --debug --temperature 0.0
```

#### Production Deployment
```bash
# Background process with signal control
python dictate.py --provider groq --model distil-whisper-large-v3-en \
  --no-trigger-key --use-xdotool &
PID=$!

# Control via signals
kill -USR1 $PID  # Start recording
kill -USR2 $PID  # Stop recording
kill $PID        # Shutdown
```

## Workflow

1. **Startup**: Configure provider, model, and audio source
2. **Ready State**: Shows trigger key or signal instructions
3. **Recording**: Hold trigger key or send SIGUSR1 signal
4. **Processing**: Audio transcribed and processed through AI model
5. **Output**: Professional text automatically injected into active application
6. **Continuation**: Ready for next recording with conversation context maintained

## Audio Source Details

### Raw Microphone (`--audio-source raw`)
- **Description**: Direct microphone recording with real-time audio capture
- **Use Case**: Standard dictation with cloud AI processing
- **Requirements**: System microphone access
- **Performance**: Lowest latency, highest quality for AI transcription

### VOSK Local Recognition (`--audio-source vosk`)
- **Description**: Local speech-to-text using VOSK models
- **Use Case**: Privacy-sensitive environments, offline operation
- **Requirements**: VOSK models downloaded locally
- **Model Format**: Pre-trained VOSK models (download from vosk-api.org)
- **Grammar Support**: Optional L-graph files for constrained recognition
- **Performance**: No cloud dependency, consistent latency

### Wav2Vec2 Phoneme Recognition (`--audio-source phoneme`/`wav2vec`)
- **Description**: Phoneme-level transcription using Wav2Vec2 models
- **Use Case**: Technical dictation, pronunciation analysis
- **Requirements**: PyTorch, transformers, Hugging Face models
- **Model Support**: Any Wav2Vec2-CTC model from Hugging Face
- **Output**: Phoneme sequences processed by AI for final text
- **Performance**: Specialized for technical/pronunciation work

## Technical Features

### XML Stream Processing
- Real-time XML tag processing with incremental updates
- Word-level ID tracking for precise editing and continuation
- Context-aware conversation state management
- Professional copy editing with minimal intervention

### Cross-Platform Text Injection
- **macOS**: Native Accessibility API integration with permission detection
- **Linux**: Xdotool integration with configurable keystroke rates
- **Testing**: Mock injection for development and CI/CD

### Model Performance Optimization
- Streaming responses for real-time feedback
- Configurable temperature and sampling parameters
- Optional reasoning chains for complex transcription tasks
- Provider-specific optimization (Groq vs Gemini)

## Troubleshooting

### Audio Issues
- **No microphone access**: Check system permissions and default audio device
- **Poor audio quality**: Adjust `--sample-rate` (try 22050 or 44100)
- **VOSK model errors**: Verify model path and compatibility with sample rate

### Text Injection Issues
- **macOS**: Grant accessibility permissions to Terminal/Python in System Settings
- **Linux**: Install xdotool package and use `--use-xdotool` flag
- **Rate limiting**: Adjust `--xdotool-hz` for slower injection

### API Issues
- **Groq rate limits**: Use `distil-whisper-large-v3-en` for higher rate limits
- **Gemini quota**: Monitor usage in Google AI Studio console
- **Network timeouts**: Check internet connection and API key validity

### Performance Optimization
- **High latency**: Disable `--enable-reasoning`, use `--temperature 0.1`
- **Memory usage**: Use smaller models, avoid multiple concurrent sessions
- **CPU usage**: For Wav2Vec2, consider CPU-only PyTorch installation

## Model Information

### Groq Models (Whisper-based)
- `distil-whisper-large-v3-en`: Fastest, English-optimized, highest rate limits
- `whisper-large-v3-turbo`: Balanced speed and accuracy
- `whisper-large-v3`: Highest accuracy, supports multiple languages

### Gemini Models (Google)
- `gemini-2.5-pro`: Highest capability, slower response
- `gemini-2.5-flash`: Balanced performance
- `gemini-2.5-flash-lite`: Fastest, basic capability
- `gemini-2.0-flash`: Previous generation, reliable
- `gemini-2.0-flash-lite`: Legacy fast option

