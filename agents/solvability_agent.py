import logging

from agents.base import create_model, create_code_agent
from agents.parsing import parse_solvability_result
from config.settings import ModelConfig, SandboxConfig
from prompts.formatter import build_solvability_system_prompt, build_solvability_task

logger = logging.getLogger(__name__)


class SolvabilityAgent:
    def __init__(
        self,
        model_config: ModelConfig,
        sandbox_config: SandboxConfig,
        max_steps: int = 30,
    ):
        model = create_model(model_config)
        system_prompt = build_solvability_system_prompt()
        self.agent = create_code_agent(
            model=model,
            instructions=system_prompt,
            authorized_imports=sandbox_config.authorized_imports,
            max_steps=max_steps,
        )

    def verify(
        self, evolved_problem: str, evolved_solution: str, evolved_answer
    ) -> dict | None:
        task = build_solvability_task(evolved_problem, evolved_solution, evolved_answer)
        try:
            result = self.agent.run(task=task)
            return parse_solvability_result(result)
        except Exception as e:
            logger.error(f"Solvability agent error: {e}")
            return None
