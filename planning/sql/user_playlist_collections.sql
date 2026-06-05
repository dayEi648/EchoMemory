-- 用户收藏歌单（替代原 users.collect_playlist_ids 数组）
CREATE TABLE user_playlist_collections (
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    playlist_id BIGINT NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_user_playlist_collections PRIMARY KEY (user_id, playlist_id)
);

CREATE INDEX idx_user_playlist_collections_user_time ON user_playlist_collections(user_id, created_at DESC);
