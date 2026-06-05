-- 音乐作者关联（替代原 musics.author_ids 数组）
CREATE TABLE music_authors (
    music_id   BIGINT NOT NULL REFERENCES musics(id) ON DELETE CASCADE,
    author_id  BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ordinal    SMALLINT DEFAULT 0 NOT NULL, -- 作者排序位，0=主创作者
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_music_authors PRIMARY KEY (music_id, author_id),
    CONSTRAINT uq_music_authors_ordinal UNIQUE (music_id, ordinal),
    CONSTRAINT chk_music_authors_ordinal_nonnegative CHECK (ordinal >= 0)
);

CREATE INDEX idx_music_authors_author ON music_authors (author_id);
