-- 初始化 shop 数据库与应用账号（MariaDB / MySQL 通用）
-- 用法：mariadb -u root -p < scripts/init-db.sql

CREATE DATABASE IF NOT EXISTS shop
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'shop'@'localhost' IDENTIFIED BY 'ShopDb2026!';
CREATE USER IF NOT EXISTS 'shop'@'127.0.0.1' IDENTIFIED BY 'ShopDb2026!';

GRANT ALL PRIVILEGES ON shop.* TO 'shop'@'localhost';
GRANT ALL PRIVILEGES ON shop.* TO 'shop'@'127.0.0.1';
FLUSH PRIVILEGES;

SELECT 'shop database ready' AS result;
