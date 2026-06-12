-- 播放记录表
CREATE TABLE play_history (
    id        BIGSERIAL PRIMARY KEY,
    user_id   BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    music_id  BIGINT NOT NULL REFERENCES musics(id) ON DELETE CASCADE,
    played_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 复合索引：按用户查询最近播放记录（核心读取场景）
CREATE INDEX idx_play_history_user_time ON play_history(user_id, played_at DESC);

-- 唯一索引：同一用户对同一首歌仅保留一条记录
CREATE UNIQUE INDEX uq_play_history_user_music ON play_history(user_id, music_id);

-- 触发器函数：维护每个用户最多100条去重播放记录
CREATE OR REPLACE FUNCTION fn_play_history_cleanup()
RETURNS TRIGGER AS $$
BEGIN
    -- 删除该用户对这首歌的旧记录（保留当前新记录）
    DELETE FROM play_history
    WHERE user_id = NEW.user_id
      AND music_id = NEW.music_id
      AND id <> NEW.id;

    -- 删除该用户超出100条的最旧记录
    DELETE FROM play_history
    WHERE id IN (
        SELECT id FROM play_history
        WHERE user_id = NEW.user_id
        ORDER BY played_at DESC, id DESC
        OFFSET 100
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_play_history_cleanup
    AFTER INSERT ON play_history
    FOR EACH ROW
    EXECUTE FUNCTION fn_play_history_cleanup();
