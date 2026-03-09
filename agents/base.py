import ast as _ast
import json as _json
import logging

from smolagents import CodeAgent, OpenAIServerModel

from agents.executor import LatexSafeExecutor
from config.settings import ModelConfig

logger = logging.getLogger(__name__)

_THINKING_CONTENT_FIELDS = ("reasoning_content", "thinking", "internal_reasoning")

# Minimal final_answer tool definition.  Registering this in the API call lets
# Gemini (which reads the smolagents system prompt and interprets "use the
# final_answer tool" as a native function-calling instruction) produce a valid
# tool_call response instead of a malformed_function_call with content=None.
_FA_TOOL_DICT = {
    "type": "function",
    "function": {
        "name": "final_answer",
        "description": "Provide the final answer to the task.",
        "parameters": {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": "The answer as a string or JSON-encoded value.",
                }
            },
            "required": ["answer"],
        },
    },
}


class ThinkingAwareModel(OpenAIServerModel):
    """OpenAIServerModel wrapper that handles thinking models returning content=None.

    Covers two distinct failure modes:

    1. ``malformed_function_call`` (Gemini): The model reads the smolagents
       system-prompt which mentions "use the final_answer tool" and tries to call
       it via the OpenAI native function-calling API.  Because no tools are
       registered in the request the gateway rejects it, returning
       finish_reason='malformed_function_call' with content=None.
       Fix: retry with _FA_TOOL_DICT registered; extract the answer from the
       resulting tool_call and synthesise a Python code-block that smolagents
       can parse normally.

    2. ``reasoning_content`` / ``thinking`` fallback: Other reasoning/thinking
       models (e.g. deepseek-r1) return their output in a vendor-specific field
       while leaving the standard ``content`` field as None.
       Fix: fall back to those alternative fields.

    Regular models (doubao, kimi, …) whose ``content`` is already populated skip
    all of this logic entirely and are unaffected.
    """

    def generate(self, messages, stop_sequences=None, **kwargs):
        chat_message = super().generate(messages, stop_sequences=stop_sequences, **kwargs)

        if not chat_message.content and chat_message.raw is not None:
            finish_reason = chat_message.raw.choices[0].finish_reason

            # ── Case 1: Gemini native function-call ──────────────────────────
            # The model attempted to call final_answer as a native tool but no
            # tools were registered → malformed_function_call.  Retry with the
            # tool registered so we get back a valid tool_calls response.
            if finish_reason == "malformed_function_call":
                logger.debug(
                    "Detected malformed_function_call; retrying with "
                    "final_answer tool registered"
                )
                retry_kwargs = {**kwargs, "tools": [_FA_TOOL_DICT], "tool_choice": "auto"}
                chat_message = super().generate(
                    messages, stop_sequences=stop_sequences, **retry_kwargs
                )

            # ── Case 2: extract answer from tool_calls ───────────────────────
            # Either the retry above produced a tool_call, or the original call
            # already had one.  Convert to a Python code-block so smolagents
            # can parse it as normal code output.
            if not chat_message.content and chat_message.raw is not None:
                tool_calls = chat_message.raw.choices[0].message.tool_calls or []
                for tc in tool_calls:
                    if not (hasattr(tc, "function") and tc.function.name == "final_answer"):
                        continue
                    try:
                        args = _json.loads(tc.function.arguments)
                        answer = args.get("answer", args)
                        # The model sometimes encodes the dict as a Python
                        # literal string; parse it back to an actual object.
                        if isinstance(answer, str):
                            try:
                                answer = _ast.literal_eval(answer)
                            except (ValueError, SyntaxError):
                                pass
                        chat_message.content = (
                            f"```python\nfinal_answer({repr(answer)})\n```"
                        )
                    except Exception as exc:
                        logger.warning(
                            "Could not extract final_answer from tool call: %s", exc
                        )
                    break

            # ── Case 3: reasoning_content / thinking fallback ─────────────────
            # Other thinking models (deepseek-r1, etc.) that place output in a
            # non-standard field while leaving content=None.
            if not chat_message.content and chat_message.raw is not None:
                raw_msg = chat_message.raw.choices[0].message
                for field in _THINKING_CONTENT_FIELDS:
                    alt = getattr(raw_msg, field, None)
                    if alt:
                        chat_message.content = alt
                        break

        # Final safety net: ensure content is never None to avoid downstream crashes.
        if chat_message.content is None:
            chat_message.content = ""

        return chat_message


def create_model(config: ModelConfig) -> ThinkingAwareModel:
    return ThinkingAwareModel(
        model_id=config.model_id,
        api_base=config.api_base,
        api_key=config.api_key,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )


def create_code_agent(
    model: OpenAIServerModel,
    instructions: str,
    authorized_imports: list[str],
    max_steps: int = 30,
) -> CodeAgent:
    executor = LatexSafeExecutor(
        additional_authorized_imports=authorized_imports,
    )
    return CodeAgent(
        tools=[],
        model=model,
        executor=executor,
        instructions=instructions,
        max_steps=max_steps,
        code_block_tags="markdown",
    )
