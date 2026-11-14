# 云集商城 · 在线电商网站

Vue 3 + TypeScript 前端，Django 5.2 + DRF 后端，MariaDB 数据库，Redis 缓存。
支付为**模拟支付**，不发生任何真实资金交易。

## 目录

```
backend/    Django 项目（config/settings, apps/{accounts,catalog,cms,core}, common）
frontend/   Vue 3 + Vite + TypeScript 前端
docs/       验收记录、部署说明
scripts/    启动脚本
```

## 本地开发（Windows 11）

### 依赖
- Python 3.12、Node.js 22+、Git
- MariaDB 10.11（本机 `D:\DBdatabase`，服务名 `MariaDB`）
- Redis 7（本机 `D:\redis`，端口 6379）

### 1. 数据库初始化（一次性）

```sql
CREATE DATABASE shop CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'shop'@'localhost' IDENTIFIED BY '<password>';
GRANT ALL PRIVILEGES ON shop.* TO 'shop'@'localhost';
FLUSH PRIVILEGES;
```

把密码写入 `backend/.env` 的 `DB_PASSWORD`，并复制 `.env.example` 作为模板。

### 2. 后端

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
cd backend
python manage.py migrate
python manage.py seed_demo        # 演示数据（幂等）
python manage.py runserver 127.0.0.1:8000
```

### 3. 前端

```powershell
cd frontend
npm ci
npm run dev        # http://127.0.0.1:5173
```

Vite 把 `/api`、`/media`、`/admin` 代理到 `127.0.0.1:8000`。

## 演示账号

| 角色 | 用户名 | 密码 |
| --- | --- | --- |
| 管理员 | admin | ShopAdmin2026 |
| 运营 | operator | ShopOperator2026 |
| 普通用户 | demo | ShopDemo2026 |

## 主要地址

- 前台：http://127.0.0.1:5173
- API 文档（Swagger）：http://127.0.0.1:8000/api/docs/
- OpenAPI schema：http://127.0.0.1:8000/api/schema/
- 后台管理：http://127.0.0.1:8000/admin/
- 健康检查：http://127.0.0.1:8000/health/live/ 、/health/ready/

## 已实现范围（I01 + I02 部分 + I03）

- 基础框架：分层配置、统一错误结构、请求 ID、分页上限 100、OpenAPI、健康检查
- 账号：注册、登录、JWT（Access 15 分钟内存态 / Refresh HttpOnly Cookie）、
  刷新旋转与黑名单、退出、CSRF 校验、auth_version 全端失效、资料修改
- 商品：分类、商品列表/详情、搜索、白名单排序、分页、缓存与失效
- CMS：轮播、内容页（草稿/发布）

购物车、订单、支付、优惠券、通知、评价、客服为后续迭代（I04–I09），
界面入口按计划保持隐藏，并由接口层拒绝。

## 交付证据截图

| 截图 | 说明 |
| --- | --- |
| `docs/screenshots/01-home.png` | 前台首页（轮播 + 精选推荐 + 全部新品） |
| `docs/screenshots/02-admin-products.png` | Django 后台商品管理列表 |
| `docs/screenshots/03-api-swagger.png` | OpenAPI / Swagger 接口文档 |
| `docs/screenshots/04-account.png` | 个人中心（登录态与资料编辑） |

## 生产部署（Ubuntu 24.04）

见 `docs/deployment.md`：Nginx + Gunicorn + systemd 直接部署，不使用容器。
