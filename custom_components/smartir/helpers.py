"""Pure helper functions for SmartIR (no hass, no I/O — trivially testable)."""

from __future__ import annotations


def closest_match(value: float | None, values: list[int]) -> int:
    """Return the index of the entry in ``values`` closest to ``value``.

    ``values`` is assumed sorted ascending. Used by the light platform to map a
    requested brightness/color-temperature onto the discrete steps a device
    supports.
    """
    prev_val: int | None = None
    for index, entry in enumerate(values):
        if entry > (value or 0):
            if prev_val is None:
                return index
            diff_lo = (value or 0) - prev_val
            diff_hi = entry - (value or 0)
            if diff_lo < diff_hi:
                return index - 1
            return index
        prev_val = entry

    return len(values) - 1
