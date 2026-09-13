"""
MetrCheck AI — Centralized Timezone and DateTime Utility (Backend)

Provides consistent UTC generation, legacy timestamp parsing, and Asia/Kolkata (IST) conversion.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

# Define Asia/Kolkata timezone with robust fallback
try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def get_current_utc_iso() -> str:
    """Generate current UTC ISO-8601 string with trailing 'Z'."""
    now_utc = datetime.now(timezone.utc)
    return now_utc.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def parse_utc_timestamp(ts_str: Optional[str]) -> datetime:
    """
    Parse an ISO timestamp string into a timezone-aware UTC datetime.
    If the timestamp is naive (legacy database record), interprets it as UTC.
    """
    if not ts_str:
        return datetime.now(timezone.utc)

    s = str(ts_str).strip()
    if not s:
        return datetime.now(timezone.utc)

    # Convert trailing 'Z' or 'z' to '+00:00' for fromisoformat compatibility
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        # Fallback to current UTC if malformed
        return datetime.now(timezone.utc)

    if dt.tzinfo is None:
        # Legacy naive timestamp -> localize as UTC
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        # Convert any existing offset to UTC
        dt = dt.astimezone(timezone.utc)

    return dt


def format_ist_datetime(ts_str: Optional[str], fmt: str = "%d %B %Y, %H:%M") -> str:
    """
    Convert a stored UTC timestamp string to Asia/Kolkata (IST) and format it.
    Example output: '07 September 2026, 14:14'
    """
    if not ts_str:
        return "Recent analysis"
    try:
        utc_dt = parse_utc_timestamp(ts_str)
        ist_dt = utc_dt.astimezone(IST)
        return ist_dt.strftime(fmt)
    except Exception:
        return str(ts_str)


def get_current_ist_datetime(fmt: str = "%d %B %Y, %H:%M:%S") -> str:
    """
    Get current timestamp in Asia/Kolkata (IST) and format it.
    Example output: '07 September 2026, 15:10:46'
    """
    return datetime.now(IST).strftime(fmt)
