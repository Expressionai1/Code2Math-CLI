import re
import warnings

from smolagents.local_python_executor import LocalPythonExecutor, CodeOutput

# Python 会错误解释的转义序列 → 还原为 LaTeX 原文
_ESCAPE_FIXES = {
    "\x07": r"\a",  # \a (bell) → \alpha, \arctan, ...
    "\x08": r"\b",  # \b (backspace) → \beta, \binom, ...
    "\x0c": r"\f",  # \f (form feed) → \frac, \forall, ...
    "\x0b": r"\v",  # \v (vertical tab) → \vee, \vec, ...
    "\x00": r"\0",  # \0 (null) → rare but possible
}

_FIX_PATTERN = re.compile("|".join(re.escape(k) for k in _ESCAPE_FIXES))


class LatexSafeExecutor(LocalPythonExecutor):
    """在代码执行后修复字符串值中被 Python 转义破坏的 LaTeX 命令。"""

    def __call__(self, code_action: str) -> CodeOutput:
        # 抑制 LLM 生成代码中 LaTeX 转义序列产生的 SyntaxWarning
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=SyntaxWarning)
            result = super().__call__(code_action)
        if result.output is not None:
            result = CodeOutput(
                output=_fix_latex_in_value(result.output),
                logs=result.logs,
                is_final_answer=result.is_final_answer,
            )
        return result


def _fix_latex_in_value(obj):
    """递归修复 dict/list/str 中被破坏的 LaTeX 转义。"""
    if isinstance(obj, str):
        return _FIX_PATTERN.sub(lambda m: _ESCAPE_FIXES[m.group()], obj)
    if isinstance(obj, dict):
        return {k: _fix_latex_in_value(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_fix_latex_in_value(v) for v in obj]
    return obj
