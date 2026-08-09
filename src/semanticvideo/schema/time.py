"""Exact media time primitives."""

from fractions import Fraction

from pydantic import Field, model_validator

from semanticvideo.schema._base import SemanticModel


class RationalRate(SemanticModel):
    """A rational rate such as 30000/1001 frames per second."""

    numerator: int = Field(gt=0)
    denominator: int = Field(default=1, gt=0)

    @property
    def fraction(self) -> Fraction:
        """Return the exact rate."""

        return Fraction(self.numerator, self.denominator)


class RationalTime(SemanticModel):
    """A non-negative integer tick count at ``rate`` ticks per second."""

    value: int = Field(ge=0)
    rate: int = Field(gt=0)

    @property
    def fraction(self) -> Fraction:
        """Return the exact time in seconds."""

        return Fraction(self.value, self.rate)

    @property
    def seconds(self) -> float:
        """Return a human-friendly, non-authoritative seconds value."""

        return float(self.fraction)


class TimeRange(SemanticModel):
    """A half-open time range ``[start, start + duration)``."""

    start: RationalTime
    duration: RationalTime

    @model_validator(mode="after")
    def require_positive_duration(self) -> "TimeRange":
        """Reject empty ranges; point observations use a one-tick duration."""

        if self.duration.value == 0:
            raise ValueError("time range duration must be positive")
        return self

    @property
    def start_fraction(self) -> Fraction:
        """Return the exact start in seconds."""

        return self.start.fraction

    @property
    def duration_fraction(self) -> Fraction:
        """Return the exact duration in seconds."""

        return self.duration.fraction

    @property
    def end_fraction(self) -> Fraction:
        """Return the exact exclusive end in seconds."""

        return self.start_fraction + self.duration_fraction


def milliseconds(value: int) -> RationalTime:
    """Construct an exact millisecond-based timestamp."""

    return RationalTime(value=value, rate=1000)
