from enum import StrEnum


class Side(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"


class Segment(StrEnum):
    EQ_INTRADAY = "EQ_INTRADAY"
    EQ_DELIVERY = "EQ_DELIVERY"
    FUT = "FUT"
    OPT = "OPT"


class ExitReason(StrEnum):
    STOP = "STOP"
    TARGET = "TARGET"
    TIME = "TIME"
    SQUAREOFF = "SQUAREOFF"
    RULE = "RULE"


class ExecutionMode(StrEnum):
    """Blueprint 5.12. Only PAPER is enabled in this version."""

    PAPER = "PAPER"
    SHADOW = "SHADOW"
    APPROVED_LIVE = "APPROVED_LIVE"
    AUTONOMOUS = "AUTONOMOUS"


class RejectReason(StrEnum):
    """Closed set of reasons a signal does not become a position (PLAN 6 and 5.2)."""

    KILL_SWITCH = "kill_switch"
    INVALID_INPUT = "invalid_input"
    ZERO_RISK = "zero_risk"
    POSITION_EXISTS = "position_exists"
    MAX_OPEN_POSITIONS = "max_open_positions"
    MAX_TRADES_PER_DAY = "max_trades_per_day"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    QTY_TOO_SMALL = "qty_too_small"
    NO_NEXT_BAR = "no_next_bar"
    AFTER_LAST_ENTRY = "after_last_entry"
    ENTRY_THROUGH_STOP = "entry_through_stop"
    ENTRY_THROUGH_TARGET = "entry_through_target"
