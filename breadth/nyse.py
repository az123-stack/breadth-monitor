"""NYSE full-day market holidays, computed from the exchange's rules (no list to keep up to date), and the
"entry cutoff" for a card date: 9:30 AM ET on the next trading session, when an idea carded on that date is bought.

Rules: New Year's Day (Saturday -> no holiday; Sunday -> Monday), MLK Day (3rd Mon Jan), Presidents Day (3rd Mon Feb),
Good Friday, Memorial Day (last Mon May), Juneteenth (from 2022), Independence Day, Labor Day (1st Mon Sep),
Thanksgiving (4th Thu Nov), Christmas. Saturday holidays move to Friday, Sunday holidays to Monday.
Special one-off closures (e.g. a national day of mourning) are not predictable; add them to EXTRA.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from dateutil.easter import easter

ET = ZoneInfo("America/New_York")
EXTRA = ["2025-01-09"]          # ad-hoc closures, "YYYY-MM-DD" (Jan 9 2025: national day of mourning, President Carter)


def _nth(year, month, weekday, n):
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last(year, month, weekday):
    d = date(year, month + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d, new_year=False):
    if d.weekday() == 5:
        return None if new_year else d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def holidays_for(year):
    out = [_observed(date(year, 1, 1), new_year=True), _nth(year, 1, 0, 3), _nth(year, 2, 0, 3),
           easter(year) - timedelta(days=2), _last(year, 5, 0),
           _observed(date(year, 6, 19)) if year >= 2022 else None, _observed(date(year, 7, 4)),
           _nth(year, 9, 0, 1), _nth(year, 11, 3, 4), _observed(date(year, 12, 25))]
    return sorted(d for d in out if d)


def holidays(first, last):
    return sorted({d.isoformat() for y in range(first, last + 1) for d in holidays_for(y)} | set(EXTRA))


def is_session(d, hol=None):
    hol = set(hol or holidays(d.year - 1, d.year + 1))
    return d.weekday() < 5 and d.isoformat() not in hol


def next_session(d):
    d = d + timedelta(days=1)
    hol = set(holidays(d.year - 1, d.year + 1))
    while not is_session(d, hol):
        d += timedelta(days=1)
    return d


def prev_session(d):
    d = d - timedelta(days=1)
    hol = set(holidays(d.year - 1, d.year + 1))
    while not is_session(d, hol):
        d -= timedelta(days=1)
    return d


def entry_cutoff(card_date):
    """9:30 AM ET on the session after card_date, as an aware datetime (when ideas carded that day are bought)."""
    d = card_date if isinstance(card_date, date) else date.fromisoformat(str(card_date)[:10])
    return datetime.combine(next_session(d), time(9, 30), tzinfo=ET)
