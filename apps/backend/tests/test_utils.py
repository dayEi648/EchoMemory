from datetime import timedelta

import pytest

from echomemory_backend.core.utils.common import (
    escape_like,
    parse_iso8601_duration,
    timedelta_to_iso8601_duration,
)


class TestEscapeLike:
    """测试 SQL LIKE 通配符转义。"""

    def test_escape_percent_and_underscore(self):
        """应转义 % 和 _ 字符。"""
        assert escape_like("100%_done") == "100\\%\\_done"

    def test_plain_string_unchanged(self):
        """普通字符串应保持不变。"""
        assert escape_like("hello") == "hello"


class TestParseIso8601Duration:
    """测试 ISO 8601 duration 字符串解析。"""

    def test_parse_days_only(self):
        """仅包含日期部分时应正确解析。"""
        assert parse_iso8601_duration("P7D") == __import__(
            "datetime"
        ).timedelta(days=7)

    def test_parse_time_only(self):
        """仅包含时间部分时应正确解析。"""
        assert parse_iso8601_duration("PT1H2M3S") == __import__(
            "datetime"
        ).timedelta(hours=1, minutes=2, seconds=3)

    def test_parse_date_and_time(self):
        """同时包含日期和时间部分时应正确解析。"""
        assert parse_iso8601_duration("P1DT2H30M15S") == __import__(
            "datetime"
        ).timedelta(days=1, hours=2, minutes=30, seconds=15)

    def test_parse_none_returns_none(self):
        """输入 None 时应返回 None。"""
        assert parse_iso8601_duration(None) is None

    def test_parse_trailing_chars_raises(self):
        """尾随非法字符时必须抛出 ValueError。"""
        with pytest.raises(ValueError):
            parse_iso8601_duration("P7Dxxx")

    def test_parse_time_trailing_chars_raises(self):
        """时间部分尾随非法字符时必须抛出 ValueError。"""
        with pytest.raises(ValueError):
            parse_iso8601_duration("PT1H2M3Sxxx")

    def test_parse_empty_p_raises(self):
        """只有 'P' 没有内容时必须抛出 ValueError。"""
        with pytest.raises(ValueError):
            parse_iso8601_duration("P")

    def test_parse_empty_pt_raises(self):
        """只有 'PT' 没有内容时必须抛出 ValueError。"""
        with pytest.raises(ValueError):
            parse_iso8601_duration("PT")

    def test_parse_zero_duration(self):
        """全零 duration（如 P0D、PT0S）应解析为零 timedelta。"""
        assert parse_iso8601_duration("P0D") == timedelta(0)
        assert parse_iso8601_duration("PT0S") == timedelta(0)

    def test_parse_missing_p_raises(self):
        """不以 P 开头时必须抛出 ValueError。"""
        with pytest.raises(ValueError):
            parse_iso8601_duration("7D")


class TestTimedeltaToIso8601Duration:
    """测试 timedelta 转换为 ISO 8601 duration 字符串。"""

    def test_days_only(self):
        """仅包含天数时应输出 PnD。"""
        td = __import__("datetime").timedelta(days=7)
        assert timedelta_to_iso8601_duration(td) == "P7D"

    def test_time_only(self):
        """仅包含时间时应输出 PTnHnMnS。"""
        td = __import__("datetime").timedelta(hours=1, minutes=2, seconds=3)
        assert timedelta_to_iso8601_duration(td) == "PT1H2M3S"

    def test_date_and_time(self):
        """同时包含日期和时间时应输出完整格式。"""
        td = __import__("datetime").timedelta(
            days=1, hours=2, minutes=30, seconds=15
        )
        assert timedelta_to_iso8601_duration(td) == "P1DT2H30M15S"

    def test_none_returns_none(self):
        """输入 None 时应返回 None。"""
        assert timedelta_to_iso8601_duration(None) is None

    def test_zero_duration(self):
        """零 timedelta 应输出 PT0S。"""
        assert timedelta_to_iso8601_duration(timedelta(0)) == "PT0S"

    def test_zero_duration_round_trip(self):
        """零 timedelta 序列化后应能再次解析。"""
        value = timedelta_to_iso8601_duration(timedelta(0))
        assert parse_iso8601_duration(value) == timedelta(0)
