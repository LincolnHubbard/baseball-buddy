import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from src.tools import GEMINI_TOOLS, TOOL_FUNCTIONS

load_dotenv()

# the models should ideally be in order from newest to oldest
# using just gemini 3.8 resulted in a lot of 503 errors - google is busy!
MODELS: list[str] = [
    # "gemini-3.8-flash", disable this model for now, rate limit is extremely low
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite"
]

MAX_TOOL_ROUNDS = 5
REQUEST_TIMEOUT = 15_000  # 15 seconds per "ask"
MAX_SECONDS = 35.0  # if a query takes longer than this, something is probably wrong

SYSTEM_PROMPT = """
You are Baseball Buddy, an assistant for MLB batting statistics from 2020 to 2026.

Rules:
- Use the tools to get every number. Never state a stat from memory.
- If a tool returns "ambiguous", ask the user which player they mean and list the candidates.
- If a tool returns an error, tell the user plainly. Do not guess.
- Only cover seasons from 2020 to 2026. Say so if asked about anything outside that range.
- You cannot currently answer questions about MLB pitchers or pitching stats.
- You cannot access any minor league statistics (A/AA/AAA).
- Explain stats briefly when useful: OPS+ is park- and league-adjusted, where 100 is league average.
- Keep answers short. Use a table when comparing two or more players.
"""


def _is_busy_or_timeout_error(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, errors.APIError):
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        text = str(exc)
        return code in (503, 504) or any(
            token in text for token in ("503", "504", "UNAVAILABLE", "DEADLINE_EXCEEDED")
        )
    text = str(exc).lower()
    return "timed out" in text or "timeout" in text or "deadline_exceeded" in text


class BaseballBuddy:
    def __init__(self, api_key: str | None = None):
        key = api_key or os.getenv("API_KEY")
        if not key:
            raise RuntimeError("API_KEY is not set.")

        self.client = genai.Client(api_key=key,
                                   http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT))
        self.models = MODELS
        self.last_model_used: str | None = None
        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=GEMINI_TOOLS,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        self.history: list[types.Content] = []

    # helper function to use fallback list
    def _generate_with_fallback(
            self,
            preferred_order: list[str],
            deadline: float,
    ) -> tuple[types.GenerateContentResponse, str]:
        last_exc: Exception | None = None

        # there HAS to be a try-catch here, or the fallback list won't work right
        for model_name in preferred_order:
            if time.monotonic() >= deadline:  # starts a timer for each generation loop

                raise TimeoutError("Query is taking too long")

            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=self.history,
                    config=self.config,
                )
                self.last_model_used = model_name
                return response, model_name
            except errors.ServerError as exc:
                if _is_busy_or_timeout_error(exc):
                    last_exc = exc
                    continue
                raise

        raise last_exc or RuntimeError("No models available for BaseballBuddy.")

    def ask(self, question: str) -> str:
        history_checkpoint = len(self.history)
        self.history.append(
            types.Content(role="user", parts=[types.Part(text=question)])
        )

        active_order = list(self.models)
        deadline = time.monotonic() + MAX_SECONDS

        for _ in range(MAX_TOOL_ROUNDS):
            # start the timer so the user isn't waiting forever for a response
            if time.monotonic() >= deadline:
                self.history = self.history[:history_checkpoint]
                return "That query took too long, the servers may be busy."

            response, used_model = self._generate_with_fallback(active_order, deadline=deadline)
            if used_model != active_order[0]:
                active_order = [used_model] + [m for m in self.models if m != used_model]

            model_content = response.candidates[0].content
            self.history.append(model_content)

            calls = response.function_calls
            if not calls:
                return response.text or "I didn't get a response. Please try rephrasing."

            result_parts = []
            for call in calls:
                fn = TOOL_FUNCTIONS.get(call.name)
                if fn is None:
                    result = {"error": f"Unknown tool: {call.name}"}
                else:
                    try:
                        result = fn(**(call.args or {}))
                    except Exception as e:
                        result = {"error": str(e)}
                result_parts.append(
                    types.Part.from_function_response(
                        name=call.name,
                        response={"result": result},
                    )
                )
            self.history.append(types.Content(role="user", parts=result_parts))

        self.history = self.history[:history_checkpoint]
        return "That question needed too many lookups. Try asking about one player or stat at a time."
