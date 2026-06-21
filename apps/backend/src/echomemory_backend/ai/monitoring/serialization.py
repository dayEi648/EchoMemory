"""Agent 监控数据的安全序列化。"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel

_REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credentials",
    "confirmation_token",
    "password",
    "password_hash",
    "proxy_authorization",
    "refresh_token",
    "secret",
    "secret_key",
    "set_cookie",
    "token",
}


def _is_sensitive_key(key: object) -> bool:
    """判断字段名是否属于凭证或秘密信息。"""
    normalized = str(key).strip().lower().replace("-", "_")
    return normalized in _SENSITIVE_KEYS or normalized.endswith(
        ("_api_key", "_password", "_secret", "_token")
    )


def _truncate_text(value: str, max_text_length: int) -> str | dict[str, Any]:
    """按上限截断文本并保留原始长度元数据。"""
    if len(value) <= max_text_length:
        return value
    return {
        "value": value[:max_text_length],
        "is_truncated": True,
        "original_length": len(value),
    }


def serialize_monitor_value(
    value: Any,
    *,
    max_text_length: int = 32_768,
    max_collection_items: int = 200,
) -> Any:
    """把任意运行时值转换为可写入 JSONB 的安全结构。

    参数:
        value: 待序列化对象。
        max_text_length: 单个文本字段最大保留字符数。
        max_collection_items: 单个集合最大保留元素数。

    返回:
        仅包含 JSON 兼容类型的结构，敏感字段已脱敏。
    """
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _truncate_text(value, max_text_length)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Path)):
        return str(value)
    if isinstance(value, Enum):
        return serialize_monitor_value(
            value.value,
            max_text_length=max_text_length,
            max_collection_items=max_collection_items,
        )
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    elif is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)

    if isinstance(value, dict):
        result: dict[str, Any] = {}
        items = list(value.items())
        for key, item in items[:max_collection_items]:
            key_text = str(key)
            result[key_text] = (
                _REDACTED
                if _is_sensitive_key(key)
                else serialize_monitor_value(
                    item,
                    max_text_length=max_text_length,
                    max_collection_items=max_collection_items,
                )
            )
        if len(items) > max_collection_items:
            result["_collection_truncated"] = {
                "original_length": len(items),
                "retained_length": max_collection_items,
            }
        return result

    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
        result = [
            serialize_monitor_value(
                item,
                max_text_length=max_text_length,
                max_collection_items=max_collection_items,
            )
            for item in items[:max_collection_items]
        ]
        if len(items) > max_collection_items:
            result.append(
                {
                    "_collection_truncated": True,
                    "original_length": len(items),
                    "retained_length": max_collection_items,
                }
            )
        return result

    if hasattr(value, "model_dump"):
        try:
            return serialize_monitor_value(
                value.model_dump(),
                max_text_length=max_text_length,
                max_collection_items=max_collection_items,
            )
        except Exception:
            pass
    if hasattr(value, "dict"):
        try:
            return serialize_monitor_value(
                value.dict(),
                max_text_length=max_text_length,
                max_collection_items=max_collection_items,
            )
        except Exception:
            pass

    try:
        fallback = repr(value)
    except Exception:
        fallback = f"<unserializable:{type(value).__name__}>"
    return _truncate_text(fallback, max_text_length)
