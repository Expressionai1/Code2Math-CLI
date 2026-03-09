import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.evolution_agent import EvolutionAgent
from agents.solvability_agent import SolvabilityAgent
from agents.difficulty_agent import DifficultyAgent
from config.settings import Code2MathConfig
from utils.loader import load_demonstrations, load_existing_results
from utils.saver import ResultSaver
from utils.logging import PipelineLogger

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(self, config: Code2MathConfig):
        self.config = config
        self.demonstrations = load_demonstrations(
            config.resolve_path(config.data.demonstrations_dir)
        )
        self.pipeline_logger = PipelineLogger(
            log_dir=str(config.resolve_path(config.logging.log_dir)),
            save_trajectories=config.logging.save_trajectories,
        )

    def _create_agents(self):
        """Create a fresh set of agents (each worker should have its own instances)."""
        evolution_agent = EvolutionAgent(
            model_config=self.config.models.evolution,
            sandbox_config=self.config.sandbox,
            demonstrations=self.demonstrations,
            max_steps=self.config.agents.max_steps,
        )
        solvability_agent = SolvabilityAgent(
            model_config=self.config.models.solvability,
            sandbox_config=self.config.sandbox,
            max_steps=self.config.agents.max_steps,
        )
        difficulty_agent = DifficultyAgent(
            model_config=self.config.models.difficulty,
            sandbox_config=self.config.sandbox,
            demonstrations=self.demonstrations,
            max_steps=self.config.agents.max_steps,
        )
        return evolution_agent, solvability_agent, difficulty_agent

    def evolve_single_problem(
        self,
        problem_id: int,
        problem: dict,
        total: int,
    ) -> dict:
        """Run the full evolution pipeline for a single problem with rollout retries."""
        max_rollouts = self.config.pipeline.max_rollouts
        failure_counts = {"evolution": 0, "solvability": 0, "difficulty": 0}
        last_evolved: dict | None = None

        evolution_agent, solvability_agent, difficulty_agent = self._create_agents()

        for rollout in range(max_rollouts):
            self.pipeline_logger.log_rollout_start(problem_id, rollout, max_rollouts, total)

            # Step 1: Evolution
            evolved = evolution_agent.evolve(problem)
            if evolved is None:
                failure_counts["evolution"] += 1
                self.pipeline_logger.log_stage_result(
                    problem_id, rollout, "evolution", False, "Failed to generate evolved problem"
                )
                continue

            self.pipeline_logger.log_stage_result(problem_id, rollout, "evolution", True)
            last_evolved = evolved

            # Step 2: Solvability verification
            solv_result = solvability_agent.verify(
                evolved_problem=evolved["new_problem"],
                evolved_solution=evolved["new_solution_steps"],
                evolved_answer=evolved.get("new_answer"),
            )
            if solv_result is None or solv_result.get("status") != "PASS":
                failure_counts["solvability"] += 1
                reason = solv_result.get("reason", "Unknown") if solv_result else "Agent returned None"
                self.pipeline_logger.log_stage_result(
                    problem_id, rollout, "solvability", False, reason
                )
                continue

            self.pipeline_logger.log_stage_result(problem_id, rollout, "solvability", True)

            # Step 3: Difficulty verification
            diff_result = difficulty_agent.verify(original=problem, evolved=evolved)
            if diff_result is None or diff_result.get("status") != "PASS":
                failure_counts["difficulty"] += 1
                reason = diff_result.get("reason", "Unknown") if diff_result else "Agent returned None"
                score = diff_result.get("score") if diff_result else None
                self.pipeline_logger.log_stage_result(
                    problem_id, rollout, "difficulty", False, f"score={score}, {reason}"
                )
                continue

            self.pipeline_logger.log_stage_result(
                problem_id, rollout, "difficulty", True,
                f"score={diff_result.get('score')}"
            )

            # All verifications passed
            result = _build_success_result(
                evolved, solv_result, diff_result, failure_counts, problem
            )
            self.pipeline_logger.log_problem_complete(problem_id, True, rollout + 1, failure_counts)
            return result

        # Exhausted all rollouts
        result = _build_failure_result(failure_counts, problem, last_evolved)
        self.pipeline_logger.log_problem_complete(problem_id, False, max_rollouts, failure_counts)
        return result

    def run(
        self,
        problems_by_id: dict[int, dict],
        problem_ids: list[int] | None = None,
        output_path: str | None = None,
        resume: bool = False,
    ) -> list[dict]:
        """Run the evolution pipeline on problems specified by their IDs."""
        if problem_ids is None:
            problem_ids = sorted(problems_by_id.keys())

        # Determine output path
        if output_path is None:
            model_id = self.config.models.evolution.model_id
            filename = ResultSaver.make_output_filename(
                model_id, demo_count=len(self.demonstrations)
            )
            output_path = str(
                self.config.resolve_path(self.config.data.output_dir) / filename
            )

        saver = ResultSaver(output_path, set(problems_by_id.keys()))

        # Load existing results for resume
        existing = {}
        if resume:
            existing = load_existing_results(output_path)

        # Filter out already-completed problems
        pending_ids = [
            pid for pid in problem_ids if pid not in existing
        ]

        total = len(pending_ids)
        if total == 0:
            logger.info("All requested problems already processed. Nothing to do.")
            return []

        logger.info(
            f"Starting pipeline: {total} problems to process "
            f"(skipped {len(problem_ids) - total} already completed)"
        )

        self.pipeline_logger.log_run_start(total, self.config)
        start_time = time.time()
        results = []
        workers = self.config.pipeline.workers

        if workers <= 1:
            # Sequential execution
            for i, problem_id in enumerate(pending_ids):
                result = self.evolve_single_problem(problem_id, problems_by_id[problem_id], total)
                saver.save_result(problem_id, result)
                results.append(result)
        else:
            # Concurrent execution
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_id = {
                    executor.submit(
                        self.evolve_single_problem, problem_id, problems_by_id[problem_id], total
                    ): problem_id
                    for problem_id in pending_ids
                }
                for future in as_completed(future_to_id):
                    problem_id = future_to_id[future]
                    try:
                        result = future.result()
                    except Exception as e:
                        logger.error(f"Problem {problem_id} raised exception: {e}")
                        result = _build_failure_result(
                            {"evolution": 0, "solvability": 0, "difficulty": 0},
                            problems_by_id[problem_id],
                            last_evolved=None,
                        )
                        result["error"] = str(e)
                    saver.save_result(problem_id, result)
                    results.append(result)

        elapsed = time.time() - start_time
        self.pipeline_logger.log_run_summary(results, elapsed)
        return results


