-- 专辑歌曲关联（替代原 albums.song_ids 数组与触发器同步逻辑）
-- 说明：musics 表中原有的 album_id 外键已移除，专辑与歌曲的关联统一由本关系表维护。
CREATE TABLE album_musics (
    album_id   BIGINT NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    music_id   BIGINT NOT NULL REFERENCES musics(id) ON DELETE CASCADE,
    ordinal    SMALLINT DEFAULT 0 NOT NULL, -- 歌曲在专辑中的排序位
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_album_musics PRIMARY KEY (album_id, music_id),
    CONSTRAINT uq_album_musics_music UNIQUE (music_id), -- 一首歌只能属于一个专辑
    CONSTRAINT uq_album_musics_ordinal UNIQUE (album_id, ordinal),
    CONSTRAINT chk_album_musics_ordinal_nonnegative CHECK (ordinal >= 0)
);

-- music_id 上已有 UNIQUE 约束带来的隐式索引，无需额外建索引。
-- album_id 已在主键中索引，无需额外建索引。
