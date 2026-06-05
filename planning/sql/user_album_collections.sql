-- 用户收藏专辑（替代原 users.collect_album_ids 数组）
CREATE TABLE user_album_collections (
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    album_id   BIGINT NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_user_album_collections PRIMARY KEY (user_id, album_id)
);

CREATE INDEX idx_user_album_collections_user_time ON user_album_collections(user_id, created_at DESC);
