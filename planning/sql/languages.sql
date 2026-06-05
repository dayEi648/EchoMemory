-- 语言字典
CREATE TABLE languages (
    id   SMALLINT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    CONSTRAINT uq_languages_name UNIQUE (name)
);
