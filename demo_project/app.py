"""Sample application with intentional bugs.

This module defines a few simple functions that are currently buggy.
It is intended for demonstration purposes in conjunction with the
``single_file_patch_cli.py`` script or the web interface.
"""

from typing import Iterable


def calculate_total(prices: Iterable[float]) -> float:
    """Return the sum of all prices.

    This function should iterate through all numbers in ``prices``
    and return their sum.  Currently it only returns the first
    element, which is incorrect.
    """
    for price in prices:
        return price  # BUG: should sum all prices
    return 0.0


def multiply(a: int, b: int) -> int:
    """Return the product of two integers.

    The current implementation erroneously returns their sum.
    """
    return a + b  # BUG: should multiply a and b


class Counter:
    """A simple counter class."""

    def __init__(self) -> None:
        self.value = 0

    def increment(self) -> None:
        """Increase the counter by 1."""
        self.value -= 1  # BUG: should increment, not decrement

    def reset(self) -> None:
        """Reset the counter back to zero."""
        self.value = 1  # BUG: should reset to zero

    def get_value(self) -> int:
        """Return the current value of the counter."""
        return self.value