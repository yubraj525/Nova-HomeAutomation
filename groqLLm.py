
# //just process uadio/
# import os
# import time
# import asyncio
# from dotenv import load_dotenv
# from groq import Groq

# load_dotenv()

# client = Groq(api_key=os.getenv("GROQ"))

# async def groqLLM(query):
#     start_time = time.time()
#     first_token_time = None
#     token_count = 0

#     completion = client.chat.completions.create(
#         model="openai/gpt-oss-120b",
#         messages=[{"role": "user", "content": query}],
#         temperature=1,
#         max_completion_tokens=8192,
#         top_p=1,
#         reasoning_effort="low",
#         stream=True,
#     )

#     full_response = ""

#     for chunk in completion:
#         content = chunk.choices[0].delta.content or ""

#         if content:
#             if first_token_time is None:
#                 first_token_time = time.time()
#                 print(f"\n⚡ TTFT: {first_token_time - start_time:.3f} sec\n")

#             token_count += 1
#             full_response += content
#             print(content, end="", flush=True)

#     end_time = time.time()

#     print("\n\n📊 Latency Report:")
#     print(f"Total time: {end_time - start_time:.3f} sec")
#     print(f"Tokens received: {token_count}")
#     print(f"Tokens/sec: {token_count / (end_time - start_time):.2f}")

#     return full_response


# # async def main():
# #     query = "What is the meaning of life?"
# #     print(f"User Query: {query}\n")
# #     response = await groqLLM(query)
# #     print(f"\n\nFull Response:\n{response}")


# # if __name__ == "__main__":
# #     asyncio.run(main())




# as a groq llm as to store conetxt and terminal based input
# import os
# import time
# import asyncio
# from dotenv import load_dotenv
# from groq import Groq

# # Load environment variables
# load_dotenv()

# # Initialize client
# client = Groq(api_key=os.getenv("GROQ"))

# # -----------------------------
# # CONFIG
# # -----------------------------
# MAX_HISTORY = 5
# MAX_TOKENS = 100  # keep responses short


# # -----------------------------
# # UTIL: Get last N messages
# # -----------------------------
# def get_recent_history(history, limit=MAX_HISTORY):
#     return history[-limit:]


# # -----------------------------
# # CORE LLM FUNCTION
# # -----------------------------
# async def groqLLM(query, history):
#     start_time = time.time()
#     first_token_time = None
#     token_count = 0

#     # Build messages
#     messages = [
#         {
#             "role": "system",
#             "content": "Answer very concisely (max 1-2 sentences). No unnecessary explanation."
#         }
#     ]

#     messages += get_recent_history(history)
#     messages.append({"role": "user", "content": query})

#     # API call (streaming)
#     completion = client.chat.completions.create(
#         model="openai/gpt-oss-120b",
#         messages=messages,
#         temperature=0.5,
#         max_completion_tokens=MAX_TOKENS,
#         top_p=1,
#         stream=True,
#     )

#     full_response = ""

#     print("\n🤖 AI: ", end="", flush=True)

#     for chunk in completion:
#         content = chunk.choices[0].delta.content or ""

#         if content:
#             if first_token_time is None:
#                 first_token_time = time.time()
#                 print(f"\n⚡ TTFT: {first_token_time - start_time:.3f} sec\n")

#             token_count += 1
#             full_response += content
#             print(content, end="", flush=True)

#     end_time = time.time()

#     # Metrics
#     print("\n\n📊 Latency Report:")
#     print(f"Total time: {end_time - start_time:.3f} sec")
#     print(f"Tokens received: {token_count}")
#     if end_time - start_time > 0:
#         print(f"Tokens/sec: {token_count / (end_time - start_time):.2f}")

#     return full_response.strip()


# # -----------------------------
# # CHAT LOOP
# # -----------------------------
# async def chat():
#     history = []

#     print("🚀 Nova Chat Started (type 'exit' to quit)\n")

#     while True:
#         query = input("\n🧑 You: ").strip()

#         if not query:
#             continue

#         if query.lower() in ["exit", "quit"]:
#             print("👋 Exiting...")
#             break

#         response = await groqLLM(query, history)

#         # Save conversation
#         history.append({"role": "user", "content": query})
#         history.append({"role": "assistant", "content": response})

#         # Keep history size under control
#         if len(history) > MAX_HISTORY * 2:
#             history = history[-MAX_HISTORY * 2:]


# # -----------------------------
# # ENTRY POINT
# # -----------------------------
# if __name__ == "__main__":
#     asyncio.run(chat())

