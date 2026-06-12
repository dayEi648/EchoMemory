"""轮播推图服务：基于 Redis 的 CRUD + 排序管理。"""

import json
import uuid
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.redis_client import redis_client
from echomemory_backend.models.music import Music
from echomemory_backend.models.album import Album

logger = logging.getLogger(__name__)

CAROUSEL_KEY = "echomemory:carousel"


async def _resolve_image_url(db: AsyncSession, item_type: str, target_id: int) -> str | None:
    """根据推送种类和目标 ID 查询对应的封面图 URL。"""
    try:
        if item_type == "music":
            stmt = select(Music.cover_home_url, Music.cover_icon_url).where(Music.id == target_id)
            result = await db.execute(stmt)
            row = result.one_or_none()
            if row:
                return row.cover_home_url or row.cover_icon_url
        elif item_type == "album":
            stmt = select(Album.cover_url, Album.cover_icon_url).where(
                Album.id == target_id, Album.is_deleted == False
            )
            result = await db.execute(stmt)
            row = result.one_or_none()
            if row:
                return row.cover_url or row.cover_icon_url
    except Exception:
        logger.warning("Failed to resolve image for carousel item type=%s id=%s", item_type, target_id, exc_info=True)
    return None


async def list_carousel_items(db: AsyncSession) -> list[dict]:
    """列出所有轮播推图（按 sort_order 排序），附带解析后的封面 URL。"""
    raw = await redis_client.lrange(CAROUSEL_KEY, 0, -1)
    items = []
    for r in raw:
        try:
            item = json.loads(r)
            items.append(item)
        except json.JSONDecodeError:
            logger.warning("Corrupted carousel item in Redis: %s", r)

    # 解析封面图
    for item in items:
        item["image_url"] = await _resolve_image_url(db, item["type"], item["target_id"])

    items.sort(key=lambda x: x.get("sort_order", 0))
    return items


async def create_carousel_item(
    db: AsyncSession,
    item_type: str,
    target_id: int,
    title: str,
    description: str,
) -> dict:
    """创建轮播推图项并追加到列表末尾。"""
    items_raw = await redis_client.lrange(CAROUSEL_KEY, 0, -1)
    max_order = 0
    for r in items_raw:
        try:
            item = json.loads(r)
            if item.get("sort_order", 0) > max_order:
                max_order = item["sort_order"]
        except json.JSONDecodeError:
            pass

    new_item = {
        "id": uuid.uuid4().hex[:12],
        "type": item_type,
        "target_id": target_id,
        "title": title,
        "description": description,
        "sort_order": max_order + 1,
    }
    await redis_client.rpush(CAROUSEL_KEY, json.dumps(new_item, ensure_ascii=False))
    new_item["image_url"] = await _resolve_image_url(db, item_type, target_id)
    return new_item


async def update_carousel_item(
    db: AsyncSession,
    item_id: str,
    title: str | None = None,
    description: str | None = None,
) -> dict | None:
    """更新指定推图的标题/描述。返回更新后的项，不存在时返回 None。"""
    items_raw = await redis_client.lrange(CAROUSEL_KEY, 0, -1)
    updated = None
    new_list = []
    for r in items_raw:
        try:
            item = json.loads(r)
        except json.JSONDecodeError:
            continue
        if item.get("id") == item_id:
            if title is not None:
                item["title"] = title
            if description is not None:
                item["description"] = description
            updated = item
        new_list.append(json.dumps(item, ensure_ascii=False))

    if updated is None:
        return None

    await redis_client.delete(CAROUSEL_KEY)
    if new_list:
        await redis_client.rpush(CAROUSEL_KEY, *new_list)
    updated["image_url"] = await _resolve_image_url(db, updated["type"], updated["target_id"])
    return updated


async def delete_carousel_item(item_id: str) -> bool:
    """删除指定推图。返回是否成功删除。"""
    items_raw = await redis_client.lrange(CAROUSEL_KEY, 0, -1)
    found = False
    new_list = []
    for r in items_raw:
        try:
            item = json.loads(r)
        except json.JSONDecodeError:
            continue
        if item.get("id") == item_id:
            found = True
            continue
        new_list.append(json.dumps(item, ensure_ascii=False))

    if not found:
        return False

    await redis_client.delete(CAROUSEL_KEY)
    if new_list:
        await redis_client.rpush(CAROUSEL_KEY, *new_list)
    return True


async def reorder_carousel_items(item_ids: list[str]) -> bool:
    """按给定 ID 顺序重新排列推图。返回是否全部 ID 有效。"""
    items_raw = await redis_client.lrange(CAROUSEL_KEY, 0, -1)
    item_map: dict[str, dict] = {}
    for r in items_raw:
        try:
            item = json.loads(r)
            item_map[item["id"]] = item
        except json.JSONDecodeError:
            pass

    if len(item_ids) != len(item_map):
        return False

    new_list = []
    for i, item_id in enumerate(item_ids):
        if item_id not in item_map:
            return False
        item = item_map[item_id]
        item["sort_order"] = i
        new_list.append(json.dumps(item, ensure_ascii=False))

    await redis_client.delete(CAROUSEL_KEY)
    if new_list:
        await redis_client.rpush(CAROUSEL_KEY, *new_list)
    return True
