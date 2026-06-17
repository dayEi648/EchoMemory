-- 用户喜欢音乐关联
CREATE TABLE user_music_likes (
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    music_id   BIGINT NOT NULL REFERENCES musics(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_user_music_likes PRIMARY KEY (user_id, music_id)
);

CREATE INDEX idx_user_music_likes_user_time ON user_music_likes(user_id, created_at DESC);