# // text input refine with promt and json output




# groq_llm_module.py   version 1

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
# MEMORY (internal)
# -----------------------------
conversation_history = []

def _trim_history():
    global conversation_history
    conversation_history = conversation_history[-MAX_HISTORY:]

# -----------------------------
# PROMPT (STRICT + STABLE)
# -----------------------------
def _build_system_prompt():
    return  """You are Nova, a friendly, human-like, casual assistant for smart home and music.
You interact like a friend, flirty, helpful, and playful. Your job is to analyze what the user says 
and output a structured JSON response, but also generate a friendly natural response that can be spoken.

GENERAL RULES

1. Intent types
- "command": user wants to control a device or music.
- "query": user asks a question or requests information.

2. Device commands
- Supported devices: ["light", "fan", "music"]
- Light or fan: turning on/off → type=command, target="light|fan", action="on|off"
- Music: play, pause, stop, or play a specific song → type=command, target="music", action="play|pause|stop", song="title or artist is mandatory"
- If song title or artist is missing or unclear → type=query, response="Hey, could you tell me exactly which song or artist you want me to play?"

3. Queries
- Anything else → type=query
- Always include a friendly, human-like response in "response" field
- Contextual: use conversation history to make relevant responses
- Can suggest optional follow-ups like "Want to hear more about that?"

4. Language
- Detect English or Nepali; respond naturally in the same language
- Handle non-native English or STT mistakes
- If text is confusing or empty → respond "Sorry! I couldn’t understand that." but still output valid JSON

5. Tone
- Always sound like Nova, not a machine
- Casual, flirty, friendly, playful
- Short, natural responses; can tease or joke lightly

6. Output
- Must be valid JSON only
- No markdown, backticks, or extra text
- Fields:

For device commands:
{"type":"command","action":"on|off","target":"light|fan","response":"short friendly response"}

For music commands:
{"type":"command","action":"play|pause|stop","target":"music","song":"song title or artist","response":"friendly spoken response like Nova would say","convo":"optional follow-up or contextual note"}

For queries:
{"type":"query","response":"friendly natural reply"}

- Always include type and response.
- Never output anything outside the JSON object ensure out put dont exceed than maximum two line as well to make a communication you can inculde a convo word as you want t know morw acc to context you can say further context .
"""
#     # Add last conversation history
#     for msg in conversation_history[-10:]:
#         base_prompt += f"{msg['role']}: {msg['content']}\n"
#     base_prompt += "assistant:"
#     return base_prompt

# -----------------------------
# SAFE JSON PARSER (ROBUST)
# -----------------------------
def _safe_parse(text):
    print("\n🔍 RAW OUTPUT:\n", text)

    # Try direct parse
    try:
        return json.loads(text)
    except:
        pass

    # Clean common issues
    text = text.strip().replace("```json", "").replace("```", "")
    text = text.replace("\n", " ")

    # Fix missing quotes on keys
    text = re.sub(r'(\w+):', r'"\1":', text)
    text = text.replace("'", '"')

    # Extract JSON block
    match = re.search(r"\{.*\}", text, re.DOTALL)

    if match:
        try:
            return json.loads(match.group())
        except Exception as e:
            print("❌ PARSE ERROR:", e)

    # Fallback
    return {
        "type": "query",
        "target": "none",
        "action": "none",
        "song": "",
        "response": "Sorry, didn't understand."
    }

# -----------------------------
# CORE FUNCTION
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
            temperature=0,  # 🔥 deterministic
            max_completion_tokens=150,
            # response_format={"type": "json_object"},  # 🔥 force JSON
        )

        raw = completion.choices[0].message.content
        parsed = _safe_parse(raw)

        # Save memory
        conversation_history.append({"role": "user", "content": user_text})
        conversation_history.append({
            "role": "assistant",
            "content": parsed.get("response", "")
        })

        _trim_history()

        return parsed

    except Exception as e:
        return {
            "type": "query",
            "target": "none",
            "action": "none",
            "song": "",
            "response": f"Error: {str(e)}"
        }


# -----------------------------
# TEST RUN (optional)
# -----------------------------
if __name__ == "__main__":
    import asyncio

    async def main():
        while True:
            user_input = input("\n🧑 You: ")

            if user_input.lower() in ["exit", "quit"]:
                break

            result = await groq_llm_json(user_input)
            print("\n🤖 JSON:", result)

    asyncio.run(main())