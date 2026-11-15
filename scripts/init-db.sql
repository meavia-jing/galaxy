-- 初始化 shop 数据库与应用账号（MariaDB / MySQL 通用）
-- 用法：mariadb -u root -p < scripts/init-db.sql

CREATE DATABASE IF NOT EXISTS shop
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'shop'@'localhost' IDENTIFIED BY 'ShopDb2026!';
CREATE USER IF NOT EXISTS 'shop'@'127.0.0.1' IDENTIFIED BY 'ShopDb2026!';

GRANT ALL PRIVILEGES ON shop.* TO 'shop'@'localhost';
GRANT ALL PRIVILEGES ON shop.* TO 'shop'@'127.0.0.1';

-- 自动化测试：pytest-django 需要创建并销毁 test_shop。
-- CREATE 是全局权限（建库必需），范围仅限于建库；test_shop 上的全权限只作用于测试库。
GRANT CREATE ON *.* TO 'shop'@'localhost';
GRANT CREATE ON *.* TO 'shop'@'127.0.0.1';
GRANT ALL PRIVILEGES ON `test_shop`.* TO 'shop'@'localhost';
GRANT ALL PRIVILEGES ON `test_shop`.* TO 'shop'@'127.0.0.1';

FLUSH PRIVILEGES;

SELECT 'shop database ready' AS result;
