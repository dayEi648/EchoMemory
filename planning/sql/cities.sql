-- 城市字典
CREATE TABLE cities (
    id   SMALLINT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    CONSTRAINT uq_cities_name UNIQUE (name)
);
