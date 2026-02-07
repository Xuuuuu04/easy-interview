## 服务器纯净部署（不使用 Docker）

目标：把本项目以“Systemd + Nginx + Certbot(LE)”方式部署到服务器，并通过域名 https://easyinterview.oyemoye.top 访问。

### 0. 前提

- 域名 A 记录已指向服务器：8.155.162.119
- 服务器能放行 80/443 端口（安全组/防火墙）

### 1. 登录服务器并准备目录

```bash
ssh root@8.155.162.119
mkdir -p /opt/easyinterview
```

### 2. 安装依赖（Debian/Ubuntu）

```bash
apt-get update
apt-get install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx
systemctl enable --now nginx
```

### 3. 拉取代码

```bash
cd /opt/easyinterview
git clone git@gitcode.com:mumu_xsy/easyinterview.git .
```

### 4. 配置 .env

把 API Key 写入：

```bash
cat >/opt/easyinterview/.env <<'EOF'
SILICONFLOW_API_KEY=你的key
EOF
chmod 600 /opt/easyinterview/.env
```

### 5. 创建运行用户、虚拟环境并安装依赖

```bash
id -u easyinterview >/dev/null 2>&1 || useradd --system --create-home --home-dir /home/easyinterview --shell /usr/sbin/nologin easyinterview
chown -R easyinterview:easyinterview /opt/easyinterview

su -s /bin/bash -c "python3 -m venv /opt/easyinterview/venv" easyinterview
su -s /bin/bash -c "/opt/easyinterview/venv/bin/pip install -U pip" easyinterview
su -s /bin/bash -c "/opt/easyinterview/venv/bin/pip install -r /opt/easyinterview/app/requirements.txt" easyinterview
```

### 6. 配置 Systemd（服务守护）

把仓库里的 `deploy/easyinterview.service` 放到 systemd：

```bash
cp /opt/easyinterview/deploy/easyinterview.service /etc/systemd/system/easyinterview.service
systemctl daemon-reload
systemctl enable --now easyinterview
systemctl status -n 50 easyinterview --no-pager
```

### 7. 配置 Nginx（反向代理）

把仓库里的 `deploy/nginx_app.conf` 放到 Nginx：

Debian/Ubuntu（推荐）：
```bash
cp /opt/easyinterview/deploy/nginx_app.conf /etc/nginx/sites-available/easyinterview.oyemoye.top
ln -sf /etc/nginx/sites-available/easyinterview.oyemoye.top /etc/nginx/sites-enabled/easyinterview.oyemoye.top
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
```

### 8. 申请并安装 Let’s Encrypt 证书

```bash
certbot --nginx -d easyinterview.oyemoye.top -m admin@oyemoye.top --agree-tos --no-eff-email --redirect --non-interactive
systemctl reload nginx
```

### 9. 验证

```bash
curl -I http://127.0.0.1:8000/ | head
curl -I https://easyinterview.oyemoye.top/ | head
```
