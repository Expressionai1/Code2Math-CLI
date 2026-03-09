import logging

from agents.base import create_model, create_code_agent
from agents.parsing import parse_evolution_result
from config.settings import ModelConfig, SandboxConfig
from prompts.formatter import build_evolution_system_prompt, build_evolution_task

logger = logging.getLogger(__name__)


class EvolutionAgent:
    def __init__(
        self,
        model_config: ModelConfig,
        sandbox_config: SandboxConfig,
        demonstrations: list[dict],
        max_steps: int = 30,
    ):
        model = create_model(model_config)
        system_prompt = build_evolution_system_prompt(demonstrations)
        self.agent = create_code_agent(
            model=model,
            instructions=system_prompt,
            authorized_imports=sandbox_config.authorized_imports,
            max_steps=max_steps,
        )

    def evolve(self, problem: dict) -> dict | None:
        task = build_evolution_task(problem)
        try:
            result = self.agent.run(task=task)
            return parse_evolution_result(result)
        except Exception as e:
            logger.error(f"Evolution agent error: {e}")
            return None
