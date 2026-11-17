"""Built-in equity and index strategies. Importing this package registers them."""

from trademind.services.strategy_engine.equity import (
    failed_orb_fade,
    first_half_hour_momentum,
    intraday_contraction,
    orb_momentum,
    overextension_fade,
    sweep_reversal,
)

__all__ = [
    "failed_orb_fade",
    "first_half_hour_momentum",
    "intraday_contraction",
    "orb_momentum",
    "overextension_fade",
    "sweep_reversal",
]
