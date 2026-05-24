#!/usr/bin/env python3
import sys
import os
import tty
import termios
import select
import subprocess
import signal
import time
import re
import difflib
import argparse
import urllib.request
import json
import random
import shutil

# Try to import rich packages, otherwise output standard error
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    console = Console()
except ImportError:
    print("Error: The 'rich' library is required to run this application.")
    print("Please install it with: pip install rich")
    sys.exit(1)

# Educational topics for prompt randomization to ensure unique generated passages
TOPICS = [
    "astronomy and deep space exploration",
    "botany, plant biology, and ancient forests",
    "volcanoes, plate tectonics, and geology",
    "oceanography, deep sea vents, and marine life",
    "classical music history, orchestras, and composers",
    "ancient architectural wonders and construction methods",
    "wildlife conservation, endangered species, and ecology",
    "meticulous gourmet culinary arts and pastry baking",
    "aerodynamics, early aviation history, and flight",
    "meteorology, severe storms, and atmospheric science",
    "archaeology, lost civilizations, and fossil hunting",
    "organic chemistry, laboratory synthesis, and elements",
    "cognitive psychology, neuroscience, and memory",
    "renewable energy, solar cells, and wind turbines",
    "epic fantasy literature, world-building, and mythology",
    "microscopic organisms, cell division, and bacteria",
    "sustainable farming, organic agriculture, and soils",
    "mountaineering, alpine peaks, and glacier exploration",
    "philosophical debates, logic, and reasoning theories",
    "the physics of light, lasers, and quantum mechanics"
]

# Curated offline fallback spelling-test texts (at least 100 words each)
FALLBACK_TEXTS = {
    "easy": [
        "The quick brown fox jumps over the lazy dog in a peaceful country meadow where green grass grows tall. "
        "Every morning, birds sing sweet songs from the branches of the ancient trees, while the bright sun shines down upon the garden. "
        "Children gather here to play together, throwing a colorful ball and running through the flowers. "
        "It is a wonderful day to practice your typing, keeping your attention focused on each word as you hear it. "
        "Please make sure to type every word slowly and carefully, and do your best to avoid any spelling mistakes. Good luck!",
        
        "Learning to spell new words is a fun journey that helps us express our thoughts more clearly in writing. "
        "When we read books, we discover how letters combine to make interesting sounds that form common sentences. "
        "Practice makes perfect, so we should write every day, trying our best to remember all the basic spelling rules. "
        "Do not worry if you make some mistakes at first, because we learn from our errors and get better over time. "
        "Focus on the sound of the voice, type what you hear in the terminal, and enjoy the dictation exercise."
    ],
    "medium": [
        "It is definitely necessary to separate the concepts when you accommodate guests. "
        "Please ensure you receive their independent feedback after each occurrence, as their conscience might reveal a subtle threshold of satisfaction. "
        "The hierarchy of spelling bee vocabulary is quite surprising, and you will notice that maintaining focus requires immense concentration. "
        "A well-versed writer should comfortably master these advanced nouns and verbs. "
        "As you progress, try to stay calm and listen closely to the rhythm of the voice. "
        "This training will significantly improve your spelling and typing precision. Keep typing what you hear until the dictation is complete.",
        
        "A successful writer must possess a diverse vocabulary to keep readers engaged throughout the entire story. "
        "Words like convenience, restaurant, and persistent are frequently used, yet they are often misspelled by many people. "
        "By practicing dictation regularly, you train your brain to recognize the relationship between speech sounds and letters. "
        "This exercise will establish a strong foundation for your spelling skills and boost your confidence in professional writing. "
        "Keep your keyboard ready, concentrate on the current word, and complete the spelling challenge with maximum attention."
    ],
    "hard": [
        "His idiosyncrasy was to supersede the standard liaison, resulting in a cacophony that convalesced into a mischievous pharaoh's pronunciation. "
        "The committee found the bureaucrat's behavior during the millennium liaison to be a highly regrettable occurrence, especially since he lacked the necessary rhythm to navigate the vacuum. "
        "An independent hierarchy of foreign vocabulary, including words like gourmet, reservoir, and silhouette, can easily lead to misspelling. "
        "A well-versed writer must have the conscience and threshold to recognize these obscure nouns. "
        "Do not let these eccentric spellings cause you to lose your attention. Type every syllable exactly as it is enunciated by the voice.",
        
        "To achieve a flawless score on this dictation test, you must be prepared for rare orthographic challenges that baffle even lexicographers. "
        "The occurrence of words like questionnaire, entrepreneur, and occurrence can easily disrupt your spelling confidence if your attention wavers. "
        "Remember that punctuation and capitalization are completely ignored in the scoring, so focus entirely on typing the correct letters. "
        "Pay close attention to double consonants and silent letters that hide within obscure academic terminology. "
        "Only a dedicated student of the language will achieve accuracy when writing these complex sentences under real-time conditions."
    ]
}


