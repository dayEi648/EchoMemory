"""内容审核输入、输出与管理接口 Schema。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ContentType = Literal["comment", "space_post"]
SafetyLevel = Literal["SAFE", "RISKY", "DANGEROUS"]
RecommendationLevel = Literal["NORMAL", "RECOMMENDED"]
ModerationStatus = Literal[
    "PENDING", "PROCESSING", "SUCCEEDED", "FAILED", "MANUAL"
]


class ModerationDecision(BaseModel):
    """模型或管理员给出的受约束审核分值。"""

    safety_score: int = Field(ge=0, le=10)
    recommendation_score: int = Field(ge=0, le=10)
    reason: str = Field(min_length=1, max_length=1000)


class ManualModerationInput(ModerationDecision):
    """管理员人工审核输入。"""


class AdminModeratedContentOut(BaseModel):
    """管理后台统一内容列表项。"""

    id: int
    content_type: ContentType
    user_id: int
    username: str
    content: str | None
    target_type: str | None = None
    target_id: int | None = None
    safety_score: int
    recommendation_score: int
    safety_level: SafetyLevel | None
    recommendation_level: RecommendationLevel | None
    moderation_status: ModerationStatus
    moderation_reason: str | None
    is_recommended: bool
    is_deleted: bool
    deletion_reason: str | None
    moderated_at: datetime | None
    created_at: datetime


class PaginatedModeratedContentOut(BaseModel):
    """管理后台内容分页响应。"""

    items: list[AdminModeratedContentOut]
    total: int


class UserContentModerationStatsOut(BaseModel):
    """用户审核统计。"""

    user_id: int
    risky_count: int
    dangerous_count: int
    recommended_count: int
    updated_at: datetime
