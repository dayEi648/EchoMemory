from datetime import timedelta


def timedelta_to_iso8601_duration(td: timedelta | None) -> str | None:
    """Convert a Python timedelta to an ISO 8601 duration string.

    Examples:
        timedelta(days=7)     -> "P7D"
        timedelta(hours=1)    -> "PT1H"
        timedelta(days=1, hours=2, minutes=30, seconds=15) -> "P1DT2H30M15S"
    """
    if td is None:
        return None
    days = td.days
    hours, rem = divmod(td.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    result = "P"
    if days:
        result += f"{days}D"
    if hours or minutes or seconds:
        result += "T"
        if hours:
            result += f"{hours}H"
        if minutes:
            result += f"{minutes}M"
        if seconds:
            result += f"{seconds}S"
    if result == "P":
        result = "PT0S"
    return result


def parse_iso8601_duration(value: str | None) -> timedelta | None:
    """Parse an ISO 8601 duration string into a Python timedelta.

    Supports formats like P7D, PT1H, P1DT2H30M15S.
    Returns None for None input.
    """
    if value is None:
        return None
    if not value.startswith("P"):
        raise ValueError("ISO 8601 duration must start with P")

    s = value[1:]  # strip leading P
    days = 0
    hours = 0
    minutes = 0
    seconds = 0

    if "T" in s:
        date_part, time_part = s.split("T", 1)
    else:
        date_part = s
        time_part = ""

    # Parse date part (only D supported for now)
    if date_part:
        import re

        m = re.match(r"(\d+)D", date_part)
        if m:
            days = int(m.group(1))
        elif date_part:
            raise ValueError(f"Unsupported ISO 8601 duration date part: {date_part}")

    # Parse time part
    if time_part:
        import re

        m = re.match(r"(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", time_part)
        if not m:
            raise ValueError(f"Unsupported ISO 8601 duration time part: {time_part}")
        if m.group(1):
            hours = int(m.group(1))
        if m.group(2):
            minutes = int(m.group(2))
        if m.group(3):
            seconds = int(m.group(3))

    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
