"""
nepanglish_tts.py — Offline Nepanglish TTS Engine
==================================================
Handles Nepali, English, and mixed "Nepanglish" text.

Pipeline per sentence:
  1. Detect script of each token (Devanagari vs Latin)
  2. Transliterate Latin tokens → Devanagari phonetically
     (seed dictionary first, AI4Bharat if available, rule-based fallback)
  3. Normalise numbers (Latin + Devanagari → Nepali words)
  4. Synthesise with Piper ne_NP-google-medium via sherpa-onnx (CPU, offline)
  5. Stream audio chunk to playback

Quick test / REPL:
    python -m app.tts.nepanglish_tts
"""
from __future__ import annotations

import logging
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Generator, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_ROOT       = Path(__file__).resolve().parent.parent.parent
_MODEL_DIR  = _ROOT / "models" / "tts"
# Default: medium-int8 tarball (17 MB, near-medium quality, best Pi balance)
_DEFAULT_DIR  = _MODEL_DIR / "vits-piper-ne_NP-google-medium-int8"
_FALLBACK_DIR = _MODEL_DIR / "vits-piper-ne_NP-google-medium"
_FILLER_DIR = _ROOT / "assets" / "sounds" / "fillers"

# ---------------------------------------------------------------------------
# Seed dictionary  — common Nepanglish English → Devanagari
# ---------------------------------------------------------------------------
SEED: dict[str, str] = {
    # Tech / devices
    "robot": "रोबट", "speed": "स्पीड", "ac": "एसी", "wifi": "वाइफाइ",
    "internet": "इन्टरनेट", "phone": "फोन", "mobile": "मोबाइल",
    "computer": "कम्प्युटर", "laptop": "ल्यापटप", "camera": "क्यामेरा",
    "video": "भिडियो", "photo": "फोटो", "app": "एप", "software": "सफ्टवेयर",
    "data": "डाटा", "password": "पासवर्ड", "email": "इमेल",
    "message": "म्यासेज", "update": "अपडेट", "download": "डाउनलोड",
    "upload": "अपलोड", "battery": "ब्याट्री", "charge": "चार्ज",
    "screen": "स्क्रिन", "keyboard": "किबोर्ड", "server": "सर्भर",
    "network": "नेटवर्क", "sensor": "सेन्सर", "light": "लाइट",
    "fan": "फ्यान", "heater": "हिटर", "speaker": "स्पिकर",
    "microphone": "माइक्रोफोन", "mic": "माइक", "power": "पावर",
    "mode": "मोड", "volume": "भोलुम", "level": "लेभल",
    "reset": "रिसेट", "status": "स्टेटस", "error": "एरर",
    "bluetooth": "ब्लुटुथ", "led": "एलईडी", "usb": "यूएसबी",
    "gps": "जीपीएस", "ai": "एआई", "api": "एपीआई", "url": "यूआरएल",
    "nova": "नोभा", "temperature": "टेम्परेचर", "humidity": "हुमिडिटी",
    "timer": "टाइमर", "alarm": "अलार्म", "notification": "नोटिफिकेसन",
    # Actions
    "on": "अन", "off": "अफ", "start": "स्टार्ट", "stop": "स्टप",
    "play": "प्ले", "pause": "पज", "next": "नेक्स्ट", "back": "ब्याक",
    "open": "ओपन", "close": "क्लोज", "save": "सेभ", "delete": "डिलिट",
    "check": "चेक", "connect": "कनेक्ट", "call": "कल", "send": "सेन्ड",
    "share": "शेयर", "search": "सर्च", "cancel": "क्यान्सेल",
    "confirm": "कन्फर्म", "submit": "सबमिट", "login": "लगिन",
    "logout": "लगआउट", "set": "सेट", "get": "गेट",
    "manage": "म्यानेज", "control": "कन्ट्रोल", "press": "प्रेस",
    "mute": "म्युट", "unmute": "अनम्युट", "increase": "बढाउ",
    "decrease": "घटाउ", "print": "प्रिन्ट", "copy": "कपी",
    "paste": "पेस्ट", "zoom": "जुम",
    # Common nouns / adjectives
    "class": "क्लास", "school": "स्कुल", "college": "कलेज",
    "office": "अफिस", "meeting": "मिटिङ", "project": "प्रोजेक्ट",
    "report": "रिपोर्ट", "result": "रिजल्ट", "exam": "एग्जाम",
    "test": "टेस्ट", "bus": "बस", "bike": "बाइक", "car": "कार",
    "taxi": "ट्याक्सी", "hotel": "होटल", "market": "मार्केट",
    "bank": "बैंक", "bill": "बिल", "account": "एकाउन्ट",
    "problem": "प्रब्लेम", "idea": "आइडिया", "plan": "प्लान",
    "list": "लिस्ट", "time": "टाइम", "news": "न्युज", "game": "गेम",
    "team": "टिम", "match": "म्याच", "music": "म्युजिक", "song": "सङ",
    "movie": "मुभी", "film": "फिल्म", "channel": "च्यानल",
    "program": "प्रोग्राम", "show": "शो", "live": "लाइभ",
    "file": "फाइल", "folder": "फोल्डर",
    "good": "गुड", "bad": "ब्याड", "nice": "नाइस", "cool": "कुल",
    "best": "बेस्ट", "fast": "फास्ट", "slow": "स्लो",
    "new": "न्यु", "old": "ओल्ड", "big": "बिग", "small": "स्माल",
    "hot": "हट", "cold": "कोल्ड", "up": "अप", "down": "डाउन",
    "left": "लेफ्ट", "right": "राइट", "high": "हाइ", "low": "लो",
    "max": "म्याक्स", "min": "मिन", "total": "टोटल",
    "number": "नम्बर", "percent": "प्रतिशत", "location": "लोकेसन",
    "ready": "रेडी", "active": "एक्टिभ", "normal": "नर्मल",
    "success": "सक्सेस", "fail": "फेल", "warning": "वार्निङ",
    "common": "कमन", "conversation": "कन्भर्सेसन",
    # Greetings / polite
    "hello": "हेलो", "hi": "हाइ", "bye": "बाइ", "ok": "ओके",
    "okay": "ओके", "yes": "यस", "no": "नो", "sorry": "सरी",
    "thanks": "थ्याङ्क्स", "thank": "थ्याङ्क", "please": "प्लिज",
    "sure": "श्योर", "how": "हाउ", "are": "आर", "you": "यु",
    "what": "व्हाट", "where": "वेयर", "when": "वेन", "why": "वाइ",
}


