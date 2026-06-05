-- 专辑作者关联（替代原 albums.author_ids / author_names 数组）
CREATE TABLE album_authors (
    album_id   BIGINT NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    author_id  BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ordinal    SMALLINT DEFAULT 0 NOT NULL, -- 作者排序位，0=主创作者
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_album_authors PRIMARY KEY (album_id, author_id),
    CONSTRAINT uq_album_authors_ordinal UNIQUE (album_id, ordinal),
    CONSTRAINT chk_album_authors_ordinal_nonnegative CHECK (ordinal >= 0)
);

-- 从作者方向查专辑（如"某作者的所有专辑"）
CREATE INDEX idx_album_authors_author ON album_authors (author_id);
