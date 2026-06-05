-- 歌单歌曲关联（替代原 playlists.song_ids 数组）
-- 注意：与 album_musics 不同，一首歌可以出现在多个歌单中，故 music_id 不加 UNIQUE。
CREATE TABLE playlist_musics (
    playlist_id BIGINT NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    music_id    BIGINT NOT NULL REFERENCES musics(id) ON DELETE CASCADE,
    ordinal     SMALLINT DEFAULT 0 NOT NULL, -- 歌曲在歌单中的排序位
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_playlist_musics PRIMARY KEY (playlist_id, music_id),
    CONSTRAINT uq_playlist_musics_ordinal UNIQUE (playlist_id, ordinal),
    CONSTRAINT chk_playlist_musics_ordinal_nonnegative CHECK (ordinal >= 0)
);

-- music_id 上未建额外索引：
-- 1. playlist_musics 是写密集表（添加/移除歌曲），每多一个索引就多一份写入开销。
-- 2. "某首歌在哪些歌单中" 不是核心高频查询场景，如有需要可后续补充。
-- playlist_id 已在主键中索引，无需额外建索引。