# ---------------------------------------------------------------------------
# Rule-based phonetic transliterator  (English graphemes → Devanagari)
# ---------------------------------------------------------------------------

# Ordered cluster rules applied left-to-right
_CLUSTERS: list[tuple[str, str]] = [
    ("sh", "श"), ("ch", "च"), ("th", "थ"), ("ph", "फ"),
    ("gh", "घ"), ("kh", "ख"), ("ck", "क"), ("qu", "क्व"),
    ("tr", "ट्र"), ("pr", "प्र"), ("br", "ब्र"), ("gr", "ग्र"),
    ("dr", "ड्र"), ("fr", "फ्र"), ("sw", "स्व"), ("sp", "स्प"),
    ("st", "स्ट"), ("sk", "स्क"), ("sl", "स्ल"), ("sm", "स्म"),
    ("sn", "स्न"), ("ee", "ी"), ("ea", "ी"), ("oo", "ू"),
    ("ai", "ै"), ("ay", "ाइ"), ("oa", "ो"), ("ow", "ो"),
    ("ou", "आउ"), ("ie", "ी"), ("ue", "ु"), ("ew", "्यु"),
    ("wh", "व"), ("wr", "र"),
    # Singles
    ("a", "ा"), ("e", "े"), ("i", "ि"), ("o", "ो"), ("u", "ु"),
    ("b", "ब"), ("c", "क"), ("d", "ड"), ("f", "फ"),
    ("g", "ग"), ("h", "ह"), ("j", "ज"), ("k", "क"),
    ("l", "ल"), ("m", "म"), ("n", "न"), ("p", "प"),
    ("q", "क"), ("r", "र"), ("s", "स"), ("t", "ट"),
    ("v", "भ"), ("w", "व"), ("x", "क्स"), ("y", "य"), ("z", "ज"),
]

# Devanagari vowel matras (ा ि ी ु ू े ै ो ौ)
_MATRAS = set("ािीुूेैोौं")


