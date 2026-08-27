"""Stable activity identity helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import math
import re

from .errors import IdentityError

_INTEGER_ID = re.compile(r"^[0-9]+$")


def normalize_run_id(value: object) -> str:
    """Normalize the production numeric ID without allowing lossy coercion."""

    if isinstance(value, bool):
        raise IdentityError("run_id must not be boolean")
    if isinstance(value, int):
        candidate = str(value)
    elif isinstance(value, str):
        candidate = value.strip()
    else:
        raise IdentityError("run_id must be an integer or decimal string")
    if not candidate or not _INTEGER_ID.fullmatch(candidate):
        raise IdentityError("run_id must contain decimal digits only")
    if int(candidate) <= 0:
        raise IdentityError("run_id must be positive")
    return candidate


def run_id_from_datetime(value: datetime) -> str:
    """Derive the current FIT/running_page identity convention.

    The production data uses the UTC activity start timestamp in milliseconds.
    A naive timestamp is rejected because it would silently depend on a runner's
    local timezone.
    """

    if value.tzinfo is None or value.utcoffset() is None:
        raise IdentityError("cannot derive run_id from a naive datetime")
    milliseconds = math.floor(value.astimezone(timezone.utc).timestamp() * 1000)
    return normalize_run_id(milliseconds)
