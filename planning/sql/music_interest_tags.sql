-- 音乐兴趣标签关联（与 user_interest_tags 共享 interest_tags 字典）
CREATE TABLE music_interest_tags (
    music_id        BIGINT NOT NULL REFERENCES musics(id) ON DELETE CASCADE,
    interest_tag_id BIGINT NOT NULL REFERENCES interest_tags(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_music_interest_tags PRIMARY KEY (music_id, interest_tag_id)
);

CREATE INDEX idx_music_interest_tags_tag ON music_interest_tags (interest_tag_id);
