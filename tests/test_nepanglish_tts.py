"""
test_nepanglish_tts.py — Unit + integration tests for Nepanglish TTS
======================================================================
Run:
    python -m pytest tests/test_nepanglish_tts.py -v

Integration tests (marked 'integration') require the Piper model to be
downloaded first:
    python scripts/download_tts_model.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make sure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ===========================================================================
# Transliterator unit tests  (no model needed)
# ===========================================================================

class TestSeedDictionary:
    def test_known_word_robot(self):
        from app.tts.nepanglish_tts import transliterate_word
        assert transliterate_word("robot") == "रोबट"

    def test_known_word_speed(self):
        from app.tts.nepanglish_tts import transliterate_word
        assert transliterate_word("speed") == "स्पीड"

    def test_known_word_case_insensitive(self):
        from app.tts.nepanglish_tts import transliterate_word
        assert transliterate_word("ROBOT") == transliterate_word("robot")

    def test_known_word_ac(self):
        from app.tts.nepanglish_tts import transliterate_word
        assert transliterate_word("ac") == "एसी"

    def test_known_word_light(self):
        from app.tts.nepanglish_tts import transliterate_word
        assert transliterate_word("light") == "लाइट"

    def test_known_word_on(self):
        from app.tts.nepanglish_tts import transliterate_word
        assert transliterate_word("on") == "अन"

    def test_known_word_off(self):
        from app.tts.nepanglish_tts import transliterate_word
        assert transliterate_word("off") == "अफ"


class TestMixedTransliteration:
    def test_pure_devanagari_unchanged(self):
        from app.tts.nepanglish_tts import transliterate_mixed
        text = "नमस्ते, कस्तो छ?"
        assert transliterate_mixed(text) == text

    def test_english_token_replaced(self):
        from app.tts.nepanglish_tts import transliterate_mixed
        result = transliterate_mixed("यो robot हो")
        assert "robot" not in result
        assert "रोबट" in result

    def test_mixed_sentence(self):
        from app.tts.nepanglish_tts import transliterate_mixed
        result = transliterate_mixed("यो robot को speed बढाउ")
        assert "रोबट" in result
        assert "स्पीड" in result
        assert "बढाउ" in result

    def test_pure_english_converted(self):
        from app.tts.nepanglish_tts import transliterate_mixed
        result = transliterate_mixed("Hello, how are you?")
        # All tokens should be Devanagari or punctuation
        assert "Hello" not in result


class TestNumberNormalisation:
    def test_zero(self):
        from app.tts.nepanglish_tts import _normalise_numbers
        assert "शून्य" in _normalise_numbers("0")

    def test_single_digit(self):
        from app.tts.nepanglish_tts import _normalise_numbers
        assert "एक" in _normalise_numbers("1")
        assert "पाँच" in _normalise_numbers("5")

    def test_two_digits(self):
        from app.tts.nepanglish_tts import _normalise_numbers
        assert "बीस" in _normalise_numbers("20")

    def test_thousands(self):
        from app.tts.nepanglish_tts import _normalise_numbers
        result = _normalise_numbers("1500")
        assert "हजार" in result

    def test_devanagari_digits(self):
        from app.tts.nepanglish_tts import _normalise_numbers
        result = _normalise_numbers("२०२४")
        # Devanagari digits should be converted to Nepali words
        assert "२" not in result

    def test_number_in_sentence(self):
        from app.tts.nepanglish_tts import _normalise_numbers
        result = _normalise_numbers("मसँग 100 रुपैयाँ छ।")
        assert "100" not in result
        assert "सय" in result


class TestSentenceSplitter:
    def test_split_on_danda(self):
        from app.tts.nepanglish_tts import split_sentences
        parts = split_sentences("नमस्ते। कस्तो छ?")
        assert len(parts) == 2

    def test_split_on_period(self):
        from app.tts.nepanglish_tts import split_sentences
        parts = split_sentences("Hello. How are you?")
        assert len(parts) == 2

    def test_single_sentence(self):
        from app.tts.nepanglish_tts import split_sentences
        parts = split_sentences("नमस्ते")
        assert parts == ["नमस्ते"]

    def test_empty_string(self):
        from app.tts.nepanglish_tts import split_sentences
        assert split_sentences("") == []


# ===========================================================================
# Integration tests  (require model; skip gracefully if not present)
# ===========================================================================

@pytest.mark.integration
class TestSynthesis:
    """Require Piper model.  Skip with:  pytest -m 'not integration'"""

    @pytest.fixture(autouse=True)
    def _check_model(self):
        model = Path(__file__).resolve().parent.parent / "models" / "tts" / "ne_NP-google-medium.onnx"
        if not model.exists():
            pytest.skip("Piper model not downloaded — run: python scripts/download_tts_model.py")

    def test_synthesize_pure_nepali(self):
        from app.tts.nepanglish_tts import NepanglishTTS
        import numpy as np
        synth = NepanglishTTS()
        audio = synth.synthesize("नमस्ते, कस्तो छ?")
        assert isinstance(audio, np.ndarray)
        assert len(audio) > 100

    def test_synthesize_mixed_nepanglish(self):
        from app.tts.nepanglish_tts import NepanglishTTS
        import numpy as np
        synth = NepanglishTTS()
        audio = synth.synthesize("यो robot को speed बढाउ")
        assert isinstance(audio, np.ndarray)
        assert len(audio) > 100

    def test_synthesize_pure_english(self):
        from app.tts.nepanglish_tts import NepanglishTTS
        import numpy as np
        synth = NepanglishTTS()
        audio = synth.synthesize("Hello, how are you?")
        assert isinstance(audio, np.ndarray)
        assert len(audio) > 100

    def test_stream_yields_chunks(self):
        from app.tts.nepanglish_tts import NepanglishTTS
        synth  = NepanglishTTS()
        chunks = list(synth.synthesize_stream("नमस्ते। कस्तो छ? Fine, thank you।"))
        assert len(chunks) >= 1
        for chunk in chunks:
            assert len(chunk) > 10

    def test_wav_output_from_tts_engine(self, tmp_path):
        """Smoke-test the full tts_engine pipeline."""
        import asyncio
        from app.tts.tts_engine import _synthesize_to_wav
        path = _synthesize_to_wav("नमस्ते, मेरो नाम नोवा हो।")
        assert Path(path).exists()
        assert Path(path).stat().st_size > 1000
