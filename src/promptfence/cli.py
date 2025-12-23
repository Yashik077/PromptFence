import typer

from promptfence import __version__

app = typer.Typer(
    name="promptfence",
    help="Security testing framework for AI applications.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print the installed PromptFence version."""
    typer.echo(__version__)


def main() -> None:
    app()
