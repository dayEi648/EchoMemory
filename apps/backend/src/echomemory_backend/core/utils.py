from datetime import timedelta


def timedelta_to_iso8601_duration(td: timedelta | None) -> str | None:
    """将 Python timedelta 转换为 ISO 8601 持续时间字符串。

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
    """将 ISO 8601 持续时间字符串解析为 Python timedelta。

    支持 P7D、PT1H、P1DT2H30M15S 等格式。
    输入为 None 时返回 None。
    """
    if value is None:
        return None
    if not value.startswith("P"):
        raise ValueError("ISO 8601 duration must start with P")

    s = value[1:]  # 去掉开头的 P
    days = 0
    hours = 0
    minutes = 0
    seconds = 0
    has_component = False

    if "T" in s:
        date_part, time_part = s.split("T", 1)
    else:
        date_part = s
        time_part = ""

    # 解析日期部分（目前仅支持 D）
    if date_part:
        import re

        m = re.fullmatch(r"(\d+)D", date_part)
        if m:
            days = int(m.group(1))
            has_component = True
        else:
            raise ValueError(f"Unsupported ISO 8601 duration date part: {date_part}")

    # 解析时间部分
    if time_part:
        import re

        m = re.fullmatch(r"(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", time_part)
        if not m:
            raise ValueError(f"Unsupported ISO 8601 duration time part: {time_part}")
        if m.group(1):
            hours = int(m.group(1))
            has_component = True
        if m.group(2):
            minutes = int(m.group(2))
            has_component = True
        if m.group(3):
            seconds = int(m.group(3))
            has_component = True

    # 空 duration（如 "P"、"PT"）视为非法
    if not has_component:
        raise ValueError("ISO 8601 duration must contain at least one component")

    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
