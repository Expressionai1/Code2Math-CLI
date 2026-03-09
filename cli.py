import sys
from pathlib import Path

import click
from dotenv import load_dotenv

# Load .env before any config (API key, etc.)
load_dotenv()

# Add project root to sys.path for imports
PROJECT_ROOT = str(Path(__file__).parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.settings import Code2MathConfig  # noqa: E402
from utils.loader import load_seed_problems  # noqa: E402
from utils.cli_helpers import parse_problem_ids  # noqa: E402
from pipeline.orchestrator import PipelineOrchestrator  # noqa: E402
from utils.logging import setup_logging  # noqa: E402


@click.group()
def cli():
    """Code2Math-CLI: Multi-agent mathematical problem evolution pipeline."""
    pass


@cli.command()
@click.option(
    "--config", "config_path",
    default="config/default.yaml",
    help="Path to configuration YAML file.",
    type=click.Path(exists=True),
)
@click.option(
    "--model",
    default=None,
    help="Override the evolution model ID (e.g., gemini-3-pro-preview).",
)
@click.option(
    "--problems",
    default="all",
    help="Problem indices to process (e.g., '0-9', '5', '0,3,7', 'all').",
)
@click.option(
    "--max-rollouts",
    default=None,
    type=int,
    help="Maximum rollout attempts per problem.",
)
@click.option(
    "--workers",
    default=None,
    type=int,
    help="Number of concurrent workers.",
)
@click.option(
    "--resume / --no-resume",
    default=False,
    help="Resume from existing output file, skipping completed problems.",
)
@click.option(
    "--output",
    default=None,
    help="Output file path for results.",
    type=click.Path(),
)
def evolve(config_path, model, problems, max_rollouts, workers, resume, output):
    """Run the math problem evolution pipeline."""
    # Load config
    config = Code2MathConfig.from_yaml(config_path)

    # Apply CLI overrides
    if model:
        config.models.evolution.model_id = model
        config.models.solvability.model_id = model
        config.models.difficulty.model_id = model
    if max_rollouts is not None:
        config.pipeline.max_rollouts = max_rollouts
    if workers is not None:
        config.pipeline.workers = workers

    # Setup logging
    setup_logging(
        level=config.logging.level,
        log_dir=str(config.resolve_path(config.logging.log_dir)),
    )

    # Load seed problems (now returns dict)
    seed_path = config.resolve_path(config.data.seed_problems)
    all_problems = load_seed_problems(seed_path)

    # Parse problem IDs
    problem_ids = parse_problem_ids(problems, set(all_problems.keys()))
    if not problem_ids:
        click.echo("No problems to process.", err=True)
        return

    click.echo(
        f"Processing {len(problem_ids)} problem(s) with model "
        f"{config.models.evolution.model_id}"
    )

    # Run pipeline
    orchestrator = PipelineOrchestrator(config)
    results = orchestrator.run(
        problems_by_id=all_problems,
        problem_ids=problem_ids,
        output_path=output,
        resume=resume,
    )

    # Summary
    successes = sum(1 for r in results if r.get("status") == "success")
    click.echo(f"\nDone. {successes}/{len(results)} problems evolved successfully.")


if __name__ == "__main__":
    cli()
