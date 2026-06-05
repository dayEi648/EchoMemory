-- 用户发行音乐关联（替代原 users.song_ids 数组）
CREATE TABLE user_music_releases (
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    music_id   BIGINT NOT NULL REFERENCES musics(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_user_music_releases PRIMARY KEY (user_id, music_id)
);

CREATE INDEX idx_user_music_releases_user_time ON user_music_releases(user_id, created_at DESC);
