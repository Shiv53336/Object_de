class TrademindError(Exception):
    """Base error."""


class ConfigError(TrademindError):
    pass


class DataError(TrademindError):
    pass


class HoldoutAccessError(TrademindError):
    """A research run tried to read dates reserved for out-of-sample validation (PLAN 9.2)."""


class ExecutionModeError(TrademindError):
    """An execution mode other than PAPER was requested."""
