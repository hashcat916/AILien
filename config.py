"""Configuration for AILIEN."""
import os
from pathlib import Path

# Project paths
PROJECT_DIR = Path(__file__).parent.resolve()
CACHE_DIR = PROJECT_DIR / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_DIR / ".env")
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Cloud LLM (xAI / Grok) — primary brain
# ---------------------------------------------------------------------------
CLOUD_API_KEY = os.getenv("CLOUD_API_KEY", os.getenv("XAI_API_KEY", os.getenv("GROQ_API_KEY", "")))
CLOUD_BASE_URL = os.getenv("CLOUD_BASE_URL", "https://api.x.ai/v1")
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "grok-4.3")
CLOUD_TEMPERATURE = float(os.getenv("CLOUD_TEMPERATURE", "0.2"))
CLOUD_MAX_TOKENS = int(os.getenv("CLOUD_MAX_TOKENS", "4096"))

# ---------------------------------------------------------------------------
# Vision model (cloud or local fallback)
# ---------------------------------------------------------------------------
# xAI Grok 4.3 supports vision natively.  Older names like
# "grok-2-vision-1212" are deprecated and return 404.
VISION_MODEL = os.getenv("VISION_MODEL", "grok-4.3")
VISION_PROMPT = os.getenv("VISION_PROMPT", "Describe this screen in detail. Mention all visible UI elements, text, buttons, windows, icons, menus, and the approximate positions of interactive elements.")

# ---------------------------------------------------------------------------
# Local Ollama fallback (kept for offline use or vision fallback)
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))
OLLAMA_MAX_TOKENS = int(os.getenv("OLLAMA_MAX_TOKENS", "4096"))
OLLAMA_CONTEXT_WINDOW = int(os.getenv("OLLAMA_CONTEXT_WINDOW", "8192"))

# ---------------------------------------------------------------------------
# Audio settings
# ---------------------------------------------------------------------------
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1
AUDIO_BLOCK_SIZE = 1024
AUDIO_RECORD_TIMEOUT = 30  # seconds
AUDIO_SILENCE_THRESHOLD = 0.01  # RMS threshold for silence detection
AUDIO_SILENCE_DURATION = 0.8  # seconds of silence before stopping (tuned for fast but reliable response)

# Whisper settings
# For low-RAM / old CPUs (e.g. 8GB RAM), use "tiny" for faster transcription.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")  # tiny, base, small, medium, large-v3
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")  # cpu, cuda, auto
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")  # int8, float16, float32
WHISPER_VAD_FILTER = os.getenv("WHISPER_VAD_FILTER", "false").lower() == "true"  # Silero VAD filtering (kept off — can be too aggressive)

# Agent behavior
_DEFAULT_WAKE_WORDS = [
    "hey ailien", "ok ailien", "ailien",
    "hey alien", "ok alien", "alien",
    "hey jarvis", "ok jarvis", "jarvis",
    "hello", "hey", "hi",
    "hello there", "hey there", "hi there",
    "what's up", "sup", "yo", "howdy",
    "good morning", "good afternoon", "good evening",
]
_AGENT_WAKE_WORDS_ENV = os.getenv("AGENT_WAKE_WORDS", "")
if _AGENT_WAKE_WORDS_ENV.strip():
    AGENT_WAKE_WORDS = [w.strip().lower() for w in _AGENT_WAKE_WORDS_ENV.split(",") if w.strip()]
else:
    AGENT_WAKE_WORDS = list(_DEFAULT_WAKE_WORDS)
AGENT_USE_WAKE_WORD = os.getenv("AGENT_USE_WAKE_WORD", "false").lower() == "true"
AGENT_VOICE_FEEDBACK = os.getenv("AGENT_VOICE_FEEDBACK", "true").lower() == "true"
AGENT_CONFIRM_DANGEROUS = os.getenv("AGENT_CONFIRM_DANGEROUS", "true").lower() == "true"
AGENT_MAX_RETRIES = 3

# TTS engine: "edge" (natural, requires internet), "pyttsx3" (robotic, offline)
TTS_ENGINE = os.getenv("TTS_ENGINE", "pyttsx3")

# ---------------------------------------------------------------------------
# Picovoice Porcupine — custom wake word engine
# ---------------------------------------------------------------------------
# Porcupine supports custom wake words like "hey alien" / "hey ailien" via
# .ppn model files from the Picovoice Console (https://console.picovoice.ai/).
# Free tier: up to 2 custom wake words, runs 100%% offline after setup.
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY", "")
_PICO_PATHS = os.getenv("PICOVOICE_KEYWORD_PATHS", "")
PICOVOICE_KEYWORD_PATHS = [p.strip() for p in _PICO_PATHS.split(",") if p.strip()] if _PICO_PATHS else []
# Optional: per-keyword sensitivities (0.0-1.0), comma-separated, matching
# the order of PICOVOICE_KEYWORD_PATHS.
_PICO_SENS = os.getenv("PICOVOICE_SENSITIVITIES", "")
PICOVOICE_SENSITIVITIES: list[float] = [float(x.strip()) for x in _PICO_SENS.split(",") if x.strip()] if _PICO_SENS else None

