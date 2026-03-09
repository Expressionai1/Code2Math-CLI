import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_seed_problems(path: str | Path) -> dict[int, dict]:
    """Load seed problems and return a mapping from problem_id to problem dict."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        problems_list = json.load(f)

    # 构建 problem_id → problem 的映射
    problems_by_id = {}
    for problem in problems_list:
        if "problem_id" not in problem:
            raise ValueError(f"Problem missing 'problem_id' field: {problem}")

        problem_id = problem["problem_id"]
        if not isinstance(problem_id, int) or problem_id < 0:
            raise ValueError(f"Invalid problem_id: {problem_id}")

        if problem_id in problems_by_id:
            raise ValueError(f"Duplicate problem_id: {problem_id}")

        problems_by_id[problem_id] = problem

    logger.info(f"Loaded {len(problems_by_id)} seed problems from {path}")
    return problems_by_id


def load_demonstrations(demo_dir: str | Path) -> list[dict]:
    demo_dir = Path(demo_dir)
    demos = []
    for category_dir in sorted(demo_dir.iterdir()):
        if not category_dir.is_dir():
            continue
        demo_file = category_dir / "demo.json"
        if not demo_file.exists():
            continue
        with open(demo_file, "r", encoding="utf-8") as f:
            category_demos = json.load(f)
        for demo in category_demos:
            # Normalize key names across different demo formats
            normalized = {
                "original_problem": demo.get("original_problem") or demo.get("original_question", ""),
                "adapted_problem": demo.get("adapted_problem") or demo.get("adapted_question", ""),
                "score": demo.get("score"),
                "rationale": demo.get("rationale", ""),
                "category": category_dir.name,
            }
            demos.append(normalized)
    logger.info(f"Loaded {len(demos)} demonstrations from {demo_dir}")
    return demos


def load_existing_results(path: str | Path) -> dict[int, dict]:
    """Load existing results and return a mapping from problem_id to result dict."""
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        results_list = json.load(f)

    existing = {}
    for result in results_list:
        if result.get("status") == "success" and "problem_id" in result:
            problem_id = result["problem_id"]
            existing[problem_id] = result

    logger.info(f"Loaded {len(existing)} existing successful results from {path}")
    return existing
