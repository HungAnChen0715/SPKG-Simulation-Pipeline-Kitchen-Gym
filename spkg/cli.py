"""SPKG Command-Line Interface.

Usage:
    spkg generate "A kitchen with an L-shaped cabinet and a table"
    spkg build kitchen_scene.scenespec.json --output ./outputs/kitchen/
    spkg validate ./outputs/kitchen/world.usda --report html
"""

import click

from spkg import __version__


@click.group()
@click.version_option(version=__version__, prog_name="spkg")
def main():
    """SPKG — Simulation-Pipeline Kitchen Gym.

    Generate, build, and validate physics-ready USD scenes from natural language.
    """


@main.command()
@click.argument("description")
@click.option("--model", default="gemini-2.0-flash", help="LLM model to use.")
@click.option("--output", "-o", default=None, help="Output SceneSpec JSON path.")
def generate(description: str, model: str, output: str | None):
    """Generate a SceneSpec from a natural language scene description."""
    click.echo(f"[spkg generate] Model: {model}")
    click.echo(f"[spkg generate] Description: {description}")
    click.echo("[spkg generate] Not implemented yet — see Week 4 roadmap.")


@main.command()
@click.argument("scenespec", type=click.Path(exists=True))
@click.option("--output", "-o", default="./outputs/", help="Output directory for USD files.")
def build(scenespec: str, output: str):
    """Build layered USD stage from a SceneSpec JSON file."""
    click.echo(f"[spkg build] SceneSpec: {scenespec}")
    click.echo(f"[spkg build] Output dir: {output}")
    click.echo("[spkg build] Not implemented yet — see Week 2 roadmap.")


@main.command()
@click.argument("stage", type=click.Path(exists=True))
@click.option("--report", type=click.Choice(["json", "html"]), default="json", help="Report format.")
@click.option("--output", "-o", default=None, help="Report output path.")
@click.option("--autofix", is_flag=True, help="Automatically fix issues where possible.")
def validate(stage: str, report: str, output: str | None, autofix: bool):
    """Validate a USD stage for physics and semantic correctness."""
    click.echo(f"[spkg validate] Stage: {stage}")
    click.echo(f"[spkg validate] Report format: {report}")
    click.echo(f"[spkg validate] Auto-fix: {autofix}")
    click.echo("[spkg validate] Not implemented yet — see Week 5-7 roadmap.")


if __name__ == "__main__":
    main()
