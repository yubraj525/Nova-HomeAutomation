import os
import json
import re
from groq import Groq
from dotenv import load_dotenv

# -----------------------------
# INIT
# -----------------------------
load_dotenv()
client = Groq(api_key=os.getenv("GROQ"))

# -----------------------------
# CONFIG
# -----------------------------
MAX_HISTORY = 5

# -----------------------------
# MEMORY (conversation context)
# -----------------------------
conversation_history = []

def _trim_history():
    global conversation_history
    conversation_history = conversation_history[-MAX_HISTORY:]

# -----------------------------
# SYSTEM PROMPT
# -----------------------------
def _build_system_prompt():
    return """
You are Nova — a fully extroverted, emotionally expressive, ultra-natural Nepali conversational AI.

Nova should NOT sound like an assistant.
Nova should sound like a real cheerful Nepali person casually talking in daily life.

Core personality:
- highly social, emotionally alive, playful, talkative
- warm, expressive, naturally curious, respectful and caring

Conversation style:
- talk like close Nepali friends/family
- naturally continue conversations with fillers and reactions
- feel spontaneous and human
- responses should sound like real voice conversations

Examples of tone:
- "ओहो, उठिसक्नुभयो हजुर? शुभ प्रभात है।"
- "आज त निकै राम्रो मुडमा हुनुहुन्छ जस्तो लाग्यो नि।"
- "के छ खबर हजुरको?"

Important:
- never give dry replies
- always make the conversation feel alive and flowing
- avoid robotic assistant-style confirmations
- avoid overly formal Nepali
- avoid repetitive sentence structures

Language rules:
- ALL responses MUST be fully in Devanagari Nepali
- never use Romanized Nepali or English filler words
- use mostly "tapai", "hajur", "hai", "ni" — but written in Devanagari

Voice optimization:
- responses must sound realistic when spoken by TTS
- prioritize conversational rhythm and warmth
- make sentences feel naturally speakable aloud

Keep responses short, expressive, natural, human-like.

Always return STRICT valid JSON only. No markdown, no explanation outside JSON.

Format:
{
"type":"casual|query|command",
"response":"short natural Devanagari response",
"convo":"warm follow-up or next conversation move"
}

If user input is unclear:
{
"type":"query",
"response":"हजुर, अलि फेरि भन्नुहुन्छ?",
"convo":"म सुन्दैछु है।"
}
"""

# -----------------------------
# SAFE JSON PARSER
# -----------------------------
def _safe_parse(text: str) -> dict:
    print("\n RAW OUTPUT:\n", text)

    stripped = text.strip().replace("```json", "").replace("```", "")

    # 1. Clean full parse
    try:
        return json.loads(stripped)
    except Exception:
        pass

    # 2. Extract first {...} block (handles leading/trailing noise)
    m = re.search(r"\{.*\}", stripped, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass

    # 3. Truncated-JSON recovery
    #    Fires when Devanagari tokens exhaust max_completion_tokens and the
    #    closing `"}` is never written.  Pull out whatever fields exist.
    partial_type = "query"
    mt = re.search(r'"type"\s*:\s*"([^"]+)"', stripped)
    if mt:
        partial_type = mt.group(1)

    # Grab response field — may or may not have closing quote
    mr = re.search(r'"response"\s*:\s*"([^"]*)"?', stripped)
    if mr:
        partial_resp = mr.group(1).rstrip(", \t")
        if partial_resp:
            print("  [parser] partial response recovered from truncated JSON")
            return {
                "type":     partial_type,
                "target":   "none",
                "action":   "none",
                "song":     "",
                "response": partial_resp,
                "convo":    ""
            }

    # 4. Total fallback — Devanagari only
    print("  [parser] could not parse LLM output — using Devanagari fallback")
    return {
        "type":     "query",
        "target":   "none",
        "action":   "none",
        "song":     "",
        "response": "\u0939\u091c\u0941\u0930, \u090f\u0915\u091a\u094b\u091f\u093f \u092b\u0947\u0930\u093f \u092d\u0928\u094d\u0928\u0941\u0939\u0941\u0928\u094d\u091b?",  # हजुर, एकचोटि फेरि भन्नुहुन्छ?
        "convo":    "\u092e \u0938\u0941\u0928\u094d\u0926\u0948\u091b\u0941 \u0939\u0948\u0964"  # म सुन्दैछु है।
    }


# -----------------------------
# CORE FUNCTION: context + JSON
# -----------------------------
async def groq_llm_json(user_text: str):
    global conversation_history

    messages = [
        {"role": "system", "content": _build_system_prompt()}
    ]
    messages += conversation_history
    messages.append({"role": "user", "content": user_text})

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=messages,
            temperature=0.5,
            max_completion_tokens=400,  # raised: Devanagari chars are token-heavy
        )

        raw    = completion.choices[0].message.content
        parsed = _safe_parse(raw)

        # Update conversation memory
        conversation_history.append({"role": "user",      "content": user_text})
        conversation_history.append({"role": "assistant", "content": parsed.get("response", "")})
        _trim_history()

        # Ensure all required fields exist (never leave a missing key)
        defaults = {
            "type":     "query",
            "target":   "none",
            "action":   "none",
            "song":     "",
            "response": "\u0939\u091c\u0941\u0930, \u090f\u0915\u091a\u094b\u091f\u093f \u092b\u0947\u0930\u093f \u092d\u0928\u094d\u0928\u0941\u0939\u0941\u0928\u094d\u091b?",
            "convo":    ""
        }
        for key, val in defaults.items():
            if key not in parsed:
                parsed[key] = val

        return parsed

    except Exception as e:
        return {
            "type":     "query",
            "target":   "none",
            "action":   "none",
            "song":     "",
            "response": "\u092e\u093e\u092b \u0917\u0930\u094d\u0928\u0941\u0938\u094d, \u0915\u0947\u0939\u0940 \u0917\u0921\u092c\u0921\u0940 \u092d\u092f\u094b\u0964",   # माफ गर्नुस्, केही गडबडी भयो।
            "convo":    "\u0915\u0943\u092a\u092f\u093e \u092b\u0947\u0930\u093f \u092a\u094d\u0930\u092f\u093e\u0938 \u0917\u0930\u094d\u0928\u0941\u0939\u094b\u0938\u094d\u0964"  # कृपया फेरि प्रयास गर्नुहोस्।
        }