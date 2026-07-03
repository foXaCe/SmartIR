"""Tests for the pure SmartIR helpers."""

from __future__ import annotations

from custom_components.smartir.helpers import closest_match


class TestClosestMatch:
    """Tests for the closest_match function."""

    def test_value_below_first_entry(self) -> None:
        """A value below the first entry returns index 0."""
        assert closest_match(5, [10, 50, 100]) == 0

    def test_value_above_last_entry(self) -> None:
        """A value above the last entry returns the last index."""
        assert closest_match(150, [10, 50, 100]) == 2

    def test_value_equal_to_last_entry(self) -> None:
        """A value equal to the last entry returns the last index."""
        assert closest_match(100, [10, 50, 100]) == 2

    def test_value_equal_to_first_entry(self) -> None:
        """A value equal to the first entry returns index 0."""
        assert closest_match(10, [10, 50, 100]) == 0

    def test_value_exact_tie_resolves_to_higher_index(self) -> None:
        """A value exactly halfway between two entries resolves to the higher index."""
        assert closest_match(30, [10, 50, 100]) == 1

    def test_value_closer_to_lower_entry(self) -> None:
        """A value clearly closer to the lower entry returns its index."""
        assert closest_match(15, [10, 50, 100]) == 0

    def test_value_closer_to_higher_entry(self) -> None:
        """A value clearly closer to the higher entry returns its index."""
        assert closest_match(45, [10, 50, 100]) == 1

    def test_value_none_defaults_to_zero(self) -> None:
        """A None value is treated as 0."""
        assert closest_match(None, [10, 50, 100]) == 0

    def test_single_value_list(self) -> None:
        """A single-entry list always returns index 0 when the value is below it."""
        assert closest_match(5, [10]) == 0

    def test_single_value_list_above(self) -> None:
        """A single-entry list returns index 0 (the last index) when the value is above it."""
        assert closest_match(100, [10]) == 0
