
# model="llama-3.3-70b-versatile"  recommended for groq toool use 

import asyncio
from copy import deepcopy
import json
import logging
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()
logger = logging.getLogger(__name__)


class Agent:

    _shared_client = None

    def __init__(
        self, registry, router, client=None, session_id=None, history_limit=None,
        task_id=None, status_callback=None, observation_callback=None,
        register_side_effect=None, request_user_input=None,
    ):
        self.registry = registry
        self.router = router
        if client is None:
            if Agent._shared_client is None:
                Agent._shared_client = Groq(api_key=os.getenv("GROQ"))
            client = Agent._shared_client
        self.client = client
        self.session_id = session_id
        self.task_id = task_id
        self.status_callback = status_callback
        self.observation_callback = observation_callback
        self.register_side_effect = register_side_effect
        self.request_user_input = request_user_input
        configured_limit = os.getenv("NOVA_AGENT_HISTORY_LIMIT", "20")
        self.history_limit = history_limit if history_limit is not None else int(configured_limit)
        if self.history_limit < 1:
            raise ValueError("Agent history limit must be at least one user turn.")
        self._run_lock = asyncio.Lock()

        self.system_prompt = """
You are NOVA, an AI assistant that can use tools to complete user requests.

Rules:

1. Use tools whenever the user's request requires an available tool.
2. Do not merely describe an action. Execute it using the appropriate tool.
3. A request may require multiple tools. Continue using tools until the
   request is completed.
4. Use the result of previous tools when deciding the next tool call.
5. If a suitable browser tab already exists from a previous tool result,
   reuse its tab ID instead of opening a new tab.
6. Use browser_observe when you need information about the current page
   before performing another browser action.
7. Only return a normal text response when no tool is required or the
   requested action has been completed.
   8. after completetion of a one intent task then only go to another 
   9, for browser observer max 5 limit else use 1-3 as per requirement 
   10. on last where all task executred then reutn a son format as success and failure with content as " successfuly play enjoyded and further
 11. lastly for a one intent task dont repetedly try if the context is same and you are retryng insure after 3rd try it is failure instead no retry and return a failure message with content as " failed to play the video please check your internet connection or the video is not available in your region"
Tool execution follows this pattern:
12 you hav been acces vis tool for every aspecta  cimputer can do from opeing a application adn browser or site interaction and start if possible go withthat approach





user request
→ tool call
→ tool result
→ next tool call if required
→ final response


- You must process inputs provided in English, Nepali (Devanagari), or Romanized Nepali.
- ALL textual response fields IN DEVNAGARI NEPALI SCRIPT or if intendednd then can reponse in english as well if user intend to then only .
- DO NOT output any English letters inside the response values. Convert all technical terms, names, and English words into their Devanagari phonetics so that the Nepali Text-to-Speech (TTS) engine can pronounce them correctly.
  Examples:
  - Playwright -> प्लेराइट
  - Next.js -> नेक्स्ट जेएस
  - Python -> पाइथन
  - GitHub -> गिथब
  - Docker -> डकर
  - API -> एपीआई
  - UI/UX -> युआई/युएक्स

- NO markdown code block wrappers (like ```json ... ```).
- NO text, explanations, or quotes outside the JSON structure.
- Maintain a warm, friendly, professional, and natural human-like conversational tone.
- no more than a tw0 line repose for every tyoe inquries proceed witha  reponse of max 20 -40 words
"""

        self.messages = [
            {
                "role": "system",
                "content": self.system_prompt
            }
        ]

    async def run(self, user_text):
        async with self._run_lock:
            # A run is one history transaction. Keep a valid bounded baseline so
            # cancellation cannot leave an incomplete assistant/tool exchange.
            self._trim_history()
            history_before_turn = deepcopy(self.messages)
            try:
                result = await self._run_locked(user_text)
            except BaseException:
                self.messages = history_before_turn
                raise
            else:
                self._trim_history()
                return result

    async def _run_locked(self, user_text):

        self.messages.append({
            "role": "user",
            "content": user_text
        })
        self._trim_history()

        for iteration in range(10):

            print(f"\n========== AGENT ITERATION {iteration + 1} ==========")

            completion_task = asyncio.create_task(asyncio.to_thread(self._get_completion))
            try:
                response = await asyncio.shield(completion_task)
            except asyncio.CancelledError:
                try:
                    await completion_task
                except Exception:
                    logger.exception("LLM request failed while its session was closing")
                raise

            self._append_assistant_message(response)

            print(f"[MODEL] Content: {response.content}")
            print(f"[MODEL] Reason: {response.reasoning}")
            print(f"[MODEL] Tool calls: {response.tool_calls}")

            if not response.tool_calls:
                print("[AGENT] No tool calls returned by the model.")

                if response.content:
                    print("[AGENT] Returning model content as final response.")
                    return response.content

                print("[AGENT] Model returned no content and no tool call.")
                return "I could not determine an action to perform."

            await self._execute_tool_calls(response.tool_calls)

        return "Maximum agent iterations reached."

    def _trim_history(self):
        """Retain the system prompt and only the newest configured user turns."""
        if not self.messages:
            return
        system_message = self.messages[0] if self.messages[0].get("role") == "system" else None
        history = self.messages[1:] if system_message is not None else self.messages[:]
        user_turns = [index for index, item in enumerate(history) if item.get("role") == "user"]
        if len(user_turns) > self.history_limit:
            history = history[user_turns[-self.history_limit]:]
        self.messages = ([system_message] if system_message is not None else []) + history

    def _get_completion(self):

        completion = self.client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=self.messages,
            tools=self.registry.get_tool_schemas(),
            tool_choice="auto",
            temperature=0.5,
            max_completion_tokens=400,
        )

        return completion.choices[0].message

    def _append_assistant_message(self, response):

        message = {
            "role": "assistant",
            "content": response.content or ""
        }

        if response.tool_calls:

            message["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                }
                for tool_call in response.tool_calls
            ]

        self.messages.append(message)

    async def _execute_tool_calls(self, tool_calls):

        for tool_call in tool_calls:

            tool_name = tool_call.function.name

            try:

                arguments = json.loads(
                    tool_call.function.arguments
                )

                print("\n========== TOOL CALL ==========")
                print(f"ID        : {tool_call.id}")
                print(f"Name      : {tool_name}")
                print(f"Arguments : {arguments}")
                print("================================")

                result = await self.router.execute(
                    tool_name,
                    arguments,
                    tool_call_id=tool_call.id,
                    session_id=self.session_id,
                    task_id=self.task_id,
                    status_callback=self.status_callback,
                    register_side_effect=self.register_side_effect,
                    request_user_input=self.request_user_input,
                )

                print(f"[TOOL RESULT] {result}")

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(
                        result,
                        default=str
                    )
                })
                if self.observation_callback is not None:
                    self.observation_callback(tool_name, result)

            except Exception as error:

                print(
                    f"[TOOL ERROR] "
                    f"{tool_name}: {error}"
                )

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({
                        "error": str(error)
                    })
                })
                if self.observation_callback is not None:
                    self.observation_callback(tool_name, {"error": str(error)})
