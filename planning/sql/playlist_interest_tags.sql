-- 歌单兴趣标签关联（替代原 playlists.interest_tags 数组）
CREATE TABLE playlist_interest_tags (
    playlist_id     BIGINT NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    interest_tag_id BIGINT NOT NULL REFERENCES interest_tags(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_playlist_interest_tags PRIMARY KEY (playlist_id, interest_tag_id)
);

-- 从标签方向查歌单（如"查找带有某兴趣标签的歌单"）
CREATE INDEX idx_playlist_interest_tags_tag ON playlist_interest_tags (interest_tag_id);