def _rule_transliterate(word: str) -> str:
    """Convert a single English word to Devanagari via grapheme rules."""
    src = word.lower()
    out: list[str] = []
    i = 0
    prev_was_consonant = False

    while i < len(src):
        matched = False
        for cluster, deva in _CLUSTERS:
            if src[i:i + len(cluster)] == cluster:
                syllable = deva
                # If this is a matra (vowel modifier) and previous was a
                # consonant, attach directly; otherwise prefix with अ
                if syllable in _MATRAS:
                    if not prev_was_consonant:
                        syllable = {
                            "ा": "आ", "ि": "इ", "ी": "ई",
                            "ु": "उ", "ू": "ऊ", "े": "ए",
                            "ै": "ऐ", "ो": "ओ", "ौ": "औ",
                        }.get(syllable, syllable)
                    prev_was_consonant = False
                else:
                    # It's a consonant cluster — add inherent 'a' suppressor
                    # only if followed by another consonant with no vowel in between
                    prev_was_consonant = True
                out.append(syllable)
                i += len(cluster)
                matched = True
                break

        if not matched:
            i += 1  # skip unrecognised char

    result = "".join(out)
    # If result ends with a bare consonant, it already has inherent 'a' in Devanagari
    return result if result else word


# ---------------------------------------------------------------------------
# AI4Bharat optional integration
# ---------------------------------------------------------------------------

_ai4bharat_engine = None
_ai4bharat_tried  = False


def _try_load_ai4bharat() -> bool:
    global _ai4bharat_engine, _ai4bharat_tried
    if _ai4bharat_tried:
        return _ai4bharat_engine is not None
    _ai4bharat_tried = True
    try:
        from ai4bharat.transliteration import XlitEngine  # type: ignore
        _ai4bharat_engine = XlitEngine("ne", beam_width=4, src_script_type="Roman")
        logger.info("AI4Bharat transliterator loaded ✓")
        return True
    except Exception:
        logger.debug("AI4Bharat not available — using rule-based fallback")
        return False


def _ai4bharat_transliterate(word: str) -> str:
    try:
        result = _ai4bharat_engine.translit_word(word, topk=1)
        return result.get("ne", [word])[0]
    except Exception:
        return _rule_transliterate(word)


# ---------------------------------------------------------------------------
# Public transliteration entry-point
# ---------------------------------------------------------------------------

def transliterate_word(word: str) -> str:
    """
    Return the best Devanagari rendering of a single Latin word.
    Priority: seed dict → AI4Bharat (if installed) → rule-based.
    """
    lower = word.lower()
    if lower in SEED:
        return SEED[lower]
    if _try_load_ai4bharat():
        return _ai4bharat_transliterate(lower)
    return _rule_transliterate(lower)


# ---------------------------------------------------------------------------
# Number normalisation (Nepali words)
# ---------------------------------------------------------------------------

_ONES = [
    "", "एक", "दुई", "तीन", "चार", "पाँच",
    "छ", "सात", "आठ", "नौ", "दश", "एघार",
    "बाह्र", "तेह्र", "चौध", "पन्ध्र", "सोह्र",
    "सत्र", "अठार", "उन्नाइस",
]
_TENS = [
    "", "", "बीस", "तीस", "चालीस", "पचास",
    "साठी", "सत्तरी", "असी", "नब्बे",
]

# Devanagari digit → ASCII
_DEVA_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _number_to_nepali(n: int) -> str:
    if n == 0:
        return "शून्य"
    if n < 0:
        return "माइनस " + _number_to_nepali(-n)
    parts: list[str] = []
    crore = n // 10_000_000
    if crore:
        parts.append(_number_to_nepali(crore) + " करोड")
        n %= 10_000_000
    lakh = n // 100_000
    if lakh:
        parts.append(_number_to_nepali(lakh) + " लाख")
        n %= 100_000
    hajar = n // 1000
    if hajar:
        parts.append(_number_to_nepali(hajar) + " हजार")
        n %= 1000
    say = n // 100
    if say:
        parts.append((_ones := _ONES[say] + " " if say > 1 else "") + "सय")
        n %= 100
    if n >= 20:
        t, o = divmod(n, 10)
        parts.append(_TENS[t] + (" " + _ONES[o] if o else ""))
    elif n:
        parts.append(_ONES[n])
    return " ".join(p for p in parts if p.strip())


def _normalise_numbers(text: str) -> str:
    """Replace Devanagari and Latin number sequences with spoken Nepali words."""
    # Devanagari digits → ASCII first
    text = text.translate(_DEVA_DIGITS)
    # Replace standalone numbers
    def _repl(m: re.Match) -> str:
        try:
            return _number_to_nepali(int(m.group()))
        except ValueError:
            return m.group()
    return re.sub(r"\d+", _repl, text)


