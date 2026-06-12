"""Schema 关联展平工具：将 ORM join 关系转换为 Pydantic 可接受的字典结构。"""


def flatten_joined_authors(v) -> list[dict]:
    """将 MusicAuthor / AlbumAuthor 等 join 关系展平为作者字典列表。

    Args:
        v: ORM 关联列表或已展平的数据。

    Returns:
        作者字段字典列表；输入为空时返回空列表。
    """
    if not v:
        return []
    if isinstance(v[0], dict):
        return v
    return [
        {
            "id": a.author.id,
            "username": a.author.username,
            "nickname": a.author.nickname,
            "avatar_url": a.author.avatar_url,
            "ordinal": a.ordinal,
        }
        for a in v
    ]


def flatten_emotion_tag_joins(v) -> list[dict]:
    """将 *EmotionTag join 关系展平为标签字典列表。

    Args:
        v: ORM 关联列表或已展平的数据。

    Returns:
        标签字段字典列表；输入为空时返回空列表。
    """
    if not v:
        return []
    if isinstance(v[0], dict):
        return v
    return [
        {"id": et.emotion_tag.id, "name": et.emotion_tag.name}
        for et in v
    ]


def flatten_interest_tag_joins(v) -> list[dict]:
    """将 *InterestTag join 关系展平为标签字典列表。

    Args:
        v: ORM 关联列表或已展平的数据。

    Returns:
        标签字段字典列表；输入为空时返回空列表。
    """
    if not v:
        return []
    if isinstance(v[0], dict):
        return v
    return [
        {"id": it.interest_tag.id, "name": it.interest_tag.name}
        for it in v
    ]