class RawTerminal:
    """Context manager to put the terminal into raw mode and disable local echo
    and flow control (IXON)."""
    def __enter__(self):
        self.fd = sys.stdin.fileno()
        self.old_settings = termios.tcgetattr(self.fd)
        
        # Put terminal in raw mode
        tty.setraw(self.fd)
        
        # Disable flow control (IXON) so Ctrl+S or other flow controls don't intercept inputs
        new_settings = termios.tcgetattr(self.fd)
        new_settings[2] = new_settings[2] & ~termios.IXON
        termios.tcsetattr(self.fd, termios.TCSADRAIN, new_settings)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore terminal settings
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)


class AudioController:
    """Manages playback using either macOS 'afplay' (for premium MP3 chunks)
    or macOS 'say' (for standard TTS text)."""
    def __init__(self, voice=None, premium_mode=False):
        self.voice = voice
        self.premium_mode = premium_mode
        self.proc = None
        self.is_paused = False

    def play(self, content, rate):
        """
        If premium_mode, content is the absolute filepath to the chunk MP3.
        If standard mode, content is the string text to speak.
        """
        self.stop()
        self.is_paused = False
        
        if self.premium_mode:
            # afplay -q 1 (high quality rate scaling) -r <rate> <file>
            cmd = ['afplay', '-q', '1', '-r', str(rate), content]
        else:
            # say -v <voice> -r <wpm> <text>
            cmd = ['say']
            if self.voice:
                cmd.extend(['-v', self.voice])
            cmd.extend(['-r', str(rate), content])
            
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def pause(self):
        if self.proc and self.proc.poll() is None and not self.is_paused:
            self.proc.send_signal(signal.SIGSTOP)
            self.is_paused = True

    def resume(self):
        if self.proc and self.proc.poll() is None and self.is_paused:
            self.proc.send_signal(signal.SIGCONT)
            self.is_paused = False

    def stop(self):
        if self.proc:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            self.proc = None
        self.is_paused = False

    def is_finished(self):
        if self.proc is None:
            return True
        return self.proc.poll() is not None


def get_available_voices():
    """Queries system for available speech voices on macOS."""
    try:
        res = subprocess.run(['say', '-v', '?'], capture_output=True, text=True, check=True)
        voices = []
        for line in res.stdout.splitlines():
            parts = line.split()
            if parts:
                voices.append(parts[0])
        return voices
    except Exception:
        return []