# ---------------------------------------------------------------------------
# Text preprocessing
# ---------------------------------------------------------------------------

_PUNCT_CLEAN = [
    (r"[""\"«»]",         '"'),
    (r"[''`]",            "'"),
    (r"[—–]",             ", "),
    (r"\.{2,}",           "।"),
    (r"[^\S\n]{2,}",      " "),
]


def _clean_text(text: str) -> str:
    for pat, repl in _PUNCT_CLEAN:
        text = re.sub(pat, repl, text)
    return text.strip()


def _is_devanagari(ch: str) -> bool:
    return "\u0900" <= ch <= "\u097f"


def _is_latin_word(tok: str) -> bool:
    """True if the token is predominantly ASCII letters."""
    letters = [c for c in tok if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if ord(c) < 128) / len(letters) > 0.5


def transliterate_mixed(text: str) -> str:
    """
    Take a mixed Nepali+English string, transliterate English tokens to
    Devanagari, return the fully Devanagari string ready for Piper.
    """
    tokens = re.split(r"(\s+)", text)
    out: list[str] = []
    for tok in tokens:
        if tok.isspace() or not tok:
            out.append(tok)
        elif _is_latin_word(tok):
            # Strip surrounding punctuation, transliterate core
            pre  = re.match(r"^[^\w]*", tok).group()
            post = re.search(r"[^\w]*$", tok).group()
            core = tok[len(pre):len(tok) - len(post) if post else len(tok)]
            out.append(pre + transliterate_word(core) + post)
        else:
            out.append(tok)
    return "".join(out)


# ---------------------------------------------------------------------------
# Sentence splitter
# ---------------------------------------------------------------------------

_SENT_RE = re.compile(r"(?<=[।.!?])\s+|(?<=[।!?])(?=[^\s])")


def split_sentences(text: str) -> list[str]:
    parts = _SENT_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Piper ONNX synthesiser via sherpa-onnx
# ---------------------------------------------------------------------------

class NepanglishTTS:
    """
    Offline Nepanglish TTS using Piper ne_NP via sherpa-onnx.

    The model directory must contain:
      model.onnx, tokens.txt, espeak-ng-data/

    Download with:  python scripts/download_tts_model.py

    Usage::
        synth = NepanglishTTS()
        audio = synth.synthesize("यो robot को speed बढाउ।")
        for chunk in synth.synthesize_stream("नमस्ते। Fine, thank you।"):
            play(chunk)
    """

    def __init__(
        self,
        model_dir: Optional[Path] = None,
        num_threads: int = 2,
        speed: float = 1.0,
    ):
        # Auto-locate: prefer caller's choice, then int8, then full medium
        if model_dir is not None:
            self.model_dir = Path(model_dir)
        elif list(_DEFAULT_DIR.glob("*.onnx")):
            self.model_dir = _DEFAULT_DIR
        elif list(_FALLBACK_DIR.glob("*.onnx")):
            self.model_dir = _FALLBACK_DIR
        else:
            self.model_dir = _DEFAULT_DIR   # will give a clear error in _load()
        self.num_threads = num_threads
        self.speed       = speed
        self._tts        = None   # lazy-loaded
        self.sample_rate = 22050  # updated after _load()

    # ------------------------------------------------------------------
    def _load(self):
        if self._tts is not None:
            return
        # The ONNX may be named model.onnx or ne_NP-*.onnx depending on tarball
        onnx_files  = list(self.model_dir.glob("*.onnx"))
        tokens_path = self.model_dir / "tokens.txt"
        data_dir    = self.model_dir / "espeak-ng-data"

        if not onnx_files:
            raise FileNotFoundError(
                f"No .onnx file found in {self.model_dir}\n"
                "Run:  python scripts/download_tts_model.py"
            )
        missing = [p for p in (tokens_path, data_dir) if not p.exists()]
        if missing:
            raise FileNotFoundError(
                f"Piper model incomplete in {self.model_dir}\n"
                f"Missing: {[p.name for p in missing]}\n"
                "Run:  python scripts/download_tts_model.py"
            )
        try:
            import sherpa_onnx  # type: ignore
        except ImportError:
            raise ImportError("sherpa-onnx not installed.  pip install sherpa-onnx")

        onnx_path = onnx_files[0]
        logger.info("Loading Piper model: %s", onnx_path.name)

        vits_cfg = sherpa_onnx.OfflineTtsVitsModelConfig(
            model    = str(onnx_path),
            lexicon  = "",
            tokens   = str(tokens_path),
            data_dir = str(data_dir),
        )
        model_cfg = sherpa_onnx.OfflineTtsModelConfig(
            vits        = vits_cfg,
            provider    = "cpu",
            debug       = False,
            num_threads = self.num_threads,
        )
        tts_cfg = sherpa_onnx.OfflineTtsConfig(
            model             = model_cfg,
            rule_fsts         = "",
            max_num_sentences = 1,
        )
        self._tts        = sherpa_onnx.OfflineTts(tts_cfg)
        self.sample_rate = self._tts.sample_rate
        logger.info("Piper ne_NP loaded  sr=%d", self.sample_rate)

    # ------------------------------------------------------------------
    def _preprocess(self, text: str) -> str:
        text = _clean_text(text)
        text = _normalise_numbers(text)
        text = transliterate_mixed(text)
        return text

    # ------------------------------------------------------------------
    def synthesize(self, text: str) -> np.ndarray:
        """Synthesise the full text; return float32 numpy array."""
        self._load()
        processed = self._preprocess(text)
        logger.debug("Synthesising: %s", processed)
        audio = self._tts.generate(processed, sid=0, speed=self.speed)
        return np.array(audio.samples, dtype=np.float32)

    # ------------------------------------------------------------------
    def synthesize_stream(self, text: str) -> Generator[np.ndarray, None, None]:
        """
        Yield one float32 numpy chunk per sentence.
        Low time-to-first-word even for long inputs.
        """
        self._load()
        sentences = split_sentences(text) or [text]
        for sent in sentences:
            processed = self._preprocess(sent)
            if not processed.strip():
                continue
            audio = self._tts.generate(processed, sid=0, speed=self.speed)
            yield np.array(audio.samples, dtype=np.float32)


