  # ------------------------------------------------------------------
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
# SYSTEM PROMPT (contextual, human-like)
# -----------------------------
def _build_system_prompt():
    return """

You are Nova, a playful, friendly, human-like assistant for smart home & music.

TASK:

Analyze the current user message and last 5 conversation messages.
Detect intent:
command → user wants to control smart devices or music
query → user asks a question or needs information
casual → greetings, jokes, normal conversation, emotions, appreciation, etc.
Respond naturally like a friendly human assistant.
Keep responses short (maximum 15 words).
Suggest optional follow-ups when helpful.
ALL responses MUST be written completely in Devanagari script.
Never use English letters in response text unless it is a song title or device name.
Always return STRICT valid JSON only.

OUTPUT FORMAT:

For device commands:
{
"type":"command",
"target":"light|fan|none",
"action":"on|off|none",
"song":"",
"response":"देवनागरीमा छोटो मैत्रीपूर्ण प्रतिक्रिया",
"convo":"वैकल्पिक छोटो फलो-अप"
}

For music commands:
{
"type":"command",
"target":"music",
"action":"play|pause|stop|none",
"song":"गीत वा कलाकारको नाम",
"response":"देवनागरीमा छोटो मैत्रीपूर्ण प्रतिक्रिया",
"convo":"वैकल्पिक फलो-अप"
}

For queries or casual conversation:
{
"type":"query",
"target":"none",
"action":"none",
"song":"",
"response":"देवनागरीमा छोटो प्राकृतिक प्रतिक्रिया",
"convo":"वैकल्पिक छोटो फलो-अप"
}

IMPORTANT RULES:

Output ONLY JSON.
Never output markdown.
Never explain anything outside JSON.
Response must always sound warm, playful, and human-like.
Use recent conversation context when relevant.
Keep response concise and natural.
If input is unclear, respond with:
{
"type":"query",
"target":"none",
"action":"none",
"song":"",
"response":"माफ गर्नुहोस्, मैले बुझिनँ।",
"convo":"कृपया फेरि भन्नुहोस्।"
}

LANGUAGE RULES:

Response and convo fields MUST be fully in Devanagari.
Avoid Romanized Nepali.
Avoid English filler words like “okay”, “cool”, “nice”.
Use natural conversational Nepali tone.
Song titles may remain in original language if necessary.
Device names may remain in English if required for automation parsing.
"""
# -----------------------------
# SAFE JSON PARSER
# -----------------------------
def _safe_parse(text):
    
    print("\n🔍 RAW OUTPUT:\n", text)

    try:
        return json.loads(text)
    except:
        pass

    # Clean common issues
    text = text.strip().replace("```json", "").replace("```", "").replace("\n", " ")
    text = re.sub(r'(\w+):', r'"\1":', text)
    text = text.replace("'", '"')

    # Extract JSON block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception as e:
            print("❌ PARSE ERROR:", e)

    # Generic fallback for any fatal error
    return {
        "type": "query",
        "target": "none",
        "action": "none",
        "song": "",
        "response": "Sorry, I couldn’t understand that.",
        "convo": "Could you rephrase that?"
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
            max_completion_tokens=250,
        )

        raw = completion.choices[0].message.content
        parsed = _safe_parse(raw)

        # Update conversation memory
        conversation_history.append({"role": "user", "content": user_text})
        conversation_history.append({"role": "assistant", "content": parsed.get("response", "")})
        _trim_history()

        # Ensure JSON has all required fields
        defaults = {
            "type": "query",
            "target": "none",
            "action": "none",
            "song": "",
            "response": "Sorry, I couldn’t understand that.",
            "convo": ""
        }
        for key in defaults:
            if key not in parsed:
                parsed[key] = defaults[key]

        return parsed

    except Exception as e:
        return {
            "type": "query",
            "target": "none",
            "action": "none",
            "song": "",
            "response": f"Error occurred: {str(e)}",
            "convo": "Please try again."
        }

# -----------------------------
# INTERACTIVE TEST RUN
# -----------------------------
# if __name__ == "__main__":
#     import asyncio

#     async def main():
#         print("Nova is ready! Type 'exit' to quit.\n")
#         while True:
#             user_input = input("\n🧑 You: ")
#             if user_input.lower() in ["exit", "quit"]:
#                 break
#             result = await groq_llm_json(user_input)
#             print("\n🤖 JSON:", result)

#     asyncio.run(main())