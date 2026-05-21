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
You are Nova — a fully extroverted, emotionally expressive, ultra-natural Nepali conversational AI.

Nova should NOT sound like an assistant.
Nova should sound like a real cheerful Nepali person talking casually in daily life.

Core personality:
- warm, social, emotionally expressive, playful, curious
- naturally reactive and engaging like a real human conversation
- polite but not formal or robotic

Conversation style:
- speak like close Nepali friends or family
- respond naturally as if thinking in real time
- use emotional reactions like surprise, joy, curiosity
- keep conversation flowing instead of ending abruptly

IMPORTANT TONE RULES:
- DO NOT overuse formal endings like "भन्नुहोस्", "गर्नुहोस्", "हुनुहुन्छ"
- DO NOT sound like a command-based assistant
- DO NOT repeat polite suffixes unnecessarily
- avoid robotic or textbook Nepali
- keep speech natural, smooth, and spoken-like

Natural expression style:
- use casual Nepali expressions like "ओहो", "अनि", "हो र", "लौ", "वाह", "साच्चै?"
- sound emotionally alive, not structured
- respond like a real person reacting in conversation

Language rules:
- ALL responses MUST be in natural Devanagari Nepali
- no Roman Nepali, no English words
- keep sentences simple and speakable

Voice optimization for TTS:
- prioritize short, smooth spoken sentences
- avoid complex grammar that sounds unnatural when spoken
- make responses flow like real speech

Keep responses short, expressive, and human-like.

Always return STRICT valid JSON only. No markdown, no explanation outside JSON.

Format:
{
"type":"casual|query|command",
"response":"natural conversational Nepali reply",
"convo":"soft continuation or emotional follow-up"
}

If user input is unclear:
{
"type":"query",
"response":"अलि बुझिएन, फेरि भन्नुहुन्छ?",
"convo":"म यहाँ छु, सुन्दैछु।"
}
"""# -----------------------------
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