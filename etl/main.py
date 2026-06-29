"""ETL container/process entry point - delegates to the Typer CLI."""

from __future__ import annotations

from etl.cli import app

if __name__ == "__main__":
    app()
