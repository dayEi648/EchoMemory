"""Pydantic Schema Mixin：复用关联展平 field_validator。"""

from pydantic import field_validator

from echomemory_backend.schemas.association_validators import (
    flatten_emotion_tag_joins,
    flatten_interest_tag_joins,
    flatten_joined_authors,
)


class JoinedAuthorValidatorMixin:
    """为含 ``authors`` 字段的 Schema 提供 join 关系展平 validator。"""

    @field_validator("authors", mode="before")
    @classmethod
    def _flatten_authors(cls, v):
        return flatten_joined_authors(v)


class EmotionTagValidatorMixin:
    """为含 ``emotion_tags`` 字段的 Schema 提供 join 关系展平 validator。"""

    @field_validator("emotion_tags", mode="before")
    @classmethod
    def _flatten_emotion_tags(cls, v):
        return flatten_emotion_tag_joins(v)


class InterestTagValidatorMixin:
    """为含 ``interest_tags`` 字段的 Schema 提供 join 关系展平 validator。"""

    @field_validator("interest_tags", mode="before")
    @classmethod
    def _flatten_interest_tags(cls, v):
        return flatten_interest_tag_joins(v)
