-- 专辑情绪标签关联（替代原 albums.emo_tags 数组）
CREATE TABLE album_emotion_tags (
    album_id       BIGINT NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    emotion_tag_id BIGINT NOT NULL REFERENCES emotion_tags(id) ON DELETE CASCADE,
    created_at     TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_album_emotion_tags PRIMARY KEY (album_id, emotion_tag_id)
);

-- 从标签方向查专辑（如"查找带有某情绪标签的专辑"）
CREATE INDEX idx_album_emotion_tags_tag ON album_emotion_tags (emotion_tag_id);
