import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    model_id: str
    api_base: str
    api_key: str
    temperature: float = 0.7
    max_tokens: int = 16384


class AgentsConfig(BaseModel):
    max_steps: int = 30


class PipelineConfig(BaseModel):
    max_rollouts: int = 20
    workers: int = 1


class SandboxConfig(BaseModel):
    executor_type: str = "local"
    authorized_imports: list[str] = Field(default_factory=list)


class DataConfig(BaseModel):
    seed_problems: str = "original_problems.json"
    demonstrations_dir: str = "prompts/math_demonstrations"
    output_dir: str = "evolved_problems"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    log_dir: str = "logs"
    save_trajectories: bool = False


class ModelsConfig(BaseModel):
    evolution: ModelConfig
    solvability: ModelConfig
    difficulty: ModelConfig


class Code2MathConfig(BaseModel):
    models: ModelsConfig
    agents: AgentsConfig = AgentsConfig()
    pipeline: PipelineConfig = PipelineConfig()
    sandbox: SandboxConfig = SandboxConfig()
    data: DataConfig = DataConfig()
    logging: LoggingConfig = LoggingConfig()
    project_root: str = "."

    @classmethod
    def from_yaml(cls, path: str, project_root: str | None = None) -> "Code2MathConfig":
        with open(path, "r") as f:
            raw = yaml.safe_load(f)

        # Allow env vars to override
        env_key = os.environ.get("CODE2MATH_API_KEY")
        env_base = os.environ.get("CODE2MATH_API_BASE")
        env_model_id = os.environ.get("CODE2MATH_MODEL_ID")
        for model_name in raw.get("models", {}):
            if env_key:
                raw["models"][model_name]["api_key"] = env_key
            raw["models"][model_name]["api_base"] = (
                env_base or raw["models"][model_name].get("api_base")
                or "https://gateway.stem-align.com/v1"
            )
            raw["models"][model_name]["model_id"] = (
                env_model_id or raw["models"][model_name].get("model_id")
                or "doubao-seed-2-0-pro-260215"
            )

        config = cls(**raw)

        if project_root:
            config.project_root = project_root
        else:
            config.project_root = str(Path(path).parent.parent)

        return config

    def resolve_path(self, relative_path: str) -> Path:
        return Path(self.project_root) / relative_path
