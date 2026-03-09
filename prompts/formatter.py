from prompts.prompt_math import (
    evolve_prompt_template_with_demonstrations,
    solvability_prompt_template,
    difficulty_prompt_template_with_demonstrations,
)


def format_demonstrations(demos: list[dict]) -> str:
    parts = []
    for i, demo in enumerate(demos, 1):
        parts.append(f"--- Example {i} (Category: {demo.get('category', 'unknown')}) ---")
        parts.append(f"Original Problem:\n{demo['original_problem']}")
        parts.append(f"\nAdapted Problem:\n{demo['adapted_problem']}")
        parts.append(f"\nScore: {demo['score']}")
        parts.append(f"\nRationale:\n{demo['rationale']}")
        parts.append("")
    return "\n".join(parts)


def build_evolution_system_prompt(demos: list[dict]) -> str:
    demo_text = format_demonstrations(demos)
    return evolve_prompt_template_with_demonstrations.replace("{demonstrations}", demo_text)


def build_evolution_task(problem: dict) -> str:
    parts = [
        "Please analyze the following mathematical problem and create a significantly harder evolved version.",
        "",
        f"**Problem Description:**\n{problem['problem_description']}",
        "",
        f"**Solution Steps:**\n{problem['solution_steps']}",
        "",
        f"**Answer:** {problem.get('answer', 'None')}",
        "",
        "Now, evolve this problem following the instructions in your system prompt. "
        "Remember to call `final_answer` with a Python dictionary containing "
        '"new_problem", "new_solution_steps", and "new_answer".',
    ]
    return "\n".join(parts)


def build_solvability_system_prompt() -> str:
    return solvability_prompt_template


def build_solvability_task(
    evolved_problem: str, evolved_solution: str, evolved_answer
) -> str:
    answer_str = str(evolved_answer) if evolved_answer is not None else "None (this is a proof problem)"
    parts = [
        "Please audit the following mathematical problem for solvability and correctness.",
        "",
        f"**Problem Text (`problem_text`):**\n{evolved_problem}",
        "",
        f"**Proposed Solution (`proposed_solution`):**\n{evolved_solution}",
        "",
        f"**Answer (`answer`):** {answer_str}",
        "",
        "Now begin your audit following the instructions in your system prompt. "
        'Remember to call `final_answer` with a Python dictionary containing "status" and "reason".',
    ]
    return "\n".join(parts)


def build_difficulty_system_prompt(demos: list[dict]) -> str:
    demo_text = format_demonstrations(demos)
    return difficulty_prompt_template_with_demonstrations.replace("{demonstrations}", demo_text)


def build_difficulty_task(original: dict, evolved: dict) -> str:
    original_answer = str(original.get("answer", "None"))
    evolved_answer = str(evolved.get("new_answer", "None"))
    parts = [
        "Please assess whether the following adapted problem represents a significant difficulty increase.",
        "",
        "## Original Problem",
        f"**Original Question:**\n{original['problem_description']}",
        f"\n**Original Solution Steps:**\n{original['solution_steps']}",
        f"\n**Original Answer:** {original_answer}",
        "",
        "## Adapted Problem",
        f"**New Problem:**\n{evolved['new_problem']}",
        f"\n**New Solution Steps:**\n{evolved['new_solution_steps']}",
        f"\n**New Answer:** {evolved_answer}",
        "",
        "Now begin your difficulty assessment following the instructions in your system prompt. "
        'Remember to call `final_answer` with a Python dictionary containing "status", "score", and "reason".',
    ]
    return "\n".join(parts)
