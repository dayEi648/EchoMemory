-- ============================================
-- 公共触发器函数（不绑定于任何单一表）
-- ============================================

-- 触发器函数：自动更新 updated_at
CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 触发器函数：根据经验值自动更新等级
CREATE OR REPLACE FUNCTION fn_update_user_level()
RETURNS TRIGGER AS $$
BEGIN
    SELECT COALESCE(MAX(level), 0) INTO NEW.level
    FROM level_config
    WHERE min_exp <= NEW.exp;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
