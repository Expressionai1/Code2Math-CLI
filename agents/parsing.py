import ast
import json
import logging
import re

logger = logging.getLogger(__name__)


def parse_agent_result(result, expected_keys: list[str]) -> dict | None:
    """Parse the result from a CodeAgent's final_answer call.

    Tries multiple strategies:
    1. If result is already a dict with expected keys, return it.
    2. If result is a string, try ast.literal_eval, then json.loads.
    3. As fallback, try regex extraction of key-value pairs.
    """
    if result is None:
        return None

    # Strategy 1: direct dict
    if isinstance(result, dict):
        if all(k in result for k in expected_keys):
            return result
        logger.warning(f"Dict result missing keys. Got: {list(result.keys())}, expected: {expected_keys}")
        return result if any(k in result for k in expected_keys) else None

    # Strategy 2: string parsing
    if isinstance(result, str):
        text = result.strip()
        # Try ast.literal_eval
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, SyntaxError):
            pass

        # Try json.loads
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

        # Try extracting JSON block from markdown
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass

        # Try finding any dict-like structure
        dict_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if dict_match:
            try:
                parsed = ast.literal_eval(dict_match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, SyntaxError):
                try:
                    parsed = json.loads(dict_match.group(0))
                    if isinstance(parsed, dict):
                        return parsed
                except (json.JSONDecodeError, ValueError):
                    pass

        logger.warning(f"Could not parse string result: {text[:200]}...")
        return None

    # Unknown type
    logger.warning(f"Unexpected result type: {type(result)}")
    return None


def parse_evolution_result(result) -> dict | None:
    parsed = parse_agent_result(result, ["new_problem", "new_solution_steps", "new_answer"])
    if parsed is None:
        return None
    # Validate required fields are non-empty
    if not parsed.get("new_problem") or not parsed.get("new_solution_steps"):
        logger.warning("Evolution result has empty required fields")
        return None
    return parsed


def parse_solvability_result(result) -> dict | None:
    parsed = parse_agent_result(result, ["status", "reason"])
    if parsed is None:
        return None
    status = parsed.get("status", "")
    if isinstance(status, str):
        parsed["status"] = status.upper()
    return parsed


def parse_difficulty_result(result) -> dict | None:
    parsed = parse_agent_result(result, ["status", "score", "reason"])
    if parsed is None:
        return None
    status = parsed.get("status", "")
    if isinstance(status, str):
        parsed["status"] = status.upper()
    # Ensure score is an integer
    score = parsed.get("score")
    if score is not None:
        try:
            parsed["score"] = int(score)
        except (ValueError, TypeError):
            pass
    return parsed
