# QuickScribe

A Python script that listens for a configurable trigger key, records audio while the key is held, uses Groq (Whisper) or Google Gemini APIs for speech-to-text transcription, and automatically pastes the resulting text into the currently active application.

## Features

*   Real-time audio recording triggered by a hotkey.
*   Transcription via Groq (using various Whisper models) or Google Gemini.
*   Configurable trigger key (defaults to `alt_r`).
*   Cross-platform text pasting using `pyperclip` and `pynput` (tested on macOS, should work on Windows/Linux).
*   Flexible setup:
    *   Interactive mode for selecting provider and model if run without arguments.
    *   Command-line arguments for specifying provider, model, trigger key, etc.
*   Automatic loading of API keys from a `.env` file.
*   Model selection based on `groq_models.txt` and `gemini_models.txt`.

## Requirements

*   Python 3.x
*   Python packages: `sounddevice`, `soundfile`, `numpy`, `pynput`, `python-dotenv`, `pyperclip`, `groq`, `google-generativeai`, `argparse` (Install via `requirements.txt`).
*   **Operating System Permissions:**
    *   **Microphone Access:** The script needs permission to access your microphone for recording.
    *   **Accessibility / Input Monitoring (macOS) or similar (Windows/Linux):** The script requires permissions to monitor keyboard input (for the trigger key) and simulate keyboard events (for pasting). Grant these permissions when prompted by your OS.
    *   **macOS Accessibility Permission:** When using the default keyboard injection on macOS, you must grant accessibility permissions to your Python interpreter or Terminal app in System Settings → Privacy & Security → Accessibility. This allows the script to inject keyboard events for text pasting.

## Installation

1.  **Clone the repository (if applicable) or download the files.**
2.  **Navigate to the project directory in your terminal.**
3.  **Install the required Python packages:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  **Create a `.env` file:** Copy the `.env.example` file to `.env` in the same directory as the script.
    ```bash
    cp .env.example .env
    ```
2.  **Add your API Keys:**
    *   Open the `.env` file in a text editor.
    *   **Groq:** Replace `gsk_YOUR_GROQ_API_KEY_HERE` with your actual Groq API key. Get one from [https://console.groq.com/keys](https://console.groq.com/keys).
    *   **Google Gemini:** Replace `YOUR_GOOGLE_AI_STUDIO_KEY_HERE` with your actual Google AI Studio (Gemini) API key. Get one from [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).
    *   *Note:* You only need the key for the provider(s) you intend to use. If only one key is present, the script may default to that provider in interactive mode.
3.  **(Optional) Review Model Lists:** The files `groq_models.txt` and `gemini_models.txt` contain the model IDs used for selection in interactive mode. You can update these if new models become available.

## Usage

Run the script from your terminal within the project directory.

**1. Interactive Mode:**

*   Simply run the script without any arguments:
    ```bash
    python dictate.py
    ```
*   The script will detect available API keys in `.env` or prompt you to select a provider (Groq/Gemini) and then a specific model from the corresponding `.txt` file.
*   It will use the default trigger key (`alt_r`) unless specified otherwise via arguments (which defeats interactive mode).

**2. Command-Line Mode:**

*   Specify the provider and model using arguments:
    ```bash
    # Example using Groq and a specific Whisper model
    python dictate.py --provider groq --model whisper-large-v3

    # Example using Gemini
    python dictate.py --provider gemini --model gemini-2.0-flash

    # Example specifying a different trigger key (Right Ctrl)
    python dictate.py --provider groq --model whisper-large-v3 --trigger-key ctrl_r

    # Example specifying language for Groq (optional)
    python dictate.py --provider groq --model whisper-large-v3 --language es
    ```
*   **Available Arguments:**
    *   `--provider`: `groq` or `gemini` (Required if using arguments)
    *   `--model`: The specific model ID for the chosen provider (Required if using arguments)
    *   `--trigger-key`: Key name (e.g., `alt_r`, `ctrl_l`, `f19`, `a`). Default: `alt_r`.
    *   `--language`: Language code (e.g., `en`, `es`). Used by Groq, ignored by Gemini. Default: `None`.
    *   `--sample-rate`: Audio sample rate in Hz. Default: `16000`.
    *   `--channels`: Number of audio channels. Default: `1` (mono).

**Core Workflow:**

1.  Once the script is running and configured, it will print `Hold '<trigger_key>' to record...`.
2.  Go to the application where you want to dictate text.
3.  **Press and hold** the configured trigger key (e.g., `Right Alt`). The script will print `Recording started...`.
4.  Speak clearly.
5.  **Release** the trigger key. The script will print `Stopped. Processing...`.
6.  After a moment, the script will transcribe the audio and print the result (e.g., `Transcription: Hello world.`).
7.  The transcribed text will be automatically pasted into the active application window.
8.  The script will print `Hold '<trigger_key>' to record...` again, ready for the next dictation.

**Exiting:**

*   Press `Ctrl+C` in the terminal where the script is running.

## License

This project is licensed under the Apache License 2.0. See the LICENSE file for details (or refer to the standard Apache 2.0 text).

## Notes / Troubleshooting

*   **Permissions are Crucial:** Ensure you grant the necessary Microphone and Accessibility/Input Monitoring permissions when prompted by your OS. If the trigger key doesn't work or pasting fails, missing permissions are the most likely cause.
*   **Gemini Language:** As noted in the script output, the Gemini API currently performs best with English audio, regardless of any `--language` argument provided.
*   **Audio Devices:** The script uses the default system input device. If you have issues, ensure the correct microphone is selected as the default in your OS sound settings. Check the terminal for any errors from the `sounddevice` library.
*   **Clipboard Utilities:** `pyperclip` relies on system clipboard utilities (like `xclip` on Linux). Ensure these are installed if you encounter clipboard errors.