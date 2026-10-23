# Copyright 2019-2026 SURF, GEANT, ESnet.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Translate crontab day_of_week values to APScheduler 3.x numbering.

Crontab: 0=Sunday, 1=Monday..6=Saturday, 7=Sunday (alias).
APScheduler 3.x: 0=Monday..6=Sunday.

This module exists solely because of this mismatch and can be removed once
APScheduler adopts crontab-compatible numbering (>= v4).

To upgrade to APScheduler v4:
  1. Remove the ``<4`` upper bound from ``pyproject.toml``.
  2. Delete this module entirely.
  3. Replace every ``maybe_translate_dow(x)`` call-site with just ``x``.
"""

import importlib.metadata

#: True when the installed APScheduler is 3.x (uses 0=Monday numbering).
#: False on v4+ (crontab-compatible 0=Sunday numbering — no translation needed).
APSCHEDULER_V3: bool = tuple(
    int(x) for x in importlib.metadata.version("APScheduler").split("-")[0].split(".") if x.isdigit()
) < (4,)


def _day_of_week_shift(n: int) -> int:
    """Shift a crontab weekday number to APScheduler 3.x numbering.

    Crontab: 0=Sunday, 1=Monday..6=Saturday, 7=Sunday (alias).
    APScheduler 3.x: 0=Monday..6=Sunday. Formula: (n - 1) % 7.
    """
    if n not in range(0, 8):
        raise ValueError(f"{n!r} is not a valid weekday number (0-7)")
    return (n - 1) % 7


def _expand_and_shift(a: int, b: int, step: int) -> str:
    """Expand crontab range(a, b+1, step), shift each day, sort, and comma-join."""
    shifted_days = sorted(_day_of_week_shift(d) for d in range(a, b + 1, step))
    return ",".join(str(d) for d in shifted_days)


def _translate_dow_numeric_range(range_part: str, separator: str, step: str) -> str:
    """Translate a numeric A-B[/step] sub-expression to APScheduler 3.x."""
    a_str, _, b_str = range_part.partition("-")
    a, b = int(a_str), int(b_str)
    # Validate endpoints before any shortcut so out-of-range values (e.g. 1-8)
    # are always caught, not silently treated as full-coverage ranges.
    if a not in range(0, 8):
        raise ValueError(f"{a!r} is not a valid weekday number (0-7)")
    if b not in range(0, 8):
        raise ValueError(f"{b!r} is not a valid weekday number (0-7)")
    if a > b:
        raise ValueError(f"day_of_week range {a}-{b} is invalid: start must not exceed end")
    step_int = int(step) if separator else 1

    # Full-coverage range: spans all 7 weekdays (e.g. 0-6 or 0-7)
    if b - a + 1 >= 7:
        return "0-6" if not separator else _expand_and_shift(a, b, step_int)

    first, last = _day_of_week_shift(a), _day_of_week_shift(b)

    if first <= last:
        # Non-inverted: range order preserved after shifting
        return f"{first}-{last}/{step}" if separator else f"{first}-{last}"

    # Inverted (only when a == 0): expand if stepped, else split into "0-last,6"
    if separator:
        return _expand_and_shift(a, b, step_int)
    return "0,6" if last == 0 else f"0-{last},6"


def _translate_dow_expr(expr: str) -> str:
    """Translate one comma-separated sub-expression of a cron day_of_week field."""
    if any(c.isalpha() for c in expr):
        # named day or named range which APScheduler handles natively
        # also, _cron_field_error will raise APScheduler error in case of
        # "mixed" names & numerals (e.g., `mon-4`)
        return expr

    range_part, separator, step = expr.partition("/")

    if range_part == "*":
        if not separator:
            # plain "*" APScheduler fires every day, no shift needed
            return expr
        # "*/N": crontab steps from Sunday(0); APScheduler steps from Monday(0).
        # Expand the crontab sequence, shift each day, sort, and comma-join.
        return _expand_and_shift(0, 6, int(step))

    if "-" not in range_part:
        n = int(range_part)
        if separator:
            # N/step: crontab steps from N through 6 with the given stride.
            # Shifting N alone would produce "shifted/step" which APScheduler
            # rejects when shifted == 6 (Sunday) because the range 6..6 is
            # smaller than the step.
            # We expand the sequence first, then shift.
            # _day_of_week_shift validates n and maps 7 (Sunday alias) to 6
            _ = _day_of_week_shift(n)  # validate; raises for n outside 0..7
            # then for expansion we need the crontab origin (0), not the shifted
            # value, so normalize 7 to 0 before expanding.
            n_normalized = 0 if n == 7 else n
            return _expand_and_shift(n_normalized, 6, int(step))
        return str(_day_of_week_shift(n))

    return _translate_dow_numeric_range(range_part, separator, step)


def _translate_dow_for_apscheduler3(value: str) -> str:
    """Translate a cron day_of_week value from crontab convention to APScheduler 3.x.

    Crontab: 0=Sunday, 1=Monday..6=Saturday, 7=Sunday (alias).
    APScheduler 3.x: 0=Monday..6=Sunday.

    Named days (mon, tue, etc...) are left unchanged; APScheduler handles them natively.
    Numeric ranges whose shifted endpoints would be inverted are split or expanded
    so that APScheduler's ``RangeExpression`` never sees ``first > last``.

    Prefer ``maybe_translate_dow`` for version-aware calls; this function always translates.
    """
    return ",".join(_translate_dow_expr(expr) for expr in value.split(","))


def maybe_translate_dow(value: str) -> str:
    """Translate ``value`` for APScheduler 3.x if needed; no-op on v4+.

    Call-sites should use this function rather than ``_translate_dow_for_apscheduler3``
    directly.  When APScheduler v4 is adopted, delete this module and replace every
    ``maybe_translate_dow(x)`` call with just ``x``.
    """
    return _translate_dow_for_apscheduler3(value) if APSCHEDULER_V3 else value
