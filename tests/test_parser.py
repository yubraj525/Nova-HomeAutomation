# -*- coding: utf-8 -*-
"""Quick test for _safe_parse recovery logic."""
import sys
sys.path.insert(0, ".")

from app.llm.groq import _safe_parse

CASES = [
    # Truncated — response value cut mid-string (no closing quote or brace)
    ('truncated_casual',
     '{"type":"casual","response":"हजुरको छुट्टी त तीन दिन हो,'),
    ('truncated_query',
     '{"type":"query","response":"हजुर, तीन दिनको छुट्टीमा के-के रमाइलो'),
    # Valid JSON — should round-trip perfectly
    ('valid_json',
     '{"type":"casual","response":"ओहो, राम्रो!","convo":"के गर्ने?"}'),
    # Total garbage
    ('garbage',
     'not json at all'),
]

print("=" * 60)
print("_safe_parse recovery test")
print("=" * 60)

all_ok = True
for label, raw in CASES:
    result = _safe_parse(raw)
    resp   = result.get("response", "")
    typ    = result.get("type", "")

    # Assertions
    ok = True
    if label in ("truncated_casual", "truncated_query"):
        # Must recover a non-empty Nepali response (not the English error)
        if not resp or "Sorry" in resp or "couldn" in resp or "Could" in resp:
            ok = False
    if label == "valid_json":
        if resp != "ओहो, राम्रो!":
            ok = False
    if label == "garbage":
        # Must return Devanagari fallback
        if "Sorry" in resp or "couldn" in resp:
            ok = False

    status = "PASS" if ok else "FAIL"
    if not ok:
        all_ok = False

    print(f"  [{status}] {label}")
    print(f"         type={typ}  response={resp[:50]}")
    print()

print("=" * 60)
print("Result:", "ALL PASS" if all_ok else "SOME FAILED")
sys.exit(0 if all_ok else 1)