def _build_success_result(
    evolved: dict, solv_result: dict, diff_result: dict,
    failure_counts: dict, original: dict,
) -> dict:
    return {
        "status": "success",
        "result_data": {
            "status": True,
            "failure_stage": None,
            "new_problem": evolved,
            "solvability": True,
            "solvability_verifier_output": solv_result,
            "difficulty": True,
            "difficulty_verifier_output": diff_result,
        },
        "failure_counts": failure_counts,
        "original_problem": original,
    }


def _build_failure_result(
    failure_counts: dict, original: dict, last_evolved: dict | None = None
) -> dict:
    # Determine the primary failure stage
    if failure_counts["evolution"] > 0 and failure_counts["solvability"] == 0 and failure_counts["difficulty"] == 0:
        failure_stage = "evolution"
    elif failure_counts["solvability"] >= failure_counts["difficulty"]:
        failure_stage = "solvability"
    else:
        failure_stage = "difficulty"

    return {
        "status": "failure",
        "result_data": {
            "status": False,
            "failure_stage": failure_stage,
            "new_problem": last_evolved,
            "solvability": False,
            "solvability_verifier_output": None,
            "difficulty": False,
            "difficulty_verifier_output": None,
        },
        "failure_counts": failure_counts,
        "original_problem": original,
    }
