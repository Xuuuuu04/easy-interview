# EasyInterview (易面) 品牌升级与 UI 重构计划

根据您的要求，我制定了全面的品牌升级和设计优化方案。我们将从当前的 "Lumina AI" 迁移到 **"EasyInterview" (易面)**，并引入全新的视觉风格。

## 1. 品牌重塑 (Rebranding)
*   **新名称**: **EasyInterview (易面)**
*   **Slogan**: "Unlock Your Future, The Easy Way." (智启未来，举重若轻)
*   **设计理念**: 保持原有的 Cyberpunk/Neo-Tokyo 科技感，但从冷峻的“青色 (Cyan)”转向更具神秘感和高级感的 **“霓虹紫 (Neon Purple)”**，呼应您的“易朝 (Yi Dynasty)”塔罗牌系列的神秘美学。

## 2. 视觉升级 (UI/UX Redesign)
*   **主色调 (Primary Color)**: 
    *   旧: Cyan `#06b6d4`
    *   **新: Neon Purple `#a855f7` (Tailwind `purple-500`)**
    *   辅助色: Pink `#ec4899` (保持不变，形成紫粉渐变)
*   **字体优化**: 保持 `JetBrains Mono` 的极客感，但在标题中引入更粗重的字重，增强冲击力。
*   **图标系统**: 将所有 SVG 图标从线框风格调整为带有“外发光”效果的实心/半透明风格。

## 3. 具体修改清单

### A. 静态资源 (`app/static/index.html`)
*   **Title**: 修改为 `EasyInterview // 易面 AI 终端`。
*   **Logo/Header**: 替换 "LUMINA INTELLIGENCE" 为 **"EASY INTERVIEW"**，并应用紫色的 Glitch 故障特效。
*   **颜色替换**: 全局查找替换 `cyan-` 为 `purple-` (如 `text-cyan-400` -> `text-purple-400`, `border-cyan-500` -> `border-purple-500`)。
*   **Meta**: 更新描述为 "Powered by SiliconFlow & EasyTech"。

### B. 样式表 (`app/static/style.css`)
*   **CSS 变量**: 更新 `:root` 中的 `--primary` 颜色值为 `#a855f7`。
*   **特效**: 调整 `scanline` (扫描线) 和 `grid` (网格) 的颜色，使其呈现淡紫色调。
*   **动画**: 调整 `flashUpdate` 等动画的关键帧颜色。

### C. 逻辑脚本 (`app/static/app.js`)
*   **动态渲染**: 替换所有在 JS 中硬编码的 HTML 模板字符串（如动态生成的卡片、列表项）中的颜色类名。
*   **Canvas 绘图**: 修改音频可视化和人脸识别框的 `strokeStyle` 和 `fillStyle` 为紫色系 hex 代码。

## 4. 预期效果
升级后，应用将呈现出一种类似“赛博塔罗牌”的神秘科技风格，既保留了 AI 的硬核感，又融入了“Easy”系列的独特美学。

准备好开始这次视觉进化了吗？