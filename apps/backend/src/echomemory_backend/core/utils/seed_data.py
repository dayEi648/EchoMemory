"""字典表种子数据管理模块。

提供从统一 JSON 文件加载字典种子数据，并生成运行时插入 SQL 或
Alembic 迁移可用的数据能力，避免多处分发导致的数据不同步。
"""

import json
from pathlib import Path

from sqlalchemy import select

from echomemory_backend.db.session import AsyncSessionLocal
from echomemory_backend.models.dictionary import (
    EmotionTag,
    InterestTag,
    Language,
    LevelConfig,
    Style,
)


# 表名到模型类的映射
_TABLE_MODEL_MAP: dict[str, type] = {
    "level_config": LevelConfig,
    "styles": Style,
    "languages": Language,
    "emotion_tags": EmotionTag,
    "interest_tags": InterestTag,
}


def _get_seed_data_path() -> Path:
    """返回字典表种子数据 JSON 文件路径。

    Returns:
        JSON 文件绝对路径。
    """
    return Path(__file__).resolve().parent.parent.parent / "data" / "dictionary_seed.json"


def load_dictionary_seed_data() -> dict[str, list[dict]]:
    """从 JSON 文件加载字典表种子数据。

    Returns:
        以表名为键、记录列表为值的字典。
    """
    with open(_get_seed_data_path(), encoding="utf-8") as f:
        return json.load(f)


async def seed_dictionary_tables() -> None:
    """若字典表为空，则灌入种子数据。

    函数内部自行创建异步 Session，调用方无需传入数据库连接。
    """
    async with AsyncSessionLocal() as db:
        data = load_dictionary_seed_data()
        for table_name, items in data.items():
            if not items:
                continue
            model_cls = _TABLE_MODEL_MAP[table_name]
            result = await db.execute(select(model_cls))
            if result.scalars().first() is None:
                db.add_all([model_cls(**item) for item in items])
        await db.commit()


def _escape_sql_string(value: str) -> str:
    """对字符串中的单引号进行 SQL 转义。

    Args:
        value: 原始字符串。

    Returns:
        转义后的字符串，可直接拼接到 SQL 字面量中。
    """
    return value.replace("'", "''")


def _validate_level_config_row(row: dict) -> tuple[int, int, str]:
    """校验并规范化 level_config 种子行。

    Args:
        row: 含 level、min_exp、title 的字典。

    Returns:
        (level, min_exp, title) 三元组。

    Raises:
        ValueError: 字段类型或范围非法时抛出。
    """
    try:
        level = int(row["level"])
        min_exp = int(row["min_exp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid level_config row: {row}") from exc
    if not 0 <= level <= 10:
        raise ValueError(f"level must be 0-10, got {level}")
    if min_exp < 0:
        raise ValueError(f"min_exp must be non-negative, got {min_exp}")
    title = row.get("title")
    if not isinstance(title, str) or not title:
        raise ValueError(f"title must be a non-empty string: {row}")
    return level, min_exp, title


def get_dictionary_seed_sql() -> str:
    """生成用于测试初始化的字典表种子 SQL。

    Returns:
        包含 INSERT 语句的 SQL 字符串；level_config 使用 ON CONFLICT UPDATE，
        其余字典表使用 ON CONFLICT DO NOTHING。
    """
    data = load_dictionary_seed_data()
    statements: list[str] = []

    level_rows = data.get("level_config", [])
    if level_rows:
        values = ",\n    ".join(
            f"({level}, {min_exp}, '{_escape_sql_string(title)}')"
            for level, min_exp, title in (
                _validate_level_config_row(row) for row in level_rows
            )
        )
        statements.append(
            f"INSERT INTO level_config (level, min_exp, title) VALUES\n    {values}\n"
            f"ON CONFLICT (level) DO UPDATE SET\n"
            f"    min_exp = EXCLUDED.min_exp,\n"
            f"    title = EXCLUDED.title;"
        )

    for table_name in ("styles", "languages", "emotion_tags", "interest_tags"):
        rows = data.get(table_name, [])
        if not rows:
            continue
        values = ",\n    ".join(
            f"('{_escape_sql_string(row['name'])}')" for row in rows
        )
        statements.append(
            f"INSERT INTO {table_name} (name) VALUES\n    {values}\n"
            f"ON CONFLICT (name) DO NOTHING;"
        )

    return "\n\n".join(statements)
