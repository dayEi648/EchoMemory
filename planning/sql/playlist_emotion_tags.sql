-- 歌单情绪标签关联（替代原 playlists.emo_tags 数组）
CREATE TABLE playlist_emotion_tags (
    playlist_id    BIGINT NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    emotion_tag_id BIGINT NOT NULL REFERENCES emotion_tags(id) ON DELETE CASCADE,
    created_at     TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_playlist_emotion_tags PRIMARY KEY (playlist_id, emotion_tag_id)
);

-- 从标签方向查歌单（如"查找带有某情绪标签的歌单"）
CREATE INDEX idx_playlist_emotion_tags_tag ON playlist_emotion_tags (emotion_tag_id);
