# deploy/ 生产部署模板

Ubuntu 24.04 + Nginx + Gunicorn + systemd。完整步骤见 `docs/deployment.md`。

| 文件 | 用途 | 需替换的占位符 |
| --- | --- | --- |
| `shop.service` | systemd 单元 | `/srv/shop` 路径、`shop` 用户 |
| `nginx-shop.conf` | Nginx 站点 | `shop.example.com`、证书路径、静态目录 |

安装（在仓库根目录执行，路径按实际调整）：

```bash
sudo cp deploy/shop.service /etc/systemd/system/shop.service
sudo cp deploy/nginx-shop.conf /etc/nginx/sites-available/shop.conf
sudo ln -sf /etc/nginx/sites-available/shop.conf /etc/nginx/sites-enabled/shop.conf
```

模板不包含任何密钥；应用配置来自 `/srv/shop/shared/.env`（权限 600，属主 `shop`）。
