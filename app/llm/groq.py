import asyncio
import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

from app.face.context import build_face_context, build_unknown_context
from app.face.person_memory import get_memory

load_dotenv()
client = Groq(api_key=os.getenv("GROQ"))

MAX_HISTORY = 5

_unknown_history: list[dict] = []
_current_face_context = ""
_current_face_id: str | None = None


def set_face_context(context: str, face_id: str | None = None):
    global _current_face_context, _current_face_id
    _current_face_context = context
    _current_face_id = face_id


def _history_for_prompt() -> list[dict]:
    if _current_face_id:
        mem = get_memory().get(_current_face_id)
        hist = mem.get("history", [])[-(MAX_HISTORY * 2):]
        return [{"role": h["role"], "content": h["content"]} for h in hist]
    return list(_unknown_history[-(MAX_HISTORY * 2):])


def _record_exchange(user_text: str, assistant_text: str):
    if _current_face_id:
        get_memory().add_history(_current_face_id, user_text, assistant_text)
        return
    _unknown_history.append({"role": "user", "content": user_text})
    _unknown_history.append({"role": "assistant", "content": assistant_text})
    if len(_unknown_history) > MAX_HISTORY * 2:
        del _unknown_history[: len(_unknown_history) - MAX_HISTORY * 2]


def _build_system_prompt():
    face = _current_face_context
    is_unknown = (face == "") or (not _current_face_id)
    face_section = ""
    if face:
        face_section = f"""
CONTEXT ABOUT PERSON IN FRONT OF YOU:
{face}

Use this context naturally. If it's a known person, greet them by name and reference past conversations if relevant. If it's an unknown person, be warm and welcoming.

"""
    elif is_unknown:
        face_section = f"""
CONTEXT ABOUT PERSON IN FRONT OF YOU:
{build_unknown_context()}

If you do not know their name yet, ask politely so we can register them.

"""

    return f"""
You are Nova, a playful, friendly, human-like assistant for an exhibition welcome bot.
{face_section}
TASK:
1. Analyze the user message and the last 5 exchanges of history.
2. Detect intent and produce ONE strict JSON object.

INTENT TYPES:
   - command  : user wants to control a device or music
   - query    : user asks a question or makes a casual comment
   - register : the speaker is unknown and either (a) we need to ask for their name, or (b) they just told us their name and we should remember them
   - conversation_continue : user is continuing a prior conversation naturally (no new intent to classify)
   - followup_question : user asks a follow-up to the previous topic
   - session_end : user signals they are leaving or done talking (e.g. "bye", "I'm leaving", "see you")
   - memory_update : user shares personal info that should be remembered (e.g. "I like AI", "I'm from Pokhara")

3. Keep the spoken `response` casual, human-like, short (max 15 words).
4. Use `convo` only for an optional natural follow-up.

OUTPUT FORMAT:

Device commands (light/fan):
{{
  "type":"command",
  "target":"light|fan|none",
  "action":"on|off|none",
  "song":"",
  "name":"",
  "response":"friendly short reply",
  "convo":"optional follow-up"
}}

Music commands:
{{
  "type":"command",
  "target":"music",
  "action":"play|pause|stop|resume|none",
  "song":"song title or artist",
  "name":"",
  "response":"friendly short reply",
  "convo":"optional follow-up"
}}

Queries / casual comments:
{{
  "type":"query",
  "target":"none",
  "action":"none",
  "song":"",
  "name":"",
  "response":"friendly short reply",
  "convo":"optional follow-up"
}}

Register (unknown visitor):
- If you still need their name, leave "name":"" and ask for it in `response`.
- If they just told you their name in the message, put it in "name" and confirm warmly in `response`.
{{
  "type":"register",
  "target":"none",
  "action":"none",
  "song":"",
  "name":"captured name or empty",
  "response":"friendly short reply",
  "convo":"optional follow-up"
}}

Conversation continue (user continuing naturally, no special intent):
{{
  "type":"conversation_continue",
  "target":"none",
  "action":"none",
  "song":"",
  "name":"",
  "response":"friendly reply continuing the chat",
  "convo":"optional follow-up"
}}

Follow-up question (user asking more about the previous topic):
{{
  "type":"followup_question",
  "target":"none",
  "action":"none",
  "song":"",
  "name":"",
  "response":"friendly reply to the follow-up",
  "convo":"optional follow-up question back"
}}

Session end (user says goodbye):
{{
  "type":"session_end",
  "target":"none",
  "action":"none",
  "song":"",
  "name":"",
  "response":"warm goodbye message",
  "convo":""
}}

Memory update (user shares info to remember):
{{
  "type":"memory_update",
  "target":"none",
  "action":"none",
  "song":"",
  "name":"",
  "response":"I'll remember that!",
  "convo":"optional follow-up"
}}

RULES:
- Output JSON only — no markdown, no extra text always reply in nepalii devnagari in response .
- Always include `type` and `response`.
- Use the conversation history to make replies feel personal.
- Match the user's language style (English / Nepali / Romanized Nepali / Nepanglish). Never switch on your own .
- For confusing input return: {{"type":"query","target":"none","action":"none","song":"","name":"","response":"Sorry, didn't understand.","convo":"Please rephrase."}}
"""


def _safe_parse(text):
    print("\nRAW OUTPUT:\n", text)

    try:
        return json.loads(text)
    except Exception:
        pass

    text = text.strip().replace("```json", "").replace("```", "").replace("\n", " ")
    text = re.sub(r'(\w+):', r'"\1":', text)
    text = text.replace("'", '"')

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception as e:
            print("PARSE ERROR:", e)

    return {
        "type": "query",
        "target": "none",
        "action": "none",
        "song": "",
        "name": "",
        "response": "Sorry, I couldn't understand that.",
        "convo": "Could you rephrase that?",
    }


async def groq_llm_json(user_text: str):
    messages = [{"role": "system", "content": _build_system_prompt()}]
    messages += _history_for_prompt()
    messages.append({"role": "user", "content": user_text})

    try:
        completion = await asyncio.to_thread(
            client.chat.completions.create,
            model="openai/gpt-oss-120b",
            messages=messages,
            temperature=0.5,
            max_completion_tokens=250,
        )

        raw = completion.choices[0].message.content
        parsed = _safe_parse(raw)

        defaults = {
            "type": "query",
            "target": "none",
            "action": "none",
            "song": "",
            "name": "",
            "response": "Sorry, I couldn't understand that.",
            "convo": "",
        }
        for key, val in defaults.items():
            parsed.setdefault(key, val)

        _record_exchange(user_text, parsed.get("response", ""))

        return parsed

    except Exception as e:
        return {
            "type": "query",
            "target": "none",
            "action": "none",
            "song": "",
            "name": "",
            "response": f"Error occurred: {str(e)}",
            "convo": "Please try again.",
        }