# 优化与修复计划

根据分析，我发现前端布局确实存在缺陷，且“面试难度”参数在后端完全未被使用。以下是具体的修复和优化方案：

## 1. UI 修复：解决计划列表滚动条消失问题
**目标**：防止警告框（Alerts）挤压计划列表，确保计划列表始终可滚动。

*   **修改 `app/static/style.css`**：
    *   将右侧面板容器 (`.right-panel` 或对应容器) 设置为 Flex 布局 (`display: flex; flex-direction: column; height: 100vh;`)。
    *   将警告区域 (`.alerts-container`) 设置为固定高度或自适应但不可压缩 (`flex-shrink: 0`)。
    *   将计划列表容器 (`#plan-checklist` 的父级) 设置为占据剩余空间 (`flex-grow: 1`) 并允许垂直滚动 (`overflow-y: auto`)。
    *   优化滚动条样式，确保在深色模式下可见。

## 2. 后端逻辑：真正实现“面试难度”控制
**目标**：让前端传递的“难度”参数真正影响 AI 面试官的提问风格和追问深度。

*   **修改 `app/interview_templates.py`**：
    *   更新所有 System Prompt 模板，增加 `{difficulty_level}` 和 `{difficulty_instruction}` 占位符。
*   **修改 `app/services/llm_service.py`**：
    *   在构建 Prompt 时，解析前端传递的 `difficulty` 值。
    *   **映射逻辑**：
        *   **低难度 (0-30)**: "风格亲和，主要引导候选人展示优势，不进行压力追问，容忍模糊回答。"
        *   **中难度 (31-70)**: "风格专业，对关键技术点进行适度追问，要求回答有逻辑支撑。"
        *   **高难度 (71-100)**: "风格严厉（压力面试），敏锐捕捉逻辑漏洞并尖锐反问，要求回答极具深度和具体细节。"
*   **修改 `app/api/routes/interview.py`**：
    *   确保从 API 请求中正确提取 `difficulty` 参数并传递给 Service 层。

## 3. Agent 优化：增强计划更新的实时性与准确性
**目标**：优化 Agent 工具调用，使其更智能地根据难度调整“任务完成”的判定标准。

*   **修改 `app/services/interview_service.py`**：
    *   更新 `PLAN_EVAL_SYSTEM_PROMPT`（计划评估 Agent 的提示词）。
    *   **引入难度维度**：告诉评估 Agent，如果当前是“高难度”模式，必须在候选人回答得非常透彻时才能标记任务为 `completed`，否则应生成 `modify_pending_item` 来插入追问环节。
    *   **优化工具定义**：确保 JSON 输出格式的稳定性，减少解析错误。

## 4. 前端微调（可选）
*   在前端界面上增加一个小的视觉反馈（如 Toast 或 状态标签），明确显示当前的“面试模式”（例如：“🔥 压力面试模式已激活”），让用户感知到设置已生效。
