"""The numeric boundary for provider values."""

PLAUSIBLE_LIMIT = 10**18


def plausible(value: object) -> int | float | None:
    """Plausible IDR amounts: zero, or a magnitude from 1 to 10^18. Anything else, including NaN, infinities and
    sub-rupiah fractions, is unavailable; the bounds keep sums and ratios of returned values finite."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if value == 0 or 1 <= abs(value) <= PLAUSIBLE_LIMIT else None