# Wake word detection tuning
WAKE_WORD_CHUNK_MAX_DURATION = float(os.getenv("WAKE_WORD_CHUNK_MAX_DURATION", "1.0"))  # Max seconds per audio chunk — shorter = faster wake word detection
WAKE_WORD_CHUNK_SILENCE_DURATION = float(os.getenv("WAKE_WORD_CHUNK_SILENCE_DURATION", "0.4"))  # Silence before stopping chunk
VAD_AGGRESSIVENESS = int(os.getenv("VAD_AGGRESSIVENESS", "2"))  # WebRTC VAD: 0=least aggressive, 3=most aggressive

# ---------------------------------------------------------------------------
# Conversation memory
# ---------------------------------------------------------------------------
CONVERSATIONS_DIR = PROJECT_DIR / "conversations"
CONVERSATIONS_DIR.mkdir(exist_ok=True)
CONVERSATION_MAX_HISTORY = int(os.getenv("CONVERSATION_MAX_HISTORY", "24"))
CONVERSATION_AUTO_SAVE = os.getenv("CONVERSATION_AUTO_SAVE", "true").lower() == "true"

# ---------------------------------------------------------------------------
# Skills / plugins
# ---------------------------------------------------------------------------
SKILLS_DIR = PROJECT_DIR / "skills"
SKILLS_ENABLED = os.getenv("SKILLS_ENABLED", "true").lower() == "true"

# ---------------------------------------------------------------------------
# JARVIS features
# ---------------------------------------------------------------------------
JARVIS_QUICK_ANSWERS = os.getenv("JARVIS_QUICK_ANSWERS", "true").lower() == "true"  # Instant responses for common queries
JARVIS_REMINDERS = os.getenv("JARVIS_REMINDERS", "true").lower() == "true"  # Reminder & timer system
JARVIS_PROACTIVE = os.getenv("JARVIS_PROACTIVE", "true").lower() == "true"  # Proactive system monitoring
JARVIS_NOTIFICATION_MIRROR = os.getenv("JARVIS_NOTIFICATION_MIRROR", "false").lower() == "true"  # Speak desktop notifications (requires dbus-python)
JARVIS_PERSONALITY = os.getenv("JARVIS_PERSONALITY", "true").lower() == "true"  # Enhanced personality mode

# ---------------------------------------------------------------------------
# OCR settings
# ---------------------------------------------------------------------------
OCR_ENGINE = os.getenv("OCR_ENGINE", "tesseract")  # tesseract, easyocr, auto (tesseract preferred, easyocr fallback)
OCR_CONFIDENCE_THRESHOLD = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "30.0"))  # minimum confidence % to include
OCR_SHOW_CONFIDENCE = os.getenv("OCR_SHOW_CONFIDENCE", "false").lower() == "true"  # include confidence per line

# Region presets for OCR (relative to screen dimensions)
OCR_REGION_PRESETS = {
    "top": {"top": 0, "left": 0, "width": 1.0, "height": 0.33},
    "bottom": {"top": 0.66, "left": 0, "width": 1.0, "height": 0.34},
    "left": {"top": 0, "left": 0, "width": 0.5, "height": 1.0},
    "right": {"top": 0, "left": 0.5, "width": 0.5, "height": 1.0},
    "center": {"top": 0.25, "left": 0.25, "width": 0.5, "height": 0.5},
    "top-left": {"top": 0, "left": 0, "width": 0.5, "height": 0.5},
    "top-right": {"top": 0, "left": 0.5, "width": 0.5, "height": 0.5},
    "bottom-left": {"top": 0.5, "left": 0, "width": 0.5, "height": 0.5},
    "bottom-right": {"top": 0.5, "left": 0.5, "width": 0.5, "height": 0.5},
}

# ---------------------------------------------------------------------------
# Safety
DANGEROUS_PATTERNS = [
    "rm -rf /", "rm -rf /*", "mkfs", "dd if=/dev/zero",
    ":(){ :|:& };:", "> /dev/sda", "format c:", "del /f /s /q",
    "shutdown -h now", "poweroff", "init 0",
]
REQUIRES_CONFIRMATION = [
    "rm -rf", "rm -r", "del ", "rmdir", "format",
    "shutdown", "reboot", "poweroff", "killall", "pkill",
    "chmod 000", "chown root", "mkfs", "fdisk",
]


# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = CACHE_DIR / "agent.log"
CRASH_LOG_FILE = CACHE_DIR / "crash.log"
