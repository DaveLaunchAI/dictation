# Spelling Dictation & Attention Test

A terminal-based Python application designed to test your spelling accuracy and attention to audio dictation. The application reads text passages out loud, allows you to type what you hear in real-time, blocks terminal autocorrect/suggestions, and generates a color-coded spelling analysis report once completed.

---

## Features

- **Interactive Config Menu**: Choose to type from a local file (`input.txt`) or generate passages dynamically using **Gemini AI** or **OpenAI AI**.
- **Adjustable Difficulty Levels**: AI-generated texts support **Easy** (common words), **Medium** (spelling bee and advanced writer vocabulary), and **Hard** (challenging orthography and obscure terms) difficulties.
- **Adaptive Low-WPM Pacing**: Speeds below 150 WPM (supporting down to **10 WPM**) speak word groups at a natural rate and insert calculated pacing delays in between, preventing robotic-sounding TTS audio.
- **Dynamic Progress Indicator**: Displays real-time status bar statistics showing active speed, voice settings, and word-by-word progress (e.g. `Word 55/104 currently dictating`).
- **Number Key Hotkeys**: Intercepts number keys `1` through `5` for direct playback control, ensuring they do not leak into your text input buffer.
- **Case & Punctuation Tolerant Report**: Generates a detailed statistical summary and side-by-side comparison, ignoring capitalization, spacing, and punctuation symbols for spelling score accuracy.

---

## Prerequisites

- **Operating System**: macOS (uses the native `/usr/bin/say` offline TTS engine).
- **Python**: Python 3.12+ (configured virtual environment in `.venv`).
- **Libraries**: `rich` (console interface formatting).

---

## Installation & Setup

1. **Clone or Navigate to the Directory**:
   ```bash
   cd /Users/dave/Code/dictation
   ```

2. **Activate the Virtual Environment & Install Dependencies**:
   ```bash
   source .venv/bin/activate
   pip install rich
   ```

3. **Set Up API Keys (Optional)**:
   To use live AI text generation, set your API keys in your shell environment:
   ```bash
   export GEMINI_API_KEY="your-api-key"
   # OR
   export OPENAI_API_KEY="your-api-key"
   ```
   *Note: If no API keys are found or if the system is offline, the app automatically falls back to high-quality, pre-programmed offline passages.*

---

## Running the Application

### 1. Interactive Config Mode (Recommended)
Run the script without arguments to open the interactive setup menus:
```bash
python dictation.py
```
You will be prompted to:
- Choose your text source (local `input.txt`, Gemini AI, or OpenAI AI).
- Choose difficulty level (if generating via AI).

### 2. Bypass Interactive Menus (CLI Overrides)
You can directly launch with preset options using CLI flags:
- `--generate-difficulty` / `-d`: Auto-generate AI text with chosen difficulty (`easy`, `medium`, or `hard`).
- `--speed` / `-s`: Specify initial speech speed in WPM (default is 175).
- `--input` / `-i`: Path to a custom text file.
- `--voice` / `-v`: Specify a custom macOS speech voice name (e.g. `Samantha` or `Daniel`).

Examples:
```bash
# Auto-generate a medium-difficulty passage
python dictation.py --generate-difficulty medium

# Read from a custom file at a slow speed of 80 WPM
python dictation.py --input test_text.txt --speed 80
```

---

## Hotkeys Reference

While the dictation test is running, type what you hear. The following single-number keys control playback and are intercepted automatically:

- **`1`**: Pause / Play Toggle (suspends/resumes audio and pacing timers instantly).
- **`2`**: Slower (decreases dictation speed by 15 WPM and restarts the current sentence).
- **`3`**: Faster (increases dictation speed by 15 WPM and restarts the current sentence).
- **`4`**: Restart (resets dictation from the beginning and clears your typing buffer).
- **`5`**: Submit & Finish (stops playback and runs spelling scoring comparison).
- **`Ctrl + C`**: Cancel & Exit (aborts the test immediately without printing a report).

---

## Spelling Report Analysis

After pressing **`5`** to submit, the terminal displays:
- **Accuracy Score**: The percentage of words spelled correctly.
- **Typing Speed**: Measured in WPM based on elapsed time.
- **Word Metrics**: A summary table showing correct, misspelled, skipped (missed), and extra (inserted) words.
- **Word-by-Word Diff**: An inline, color-coded comparison of the original text vs. what you typed:
  - `Green`: Correctly typed word.
  - `[Red Brackets]`: Skipped or missed word.
  - `[Red Brackets]->(Yellow Parentheses)`: Misspelled word showing `[original]->(typed)`.
  - `(Cyan Parentheses)`: Extra word inserted.