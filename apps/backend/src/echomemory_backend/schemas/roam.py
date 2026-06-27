"""私人漫游（Private Roam）请求与响应 Schema。"""

from pydantic import BaseModel, ConfigDict, Field

from echomemory_backend.schemas.music import MusicOut


class RoamDislikeReasons(BaseModel):
    """明确不喜欢时可选的标签级原因。

    未提供任何字段时视为仅 dislike 歌曲本身（不涉及标签）。
    """

    emotion_tag_ids: list[int] | None = Field(default=None)
    interest_tag_ids: list[int] | None = Field(default=None)
    style_id: int | None = Field(default=None)
    language_id: int | None = Field(default=None)


class RoamStateOut(BaseModel):
    """漫游 session 完整状态。"""

    model_config = ConfigDict(from_attributes=True)

    playlist: list[int]
    position: int
    current_song: MusicOut
    pref_pool_summary: dict[str, str]
    dislike_pool_summary: dict[str, str]
    recommend_reason: str | None = None


class RoamReportOut(BaseModel):
    """漫游结束品味总结报告。"""

    model_config = ConfigDict(from_attributes=True)

    total_songs: int
    favorited_count: int
    disliked_count: int
    favorited_songs: list[MusicOut]
    taste_summary: str
    recommendation: str | None = None


class RoamGuideRequest(BaseModel):
    """自然语言引导请求。"""

    hint: str = Field(min_length=1, max_length=100)


class RoamGuideResponse(BaseModel):
    """自然语言引导响应。"""

    model_config = ConfigDict(from_attributes=True)

    parsed_intent: str
    adjustments: dict
    new_state: RoamStateOut
