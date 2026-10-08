"""The IDX trading calendar: weekdays less official exchange holidays, only for years with a holiday list."""

import csv
from datetime import date, timedelta
from pathlib import Path


def trading_calendar(holidays_file: Path, until: date) -> list[str]:
    """Trading dates up to `until` in every year the holiday list covers; an uncovered year has no known trading
    days, so measures needing it are blocked rather than guessed."""
    if not holidays_file.exists():
        return []
    with holidays_file.open(newline="") as handle:
        holidays = {row["date"] for row in csv.DictReader(handle)}
    days = []
    for year in sorted({int(day[:4]) for day in holidays}):
        day = date(year, 1, 1)
        while day.year == year and day <= until:
            if day.weekday() < 5 and day.isoformat() not in holidays:
                days.append(day.isoformat())
            day += timedelta(days=1)
    return days
