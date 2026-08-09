"""Exact time behavior."""

from fractions import Fraction

import pytest
from pydantic import ValidationError

from semanticvideo.schema.time import (
    RationalRate,
    RationalTime,
    TimeRange,
    milliseconds,
)


def test_rational_time_is_exact() -> None:
    timestamp = RationalTime(value=1001, rate=30_000)

    assert timestamp.fraction == Fraction(1001, 30_000)
    assert timestamp.seconds == pytest.approx(0.0333666667)
    assert "seconds" not in timestamp.model_dump()


def test_rational_rate_is_exact() -> None:
    assert RationalRate(numerator=30_000, denominator=1001).fraction == Fraction(
        30_000, 1001
    )


def test_time_range_computes_exact_end() -> None:
    time_range = TimeRange(start=milliseconds(1200), duration=milliseconds(800))

    assert time_range.start_fraction == Fraction(6, 5)
    assert time_range.duration_fraction == Fraction(4, 5)
    assert time_range.end_fraction == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"value": -1, "rate": 1000},
        {"value": 1, "rate": 0},
    ],
)
def test_invalid_rational_time_is_rejected(payload: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        RationalTime.model_validate(payload)


def test_empty_time_range_is_rejected() -> None:
    with pytest.raises(ValidationError, match="duration must be positive"):
        TimeRange(start=milliseconds(0), duration=milliseconds(0))
