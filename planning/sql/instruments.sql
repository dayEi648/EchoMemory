-- 乐器字典
CREATE TABLE instruments (
    id   BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    CONSTRAINT uq_instruments_name UNIQUE (name)
);