# ---------------------------------------------------------------------------
# Module-level singleton + convenience API
# ---------------------------------------------------------------------------

_synth: Optional[NepanglishTTS] = None


def get_synthesizer() -> NepanglishTTS:
    global _synth
    if _synth is None:
        _synth = NepanglishTTS()
    return _synth


def speak(text: str, filler: Optional[str] = None, speed: float = 1.0):
    """
    Speak *text* (Nepali, English, or mixed) — blocks until done.
    Optionally plays a pre-rendered filler sound first.
    """
    if filler:
        try:
            from app.tts.fillers import play_filler
            play_filler(filler)
        except Exception:
            pass

    synth = get_synthesizer()
    synth.speed = speed

    try:
        import sounddevice as sd  # type: ignore
        for chunk in synth.synthesize_stream(text):
            sd.play(chunk, samplerate=synth.sample_rate, blocking=True)
    except Exception as exc:
        logger.warning("sounddevice failed (%s) — trying pygame fallback", exc)
        _pygame_fallback(synth, text)


def _pygame_fallback(synth: NepanglishTTS, text: str):
    """Save to temp WAV and play via pygame (fallback if sounddevice unavailable)."""
    import tempfile, wave, struct
    try:
        import pygame  # type: ignore
    except ImportError:
        logger.error("Neither sounddevice nor pygame available — no audio output")
        return

    samples_all = synth.synthesize(text)
    pcm = (np.clip(samples_all, -1, 1) * 32767).astype(np.int16).tobytes()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name

    with wave.open(tmp, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(synth.sample_rate)
        wf.writeframes(pcm)

    pygame.mixer.init()
    pygame.mixer.music.load(tmp)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.05)
    pygame.mixer.music.unload()
    os.unlink(tmp)


# ---------------------------------------------------------------------------
# CLI REPL
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    print("Nepanglish TTS  —  type a sentence and press Enter.  'quit' to exit.")
    print("Slash commands:  /transliterate <text>  /version\n")
    synth = get_synthesizer()  # pre-load model
    while True:
        try:
            line = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if not line:
            continue
        if line in ("quit", "q", "exit"):
            break
        if line.startswith("/transliterate "):
            print(transliterate_mixed(line[15:]))
            continue
        if line == "/version":
            print("sherpa-onnx:", end=" ")
            try:
                import sherpa_onnx; print(sherpa_onnx.__version__)
            except Exception:
                print("not installed")
            continue
        speak(line)
