-- 音乐情绪标签关联（与 user_emotion_tags 共享 emotion_tags 字典）
CREATE TABLE music_emotion_tags (
    music_id       BIGINT NOT NULL REFERENCES musics(id) ON DELETE CASCADE,
    emotion_tag_id BIGINT NOT NULL REFERENCES emotion_tags(id) ON DELETE CASCADE,
    created_at     TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_music_emotion_tags PRIMARY KEY (music_id, emotion_tag_id)
);

CREATE INDEX idx_music_emotion_tags_tag ON music_emotion_tags (emotion_tag_id);
