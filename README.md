## EasyInterview

面向多场景的智能面试系统，包含前端交互、面试计划生成、题库驱动与评估流程。支持技术与非技术方向题库扩展，并提供一键部署脚本。

### 功能概览

- 多场景面试模板与动态计划生成
- 题库驱动的结构化提问与追问
- 简历解析与多模态接口（音频/视频/文本）
- Systemd + Nginx + Certbot 的无 Docker 部署方案

### 技术栈

- 后端：FastAPI + Uvicorn
- 前端：原生 HTML/CSS/JS
- 数据：本地题库 JSON

### 目录结构

```
app/
  api/routes/              # API 路由
  services/                # 核心服务层
  core/                    # 配置与日志
  schemas/                 # 请求模型
  question_bank/packs/     # 场景题库
  static/                  # 前端静态资源
deploy/
  DEPLOY_STEPS.md          # 服务器部署步骤
  deploy.py                # 自动化部署脚本
  easyinterview.service    # systemd 服务
  nginx_app.conf           # Nginx 反代配置
```

### 快速启动

```bash
cd app
pip install -r requirements.txt
```

创建环境变量文件：

```
SILICONFLOW_API_KEY=你的key
```

启动服务：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 接口概览

- `GET /api/scenarios` 获取可用面试场景
- `GET /api/languages` 获取语言列表
- `POST /api/analyze-resume` 生成面试计划并开始交互

### 题库说明

- 题库目录：`app/question_bank/packs/`
- 当前已覆盖 14 个场景，每个场景题量不少于 100 题

### 部署方式

- 详细步骤见 `deploy/DEPLOY_STEPS.md`
- 自动部署脚本：`deploy/deploy.py`

部署脚本环境变量：

```
DEPLOY_HOST=服务器IP或域名
DEPLOY_USER=root
DEPLOY_PASSWORD=密码
DEPLOY_KEY_PATH=私钥路径（可替代密码）
DEPLOY_REMOTE_DIR=/opt/easyinterview
DEPLOY_DOMAIN=easyinterview.oyemoye.top
DEPLOY_EMAIL=admin@oyemoye.top
DEPLOY_INCLUDE_ENV=1
```

### 服务器信息

- 域名：easyinterview.oyemoye.top
- 服务器 IP：8.155.162.119
- SSH 用户：root
- 部署目录：/opt/easyinterview
- 运行服务：easyinterview.service
- 内部端口：8000
- 对外端口：80/443
- Nginx 配置路径：/etc/nginx/sites-available/easyinterview.oyemoye.top
- 证书邮箱：admin@oyemoye.top

## 开发进度（截至 2026-02-07）
- 当前开发进度与已知风险：`docs/PROJECT_STATUS.md`
- 本仓库以可公开协作为目标维护，功能清单与后续计划以状态文档为准并持续更新。
