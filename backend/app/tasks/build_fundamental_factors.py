from datetime import date
from typing import Annotated

import typer

from app.core.db import SessionLocal
from app.repositories.factor import FactorRepository

cli = typer.Typer(help="Build long-term fundamental factor values.")


@cli.command("run")
def run(
    start_date: Annotated[
        str | None,
        typer.Option(help="Optional factor start date, YYYY-MM-DD."),
    ] = None,
) -> None:
    parsed_start_date = date.fromisoformat(start_date) if start_date else None
    with SessionLocal() as session:
        repository = FactorRepository(session)
        rows = repository.rebuild_factor_values(start_date=parsed_start_date)
        latest_factor_date = repository.latest_factor_date()
        session.commit()
    typer.echo(
        "FUNDAMENTAL_FACTORS "
        f"rows={rows} "
        f"start_date={parsed_start_date} "
        f"latest_factor_date={latest_factor_date}"
    )


if __name__ == "__main__":
    cli()
