"""Keep a Windows laptop awake during the paper run, and read its AC power state. No-ops elsewhere.

Windows still sleeps when the lid closes unless the lid action is "Do nothing" (docs/TESTING.md).
"""

from __future__ import annotations

import contextlib
import ctypes
import sys
from collections.abc import Iterator

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


@contextlib.contextmanager
def keep_awake() -> Iterator[bool]:
    """Ask Windows not to sleep while the block runs. Yields whether the request was accepted."""
    if sys.platform != "win32":
        yield False
        return
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    accepted = bool(kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED))
    try:
        yield accepted
    finally:
        kernel32.SetThreadExecutionState(ES_CONTINUOUS)


class _PowerStatus(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]


def on_battery() -> bool | None:
    """True on battery, False on mains, None when unknown or not Windows."""
    if sys.platform != "win32":
        return None
    status = _PowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):  # type: ignore[attr-defined]
        return None
    return {0: True, 1: False}.get(status.ACLineStatus)
