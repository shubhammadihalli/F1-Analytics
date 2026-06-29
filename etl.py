"""Entry point: `python etl.py` ingests every F1 session not yet in Postgres.

Thin wrapper around the `etl` package's Typer CLI so the pipeline can be run
directly from the repository root without `python -m etl.cli`.
"""

from __future__ import annotations

from etl.cli import app

if __name__ == "__main__":
    app()
