-- 音乐乐器关联（引用 instruments 字典，替代原 musics.instruments 数组）
CREATE TABLE music_instruments (
    music_id      BIGINT NOT NULL REFERENCES musics(id) ON DELETE CASCADE,
    instrument_id BIGINT NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
    created_at    TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_music_instruments PRIMARY KEY (music_id, instrument_id)
);

CREATE INDEX idx_music_instruments_instrument ON music_instruments (instrument_id);
