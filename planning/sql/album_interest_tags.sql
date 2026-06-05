-- 专辑兴趣标签关联（替代原 albums.interest_tags 数组）
CREATE TABLE album_interest_tags (
    album_id        BIGINT NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    interest_tag_id BIGINT NOT NULL REFERENCES interest_tags(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_album_interest_tags PRIMARY KEY (album_id, interest_tag_id)
);

-- 从标签方向查专辑（如"查找带有某兴趣标签的专辑"）
CREATE INDEX idx_album_interest_tags_tag ON album_interest_tags (interest_tag_id);
