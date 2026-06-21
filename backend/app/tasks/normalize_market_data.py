from datetime import date
from typing import Annotated

import typer

from app.core.db import SessionLocal
from app.services.market_data_normalization import MarketDataNormalizationService

cli = typer.Typer(
    help="Normalize raw Tushare market data into application tables.",
    invoke_without_command=True,
)


def parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


@cli.command()
def core(
    start_date: Annotated[
        str | None,
        typer.Option(help="Inclusive quote start date, YYYY-MM-DD."),
    ] = None,
    end_date: Annotated[
        str | None,
        typer.Option(help="Inclusive quote end date, YYYY-MM-DD."),
    ] = None,
) -> None:
    with SessionLocal() as session:
        result = MarketDataNormalizationService(session).normalize_core_market_data(
            start_date=parse_date(start_date),
            end_date=parse_date(end_date),
        )

    typer.echo(
        "Normalized core market data: "
        f"stocks={result.stocks}, "
        f"trade_calendars={result.trade_calendars}, "
        f"daily_quotes={result.daily_quotes}, "
        f"index_daily_quotes={result.index_daily_quotes}, "
        f"daily_indicators={result.daily_indicators}, "
        f"adj_factors={result.adj_factors}"
    )


if __name__ == "__main__":
    cli()
