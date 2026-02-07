# EasyInterview（智能面试系统）- 项目体检

最后复核：2026-02-05

## 状态
- 状态标签：active
- 定位：多场景面试系统（题库驱动 + 简历解析 + 多模态接口 + 部署脚本）。

## 架构速览
- 后端入口：`app/main.py`（FastAPI）
- 路由层：`app/api/routes/`（system/interview）
- 服务层：`app/services/`（LLM、面试流程、文件处理等）
- 题库：`app/question_bank/packs/`
- 前端：`app/static/`（静态 HTML/JS）
- 部署：`deploy/`（systemd + nginx + certbot）
- 架构说明：`CLAUDE.md`（已包含模块结构图与端点列表）

## 文档改进（已完成）
- 将 README 与部署文档中的本地 `file://` 链接改为仓库相对路径，便于跨设备使用。

## 重要风险（需要尽快处理）
- 仓库根目录存在 `.env`，属于高风险文件：建议删除并改用 `.env.example`（只保留模板，不含 key）。
- 发现 `app/venv/`：建议不要提交虚拟环境目录（体积大、易过期、混入第三方文件）；改用 `requirements.txt` + 本地 venv 生成。
- 存在 `模型文档与key.txt`：建议迁移到本地私密笔记或改名为不含 key 的说明文档，避免误分享。

## 下一步（对齐你的目标）
- 增加最小测试：`app/tests/` + `pytest`，至少覆盖 1-2 条核心流程（生成面试计划、题库检索、对话一轮）。
- 增加评测与回归：固定一组简历样例/对话样例，做离线回归脚本输出对比（成本低，收益高）。

