import json
import logging
import sys
import time
import uuid
from pathlib import Path


def setup_logging(level: str = "INFO", log_dir: str | None = None) -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            log_path / f"code2math_cli_{time.strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8",
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )


class PipelineLogger:
    def __init__(self, log_dir: str, save_trajectories: bool = False):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.save_trajectories = save_trajectories
        self.run_id = str(uuid.uuid4())[:8]
        self.logger = logging.getLogger("pipeline")

        if save_trajectories:
            self.trajectory_file = self.log_dir / f"{self.run_id}.jsonl"
        else:
            self.trajectory_file = None

    def _write_event(self, event: dict) -> None:
        if self.trajectory_file:
            event["timestamp"] = time.time()
            event["run_id"] = self.run_id
            with open(self.trajectory_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def log_run_start(self, total_problems: int, config) -> None:
        self.logger.info(
            f"=== Run {self.run_id} started | "
            f"Problems: {total_problems} | "
            f"Max rollouts: {config.pipeline.max_rollouts} | "
            f"Workers: {config.pipeline.workers} | "
            f"Model: {config.models.evolution.model_id} ==="
        )
        self._write_event({
            "event": "run_start",
            "total_problems": total_problems,
            "model": config.models.evolution.model_id,
        })

    def log_rollout_start(
        self, problem_idx: int, rollout: int, max_rollouts: int, total: int
    ) -> None:
        self.logger.info(
            f"[Problem {problem_idx}] Rollout {rollout + 1}/{max_rollouts}"
        )
        self._write_event({
            "event": "rollout_start",
            "problem_idx": problem_idx,
            "rollout": rollout + 1,
        })

    def log_stage_result(
        self,
        problem_idx: int,
        rollout: int,
        stage: str,
        passed: bool,
        detail: str = "",
    ) -> None:
        status = "PASS" if passed else "FAIL"
        msg = f"[Problem {problem_idx}] Rollout {rollout + 1} | {stage}: {status}"
        if detail:
            msg += f" | {detail}"
        if passed:
            self.logger.info(msg)
        else:
            self.logger.warning(msg)
        self._write_event({
            "event": "stage_result",
            "problem_idx": problem_idx,
            "rollout": rollout + 1,
            "stage": stage,
            "passed": passed,
            "detail": detail,
        })

    def log_problem_complete(
        self,
        problem_idx: int,
        success: bool,
        rollouts_used: int,
        failure_counts: dict,
    ) -> None:
        status = "SUCCESS" if success else "FAILURE"
        self.logger.info(
            f"[Problem {problem_idx}] {status} after {rollouts_used} rollout(s) | "
            f"Failures: evo={failure_counts['evolution']}, "
            f"solv={failure_counts['solvability']}, "
            f"diff={failure_counts['difficulty']}"
        )
        self._write_event({
            "event": "problem_complete",
            "problem_idx": problem_idx,
            "success": success,
            "rollouts_used": rollouts_used,
            "failure_counts": failure_counts,
        })

    def log_run_summary(self, results: list[dict], elapsed: float) -> None:
        total = len(results)
        successes = sum(1 for r in results if r.get("status") == "success")
        failures = total - successes

        total_evo_failures = sum(
            r.get("failure_counts", {}).get("evolution", 0) for r in results
        )
        total_solv_failures = sum(
            r.get("failure_counts", {}).get("solvability", 0) for r in results
        )
        total_diff_failures = sum(
            r.get("failure_counts", {}).get("difficulty", 0) for r in results
        )

        self.logger.info("=" * 60)
        self.logger.info(f"Run {self.run_id} completed in {elapsed:.1f}s")
        self.logger.info(f"  Total problems: {total}")
        self.logger.info(f"  Successes: {successes} ({100 * successes / total:.1f}%)" if total > 0 else "  Successes: 0")
        self.logger.info(f"  Failures: {failures}")
        self.logger.info(f"  Evolution failures: {total_evo_failures}")
        self.logger.info(f"  Solvability failures: {total_solv_failures}")
        self.logger.info(f"  Difficulty failures: {total_diff_failures}")
        self.logger.info("=" * 60)

        self._write_event({
            "event": "run_summary",
            "total": total,
            "successes": successes,
            "failures": failures,
            "elapsed_seconds": elapsed,
            "evolution_failures": total_evo_failures,
            "solvability_failures": total_solv_failures,
            "difficulty_failures": total_diff_failures,
        })