def save_previous_test(text, target_speed, speak_speed, custom_pause, premium_mode, premium_voice, topic=""):
    """Saves the details of the spelling test to previous_test.json."""
    data = {
        "original_text": text,
        "target_speed": target_speed,
        "speak_speed": speak_speed,
        "custom_pause": custom_pause,
        "premium_mode": premium_mode,
        "premium_voice": premium_voice,
        "topic": topic
    }
    try:
        with open("previous_test.json", "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def load_previous_test():
    """Loads the details of the previous spelling test from previous_test.json."""
    if os.path.exists("previous_test.json"):
        try:
            with open("previous_test.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def generate_gemini(difficulty, topic=None):
    """Generates spelling dictation text using Gemini API REST endpoint."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not found.")
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    topic_str = f" The theme of the passage should be loosely related to: {topic}." if topic else ""
    prompt = (
        f"Generate a passage of text (at least 100 to 120 words) for a spelling dictation test.{topic_str} "
        f"The difficulty level is {difficulty}. "
        f"For Easy: Use common vocabulary, simple spelling words. "
        f"For Medium: Include typical spelling bee words and advanced nouns that a well-versed writer should know (e.g., accommodate, conscience, threshold, separate, hierarchy). "
        f"For Hard: Include challenging spelling bee words, obscure nouns, and words with non-phonetic spellings (e.g., idiosyncrasy, supersede, convalesce, pharaoh, liaison, cacophony, mischievous, pronunciation). "
        f"Keep the text natural, coherent, and grammatically correct. Do not use any numeric digits (e.g., write 'five' instead of '5'). "
        f"Do not include any formatting, markdown, titles, or numbering. Output ONLY the passage text itself."
    )
    
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    
    with urllib.request.urlopen(req, timeout=10) as response:
        res_data = json.loads(response.read().decode('utf-8'))
        text = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
        return text


def generate_openai(difficulty, topic=None):
    """Generates spelling dictation text using OpenAI API REST endpoint."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not found.")
        
    url = "https://api.openai.com/v1/chat/completions"
    
    topic_str = f" The theme of the passage should be loosely related to: {topic}." if topic else ""
    prompt = (
        f"Generate a passage of text (at least 100 to 120 words) for a spelling dictation test.{topic_str} "
        f"The difficulty level is {difficulty}. "
        f"For Easy: Use common vocabulary, simple spelling words. "
        f"For Medium: Include typical spelling bee words and advanced nouns that a well-versed writer should know (e.g., accommodate, conscience, threshold, separate, hierarchy). "
        f"For Hard: Include challenging spelling bee words, obscure nouns, and words with non-phonetic spellings (e.g., idiosyncrasy, supersede, convalesce, pharaoh, liaison, cacophony, mischievous, pronunciation). "
        f"Keep the text natural, coherent, and grammatically correct. Do not use any numeric digits (e.g., write 'five' instead of '5'). "
        f"Do not include any formatting, markdown, titles, or numbering. Output ONLY the passage text itself."
    )
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    
    with urllib.request.urlopen(req, timeout=10) as response:
        res_data = json.loads(response.read().decode('utf-8'))
        text = res_data['choices'][0]['message']['content'].strip()
        return text


def get_ai_text(provider, difficulty):
    """Fetches AI generated spelling text, falling back gracefully to local text if APIs fail."""
    prov_name = "Gemini" if provider == 2 else "OpenAI"
    diff_name = difficulty.lower()
    topic = random.choice(TOPICS)
    console.print(f"[cyan]Connecting to {prov_name} API to generate {diff_name} spelling text themed around '{topic}'...[/cyan]")
    
    try:
        if provider == 2:
            return generate_gemini(diff_name, topic), topic
        else:
            return generate_openai(diff_name, topic), topic
    except Exception as e:
        console.print(f"[bold yellow]Warning: Failed to fetch text from {prov_name} ({e}).[/bold yellow]")
        console.print("[yellow]Falling back to curated offline dictionary.[/yellow]")
        return random.choice(FALLBACK_TEXTS[diff_name]), f"offline {diff_name} fallback"


def download_openai_tts(text, voice, filepath):
    """Downloads TTS audio file from OpenAI API and saves to disk."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not found.")
        
    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    data = {
        "model": "tts-1",
        "input": text,
        "voice": voice
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    
    with urllib.request.urlopen(req, timeout=15) as response:
        with open(filepath, "wb") as f:
            f.write(response.read())


def pre_download_chunks(chunks, voice, temp_dir):
    """Pre-downloads all chunks sequentially and caches them."""
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    
    num_chunks = len(chunks)
    console.print(f"[cyan]Downloading premium human-like speech files ({voice} voice)...[/cyan]")
    
    for idx, chunk in enumerate(chunks):
        filepath = os.path.join(temp_dir, f"chunk_{idx}.mp3")
        retries = 3
        while retries > 0:
            try:
                download_openai_tts(chunk, voice, filepath)
                break
            except Exception as e:
                retries -= 1
                if retries == 0:
                    raise e
                time.sleep(1)
        console.print(f"  [green]✓[/green] Downloaded chunk {idx+1}/{num_chunks} ({len(chunk.split())} words)")


def cleanup_audio_files(temp_dir):
    """Deletes cached speech chunks and temp folder."""
    if os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


def chunk_text(text, chunk_size):
    """Splits text into chunks of specified word count."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i+chunk_size]))
    return chunks


def find_chunk_for_word(chunks, word_num):
    """Finds the chunk index that contains the target word index (1-based)."""
    cumulative = 0
    for idx, chunk in enumerate(chunks):
        words_in_chunk = len(chunk.split())
        if cumulative < word_num <= cumulative + words_in_chunk:
            return idx
        cumulative += words_in_chunk
    return len(chunks) - 1  # Fallback to the last chunk if target is out of bounds


def get_chunk_delay(chunk, target_speed, speak_speed, custom_pause=None):
    """Calculates padding delay to simulate target speed without drawing out words."""
    if custom_pause is not None:
        return custom_pause
    if target_speed >= 150:
        return 0.0
    words_count = len(chunk.split())
    target_duration = (words_count / target_speed) * 60.0
    speak_duration = (words_count / speak_speed) * 60.0
    return max(0.0, target_duration - speak_duration)


def draw_screen(typed_text, paused, target_speed, start_word, total_words, voice_name, is_audio_finished, delay_remaining):
    """Redraws the full-screen terminal interface in-place to prevent flickering."""
    # Move cursor to top-left of the viewport
    sys.stdout.write("\033[H")
    sys.stdout.flush()
    
    # Format status text and colors
    if start_word >= total_words and is_audio_finished and delay_remaining <= 0:
        status_color = "cyan"
        status_text = "SPEECH FINISHED"
        progress_str = f"Completed {total_words}/{total_words} words"
    elif paused:
        status_color = "yellow"
        status_text = "PAUSED"
        progress_str = f"Word {start_word}/{total_words} currently dictating"
    elif not is_audio_finished:
        status_color = "green"
        status_text = "SPEAKING"
        progress_str = f"Word {start_word}/{total_words} currently dictating"
    elif delay_remaining > 0:
        status_color = "blue"
        status_text = f"PACING DELAY ({delay_remaining:.1f}s)"
        progress_str = f"Word {start_word}/{total_words} currently dictating"
    else:
        status_color = "green"
        status_text = "PLAYING"
        progress_str = f"Word {start_word}/{total_words} currently dictating"
        
    header_content = (
        f"[bold cyan]Spelling Dictation & Attention Test[/bold cyan]\n"
        f"Voice: [bold magenta]{voice_name}[/bold magenta] | "
        f"Status: [bold {status_color}]{status_text}[/bold {status_color}] | "
        f"Speed: [bold white]{target_speed} WPM[/bold white] | "
        f"Progress: [bold white]{progress_str}[/bold white]\n"
        f"Shortcuts: [bold yellow]1[/bold yellow] Pause/Play | "
        f"[bold yellow]2[/bold yellow] Slower | "
        f"[bold yellow]3[/bold yellow] Faster | "
        f"[bold yellow]4[/bold yellow] Restart | "
        f"[bold yellow]5[/bold yellow] Submit | "
        f"[bold yellow]6[/bold yellow] Cancel | "
        f"[bold yellow]7[/bold yellow] Jump to Word"
    )
    
    header_panel = Panel(
        header_content,
        title="[bold magenta]Controls & Info[/bold magenta]",
        border_style="magenta",
        expand=True
    )
    
    console.print(header_panel)
    console.print("\n[bold white]Type what you hear below (suggestions, auto-correct, case & punctuation ignored):[/bold white]\n")
    
    # Render typed text with cursor block. Replace newlines with \r\n for TTY raw mode compatibility
    display_text = (typed_text + "█").replace("\n", "\r\n")
    console.print(display_text, end="")
    
    # Clear anything remaining below the cursor
    sys.stdout.write("\033[J")
    sys.stdout.flush()


def print_report(original_text, typed_text, duration_seconds):
    """Generates and prints a detailed spelling accuracy report."""
    orig_words = original_text.split()
    typed_words = typed_text.split()
    
    # Normalize words to strip punctuation and lowercase for spelling comparison
    def normalize(word):
        return re.sub(r'[^\w]', '', word).lower()
        
    orig_normalized = [normalize(w) for w in orig_words]
    typed_normalized = [normalize(w) for w in typed_words]
    
    matcher = difflib.SequenceMatcher(None, orig_normalized, typed_normalized)
    
    correct_count = 0
    misspelled_count = 0
    missed_count = 0
    extra_count = 0
    
    formatted_diff = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for idx in range(i1, i2):
                formatted_diff.append(f"[green]{orig_words[idx]}[/green]")
                correct_count += 1
        elif tag == 'replace':
            # Highlight misspellings and insertions/deletions within replacements
            for idx in range(max(i2 - i1, j2 - j1)):
                o_idx = i1 + idx
                t_idx = j1 + idx
                if o_idx < i2 and t_idx < j2:
                    formatted_diff.append(f"[bold red]\\[{orig_words[o_idx]}][/bold red]->[bold yellow]({typed_words[t_idx]})[/bold yellow]")
                    misspelled_count += 1
                elif o_idx < i2:
                    formatted_diff.append(f"[bold red]\\[{orig_words[o_idx]}][/bold red]")
                    missed_count += 1
                elif t_idx < j2:
                    formatted_diff.append(f"[bold cyan]({typed_words[t_idx]})[/bold cyan]")
                    extra_count += 1
        elif tag == 'delete':
            for idx in range(i1, i2):
                formatted_diff.append(f"[bold red]\\[{orig_words[idx]}][/bold red]")
                missed_count += 1
        elif tag == 'insert':
            for idx in range(j1, j2):
                formatted_diff.append(f"[bold cyan]({typed_words[idx]})[/bold cyan]")
                extra_count += 1
                
    accuracy = (correct_count / len(orig_words) * 100) if orig_words else 0.0
    wpm = (len(typed_words) / (duration_seconds / 60)) if duration_seconds > 0 else 0.0
    
    summary_table = Table(title="Spelling Test Summary", title_style="bold magenta", border_style="magenta")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white")
    
    summary_table.add_row("Accuracy Score", f"[bold green]{accuracy:.1f}%[/bold green]" if accuracy >= 90 else f"[bold yellow]{accuracy:.1f}%[/bold yellow]")
    summary_table.add_row("Typing Speed", f"{wpm:.1f} WPM")
    summary_table.add_row("Correct Words", f"{correct_count}")
    summary_table.add_row("Misspelled Words", f"{misspelled_count}")
    summary_table.add_row("Missed Words (Skipped)", f"{missed_count}")
    summary_table.add_row("Extra Words (Inserted)", f"{extra_count}")
    summary_table.add_row("Total Time Taken", f"{duration_seconds:.1f} seconds")
    
    console.print("\n")
    console.print(Panel(
        summary_table,
        title="[bold green]Test Complete[/bold green]",
        border_style="green",
        expand=False
    ))
    
    console.print("\n[bold white]Word-by-word Comparison:[/bold white]")
    console.print("[dim italic]Legend: [green]Correct[/green] | [bold red]\\[Missed][/bold red] | [bold red]\\[Original][/bold red]->[bold yellow](Typed)[/bold yellow] | [bold cyan](Extra)[/bold cyan][/dim italic]\n")
    
    diff_text = " ".join(formatted_diff)
    console.print(Panel(diff_text, border_style="blue", title="[bold blue]Comparison Report[/bold blue]", expand=True))


def interactive_config_menu():
    """Renders interactive startup configuration menu in TTY."""
    console.print(Panel(
        "[bold cyan]Welcome to the Spelling Dictation & Attention Test![/bold cyan]\n"
        "Configure your options below.",
        border_style="cyan"
    ))
    
    # Check if a previous test state is cached
    previous_test = load_previous_test()
    has_prev = previous_test is not None
    
    # 1. Text Source
    console.print("\n[bold white]1. Select Text Source:[/bold white]")
    if has_prev:
        topic_desc = f" (Theme: '{previous_test.get('topic', 'N/A')}')"
        console.print(f"  [1] [bold green]Retry / repeat the previous test[/bold green]{topic_desc} - {previous_test['target_speed']} WPM")
        console.print("  [2] Read local [bold green]input.txt[/bold green] (Default)")
        console.print("  [3] Generate dynamically using [bold green]Gemini AI[/bold green]")
        console.print("  [4] Generate dynamically using [bold green]OpenAI AI[/bold green]")
    else:
        console.print("  [1] Read local [bold green]input.txt[/bold green] (Default)")
        console.print("  [2] Generate dynamically using [bold green]Gemini AI[/bold green]")
        console.print("  [3] Generate dynamically using [bold green]OpenAI AI[/bold green]")
        
    choice_src = input(f"Enter selection [default {'2' if has_prev else '1'}]: ").strip()
    if not choice_src:
        choice_src = '2' if has_prev else '1'
        
    source = 1
    if has_prev:
        if choice_src == '1':
            # Load and return previous test config directly (is_retry = True)
            return (
                previous_test['original_text'],
                previous_test['target_speed'],
                previous_test['speak_speed'],
                previous_test['custom_pause'],
                previous_test['premium_mode'],
                previous_test['premium_voice'],
                previous_test.get('topic', ''),
                True  # is_retry
            )
        elif choice_src == '2':
            source = 1  # input.txt
        elif choice_src == '3':
            source = 2  # Gemini
        elif choice_src == '4':
            source = 3  # OpenAI
    else:
        if choice_src == '1':
            source = 1  # input.txt
        elif choice_src == '2':
            source = 2  # Gemini
        elif choice_src == '3':
            source = 3  # OpenAI
            
    original_text = ""
    topic = "local input.txt"
    
    if source == 1:
        # Load local input.txt
        if not os.path.exists("input.txt"):
            console.print("[yellow]input.txt not found. Creating a default file...[/yellow]")
            default_content = (
                "It is definitely necessary to separate the concepts when you accommodate guests. "
                "Please ensure you receive their independent feedback after each occurrence, as their conscience might reveal a subtle threshold of satisfaction. "
                "The hierarchy of spelling bee vocabulary is quite surprising, and you will notice that maintaining focus requires immense concentration. "
                "A well-versed writer should comfortably master these advanced nouns and verbs. "
                "As you progress, try to stay calm and listen closely to the rhythm of the voice. "
                "This training will significantly improve your spelling and typing precision. Keep typing what you hear until the dictation is complete."
            )
            with open("input.txt", "w", encoding="utf-8") as f:
                f.write(default_content)
        with open("input.txt", "r", encoding="utf-8") as f:
            original_text = f.read().strip()
    else:
        # Ask for difficulty
        console.print("\n[bold white]2. Select AI Difficulty Level:[/bold white]")
        console.print("  [1] Easy (basic spelling)")
        console.print("  [2] Medium (spelling bee & advanced writer vocabulary) (Default)")
        console.print("  [3] Hard (highly challenging spelling bee and obscure words)")
        
        choice_diff = input("Enter selection [1-3, default 2]: ").strip()
        difficulty = "Medium"
        if choice_diff == '1':
            difficulty = "Easy"
        elif choice_diff == '3':
            difficulty = "Hard"
            
        original_text, topic = get_ai_text(source, difficulty)

    # 3. Voice Quality selection
    premium_mode = False
    premium_voice = "alloy"
    
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        console.print("\n[bold white]3. Select Voice Quality:[/bold white]")
        console.print("  [1] Premium (OpenAI Human-like TTS - online) (Default)")
        console.print("  [2] Standard (macOS say - offline)")
        
        choice_quality = input("Enter selection [1-2, default 1]: ").strip()
        if choice_quality != '2':
            premium_mode = True
            
            # Select Premium Voice
            console.print("\n[bold white]4. Select Premium Voice Model:[/bold white]")
            console.print("  [1] Alloy (neutral) (Default)")
            console.print("  [2] Echo (warm male)")
            console.print("  [3] Fable (dramatic)")
            console.print("  [4] Onyx (deep male)")
            console.print("  [5] Nova (expressive female)")
            console.print("  [6] Shimmer (professional female)")
            
            choice_voice = input("Enter selection [1-6, default 1]: ").strip()
            voices = {
                '1': 'alloy', '2': 'echo', '3': 'fable',
                '4': 'onyx', '5': 'nova', '6': 'shimmer'
            }
            premium_voice = voices.get(choice_voice, 'alloy')

    # 5. Playback Speed Config
    console.print("\n[bold white]5. Configure Playback Speed:[/bold white]")
    while True:
        try:
            speed_input = input("Enter target WPM speed (10-350) [default 175]: ").strip()
            if not speed_input:
                target_speed = 175
                break
            target_speed = int(speed_input)
            if 10 <= target_speed <= 350:
                break
            console.print("[red]Please enter a speed between 10 and 350 WPM.[/red]")
        except ValueError:
            console.print("[red]Invalid input. Please enter a valid number.[/red]")
            
    speak_speed = max(150, target_speed)
    custom_pause = None
    
    if target_speed < 150:
        console.print(f"\n[bold yellow]Notice: Target speed ({target_speed} WPM) is below 150 WPM. Pacing chunks is recommended.[/bold yellow]")
        # Ask for speak speed
        while True:
            try:
                speak_input = input("Enter speaking WPM speed for individual words (150-250) [default 150]: ").strip()
                if not speak_input:
                    speak_speed = 150
                    break
                speak_speed = int(speak_input)
                if 150 <= speak_speed <= 250:
                    break
                console.print("[red]Please enter a speed between 150 and 250 WPM.[/red]")
            except ValueError:
                console.print("[red]Invalid input. Please enter a valid number.[/red]")
                
        # Ask for custom pause
        while True:
            pause_input = input("Enter custom pause duration in seconds (or 'auto' to calculate based on WPM) [default auto]: ").strip().lower()
            if not pause_input or pause_input == 'auto':
                custom_pause = None
                break
            try:
                custom_pause = float(pause_input)
                if 0.0 <= custom_pause <= 60.0:
                    break
                console.print("[red]Please enter a pause duration between 0.0 and 60.0 seconds.[/red]")
            except ValueError:
                console.print("[red]Invalid input. Please enter 'auto' or a valid decimal number.[/red]")

    return original_text, target_speed, speak_speed, custom_pause, premium_mode, premium_voice, topic, False


def main():
    parser = argparse.ArgumentParser(description="Terminal-based Spelling Dictation App")
    parser.add_argument("--voice", "-v", type=str, default=None, help="TTS Voice Name (e.g., Samantha, Daniel)")
    parser.add_argument("--premium", action="store_true", help="Use OpenAI premium human-like TTS (requires OPENAI_API_KEY)")
    parser.add_argument("--premium-voice", type=str, default="alloy", choices=["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                        help="OpenAI premium voice model (default: alloy)")
    parser.add_argument("--speed", "-s", type=int, default=175, help="Initial speech speed in WPM (default: 175)")
    parser.add_argument("--speak-speed", type=int, default=None, help="TTS speaking rate for low-WPM chunk pacing (>= 150)")
    parser.add_argument("--custom-pause", type=float, default=None, help="Force custom pause between chunks in seconds")
    parser.add_argument("--chunk-size", "-c", type=int, default=6, help="Words spoken per chunk (default: 6)")
    parser.add_argument("--input", "-i", type=str, default=None, help="Input text file path (skips interactive config)")
    parser.add_argument("--generate-difficulty", "-d", type=str, choices=["easy", "medium", "hard"], default=None,
                        help="Auto-generate AI text with chosen difficulty (skips interactive config, uses Gemini by default)")
    args = parser.parse_args()

    original_text = ""
    speed = args.speed
    speak_speed = args.speak_speed if args.speak_speed else max(150, speed)
    custom_pause = args.custom_pause
    premium_mode = args.premium
    premium_voice = args.premium_voice
    topic = "CLI Config"
    is_retry = False
    
    # Store standard terminal TTY settings for switching inside main loop
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    
    # Decide text source: CLI overrides or interactive menu
    if args.input:
        if not os.path.exists(args.input):
            console.print(f"[bold red]Error: Input file '{args.input}' not found.[/bold red]")
            sys.exit(1)
        with open(args.input, "r", encoding="utf-8") as f:
            original_text = f.read().strip()
        topic = "CLI input file"
    elif args.generate_difficulty:
        # CLI direct generation (default Gemini if both key found, otherwise checks environment)
        provider = 2 # Gemini
        if not os.environ.get("GEMINI_API_KEY") and os.environ.get("OPENAI_API_KEY"):
            provider = 3 # OpenAI
        original_text, topic = get_ai_text(provider, args.generate_difficulty)
    else:
        # Interactive configuration
        original_text, speed, speak_speed, custom_pause, p_mode, p_voice, t_name, is_ret = interactive_config_menu()
        premium_mode = p_mode
        premium_voice = p_voice
        topic = t_name
        is_retry = is_ret
        
    if not original_text:
        console.print("[bold red]Error: No dictation text loaded.[/bold red]")
        sys.exit(1)
        
    # Check if premium mode is enabled but key is missing
    if premium_mode and not os.environ.get("OPENAI_API_KEY"):
        console.print("[yellow]Warning: OPENAI_API_KEY not found in environment. Falling back to offline macOS say.[/yellow]")
        premium_mode = False
        
    # Get available voices and select a default if none specified (for standard mode)
    available_voices = get_available_voices()
    voice = args.voice
    if not voice:
        # Preferred default voices
        for v in ["Samantha", "Daniel", "Alex", "Fred"]:
            if v in available_voices:
                voice = v
                break
        if not voice and available_voices:
            voice = available_voices[0]
            
    if voice and voice not in available_voices:
        console.print(f"[yellow]Warning: Voice '{voice}' not found on this system. Falling back to system default.[/yellow]")
        voice = None
        
    voice_name = premium_voice if premium_mode else (voice if voice else "System Default")
    if premium_mode:
        voice_name += " (Premium)"
        
    chunks = chunk_text(original_text, args.chunk_size)
    num_chunks = len(chunks)
    total_words = len(original_text.split())
    
    # Save this run config to previous_test.json if it is not a retry
    if not is_retry:
        save_previous_test(original_text, speed, speak_speed, custom_pause, premium_mode, premium_voice, topic)
        
    temp_dir = ".temp_audio_cache"
    
    # Pre-download chunks if premium mode is enabled
    if premium_mode:
        # If it is a retry, check if we can reuse cached files to save API quota and latency
        cache_valid = os.path.exists(temp_dir) and len(os.listdir(temp_dir)) == num_chunks
        
        if is_retry and cache_valid:
            console.print("[green]Reusing cached premium audio files from previous test.[/green]")
            time.sleep(1)
        else:
            try:
                pre_download_chunks(chunks, premium_voice, temp_dir)
            except Exception as e:
                console.print(f"[bold red]Error pre-downloading OpenAI TTS speech files: {e}[/bold red]")
                console.print("[yellow]Falling back to standard offline macOS say.[/yellow]")
                premium_mode = False
                voice_name = voice if voice else "System Default"
                
    audio = AudioController(voice=voice, premium_mode=premium_mode)
    
    typed_text = ""
    paused = False
    chunk_idx = 0
    delay_remaining = 0.0
    
    # Hide terminal cursor while redrawing
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()
    
    # Clear screen initially
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    
    start_time = time.time()
    last_redraw_time = 0
    last_loop_time = time.time()
    
    try:
        with RawTerminal():
            while True:
                now = time.time()
                elapsed_time = now - last_loop_time
                last_loop_time = now
                
                # Check playback progression
                if not paused:
                    if chunk_idx < num_chunks:
                        # If audio is playing, do nothing. If audio completed, tick down padding delay
                        if audio.is_finished():
                            if delay_remaining > 0:
                                delay_remaining = max(0.0, delay_remaining - elapsed_time)
                            else:
                                if premium_mode:
                                    # Play cached MP3 chunk using afplay
                                    filepath = os.path.join(temp_dir, f"chunk_{chunk_idx}.mp3")
                                    speak_speed_to_use = max(150, speed) if speed < 150 else speed
                                    if speed < 150 and args.speak_speed:
                                        speak_speed_to_use = speak_speed
                                    rate_multiplier = speak_speed_to_use / 150.0
                                    
                                    delay_remaining = get_chunk_delay(chunks[chunk_idx], speed, speak_speed_to_use, custom_pause)
                                    audio.play(filepath, rate_multiplier)
                                else:
                                    # Play next text chunk using standard say command
                                    speak_speed_to_use = max(150, speed) if speed < 150 else speed
                                    if speed < 150 and args.speak_speed:
                                        speak_speed_to_use = speak_speed
                                    
                                    delay_remaining = get_chunk_delay(chunks[chunk_idx], speed, speak_speed_to_use, custom_pause)
                                    audio.play(chunks[chunk_idx], speak_speed_to_use)
                                
                                chunk_idx += 1
                                last_redraw_time = 0 # Force immediate redraw
                                
                # Periodic or event-driven screen redraw
                if now - last_redraw_time > 0.1:
                    # Calculate active word count for progress
                    active_idx = max(0, chunk_idx - 1)
                    if chunk_idx == 0:
                        start_word = 1
                    else:
                        start_word = sum(len(c.split()) for c in chunks[:active_idx]) + 1
                    start_word = min(start_word, total_words)
                    
                    draw_screen(typed_text, paused, speed, start_word, total_words, voice_name, audio.is_finished(), delay_remaining)
                    last_redraw_time = now
                    
                # Read keyboard input without blocking
                r, _, _ = select.select([sys.stdin], [], [], 0.02)
                if r:
                    char = sys.stdin.read(1)
                    
                    if char == '\x03':  # Ctrl+C -> Cancel
                        audio.stop()
                        sys.stdout.write("\033[?25h\r\n\033[31mCancelled.\033[0m\r\n")
                        sys.stdout.flush()
                        return
                        
                    elif char == '1':  # 1 -> Pause/Play
                        paused = not paused
                        if paused:
                            audio.pause()
                        else:
                            audio.resume()
                        last_redraw_time = 0
                        
                    elif char == '2':  # 2 -> Slower
                        speed = max(10, speed - 15)
                        # Restart current chunk at new speed
                        if not paused and chunk_idx > 0:
                            chunk_idx -= 1
                            audio.stop()
                            delay_remaining = 0.0
                        last_redraw_time = 0
                        
                    elif char == '3':  # 3 -> Faster
                        speed = min(350, speed + 15)
                        # Restart current chunk at new speed
                        if not paused and chunk_idx > 0:
                            chunk_idx -= 1
                            audio.stop()
                            delay_remaining = 0.0
                        last_redraw_time = 0
                        
                    elif char == '4':  # 4 -> Restart dictation
                        audio.stop()
                        typed_text = ""
                        paused = False
                        chunk_idx = 0
                        delay_remaining = 0.0
                        start_time = time.time()
                        last_redraw_time = 0
                        
                    elif char == '5':  # 5 -> Submit & Finish
                        audio.stop()
                        break
                        
                    elif char == '6':  # 6 -> Cancel & Exit
                        audio.stop()
                        sys.stdout.write("\033[?25h\r\n\033[31mCancelled.\033[0m\r\n")
                        sys.stdout.flush()
                        return
                        
                    elif char == '7':  # 7 -> Jump to Word
                        # Stop active speech
                        audio.stop()
                        
                        # Temporarily restore terminal raw mode settings to allow standard input
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                        
                        # Show terminal cursor and add newlines for visual clarity
                        sys.stdout.write("\033[?25h\r\n")
                        sys.stdout.flush()
                        
                        try:
                            word_input = input(f"Enter word number to jump to (1-{total_words}): ").strip()
                            if word_input:
                                target_word = int(word_input)
                                if 1 <= target_word <= total_words:
                                    chunk_idx = find_chunk_for_word(chunks, target_word)
                                    delay_remaining = 0.0
                                    paused = False
                                    last_redraw_time = 0
                                else:
                                    console.print(f"[red]Word number must be between 1 and {total_words}.[/red]")
                                    time.sleep(1.5)
                        except ValueError:
                            console.print("[red]Invalid input. Must be a valid number.[/red]")
                            time.sleep(1.5)
                        finally:
                            # Re-enter raw terminal mode
                            tty.setraw(fd)
                            new_settings = termios.tcgetattr(fd)
                            new_settings[2] = new_settings[2] & ~termios.IXON
                            termios.tcsetattr(fd, termios.TCSADRAIN, new_settings)
                            
                            # Hide cursor again
                            sys.stdout.write("\033[?25l")
                            # Clear the console prompt lines to keep typing screen clean
                            sys.stdout.write("\033[2J\033[H")
                            sys.stdout.flush()
                            last_redraw_time = 0
                            last_loop_time = time.time()  # Reset loop time to prevent pacing jumps
                        
                    elif char == '\x1b':  # Escape sequence (e.g. arrow keys)
                        # Consume extra characters of arrow key sequence to prevent garbage characters
                        r2, _, _ = select.select([sys.stdin], [], [], 0.02)
                        if r2:
                            sys.stdin.read(2)
                            
                    elif char in ('\x7f', '\x08'):  # Backspace
                        if len(typed_text) > 0:
                            typed_text = typed_text[:-1]
                        last_redraw_time = 0
                        
                    elif char in ('\r', '\n'):  # Enter
                        typed_text += "\n"
                        last_redraw_time = 0
                        
                    elif ord(char) >= 32 and ord(char) < 127:  # Printable character
                        # Avoid allowing 1-7 keys to leak through to typed text if pressed in normal typing
                        if char not in ('1', '2', '3', '4', '5', '6', '7'):
                            typed_text += char
                        last_redraw_time = 0
                        
    finally:
        # Make sure speech stops and restore cursor
        audio.stop()
        sys.stdout.write("\033[?25h\r\n")
        sys.stdout.flush()
        
    # Render final spelling test report
    duration_seconds = time.time() - start_time
    print_report(original_text, typed_text, duration_seconds)


if __name__ == "__main__":
    main()
