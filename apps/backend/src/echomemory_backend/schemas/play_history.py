from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PlayHistoryMusicOut(BaseModel):
    """播放历史中嵌套的音乐精简信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    cover_icon_url: str | None = None


class PlayHistoryOut(BaseModel):
    """单条播放历史输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    played_at: datetime
    music: PlayHistoryMusicOut


class PlayHistoryCreate(BaseModel):
    """记录播放历史的请求体。"""

    music_id: int
