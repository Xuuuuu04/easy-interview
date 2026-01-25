// FaceTheProf Logic Core - Enhanced Version
import { FilesetResolver, FaceLandmarker } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.0/+esm";

// WAV Encoding Helpers
const writeString = (view, offset, string) => {
    for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
    }
};

const floatTo16BitPCM = (output, offset, input) => {
    for (let i = 0; i < input.length; i++, offset += 2) {
        const s = Math.max(-1, Math.min(1, input[i]));
        output.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
};

const encodeWAV = (samples, sampleRate) => {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(view, 36, 'data');
    view.setUint32(40, samples.length * 2, true);
    floatTo16BitPCM(view, 44, samples);
    return view;
};

const TTS_VOICES = ['anna', 'alex', 'bella', 'benjamin', 'charles', 'claire', 'david', 'diana'];

// Difficulty presets
const DIFFICULTY_PRESETS = {
    1: { name: "极温柔", style: "gentle, encouraging, patient, simple words", tone: "warm, supportive, comforting" },
    2: { name: "温柔", style: "friendly, approachable, easygoing", tone: "kind, soft, positive" },
    3: { name: "温和", style: "polite, respectful, moderate", tone: "balanced, courteous" },
    4: { name: "友好", style: "professional but warm, clear", tone: "constructive, helpful" },
    5: { name: "中等", style: "neutral, professional, standard", tone: "objective, balanced" },
    6: { name: "严格", style: "formal, demanding, precise", tone: "serious, expectant" },
    7: { name: "较严厉", style: "challenging, probing, critical", tone: "sharp, analytical" },
    8: { name: "严厉", style: "tough, skeptical, deep-digging", tone: "stern, pressing" },
    9: { name: "极严厉", style: "harsh, grueling, relentless", tone: "severe, uncompromising" },
    10: { name: "地狱", style: "brutal, impossible, crushing", tone: "merciless, devastating" }
};

const app = {
    state: {
        isRecording: false,
        visionModel: null,
        videoEl: null,
        canvasEl: null,
        ctx: null,
        gazeWarningActive: false,

        audioContext: null,
        mediaStreamSource: null,
        scriptProcessor: null,
        audioBuffers: [],
        recordingStartTime: 0,
        history: [],
        resumeText: "",

        selectedScenario: 'tech_backend',
        selectedLanguage: 'zh-CN',
        scenarios: [],
        currentVoice: null,  // Random voice for current interview session
        difficulty: 5,  // Interview difficulty 1-10

        // Cheat Counter
        cheatCount: 0,

        // 新增：视频帧分析
        videoFrameBuffer: [],
        lastFrameCapture: 0,
        frameCaptureInterval: 1000 // 每秒截取一帧
    },

    init: async () => {
        // Filter out specific console warnings
        const originalWarn = console.warn;
        console.warn = function (...args) {
            const msg = args.join(' ');
            if (msg.includes('Face blendshape model contains CPU only ops') ||
                msg.includes('ScriptProcessorNode is deprecated') ||
                msg.includes('The ScriptProcessorNode is deprecated') ||
                msg.includes('OpenGL error checking is disabled')) {
                return;
            }
            originalWarn.apply(console, args);
        };

        console.log("🚀 系统初始化中...");
        app.state.videoEl = document.getElementById('webcam');
        app.state.canvasEl = document.getElementById('vision-canvas');
        app.state.ctx = app.state.canvasEl.getContext('2d');

        // 加载场景列表
        await app.loadScenarios();

        // 场景选择按钮事件
        const resumeInput = document.getElementById('resume-input');
        if (resumeInput) {
            resumeInput.addEventListener('change', app.handleResumeUpload);
        }

        // 难度滑块事件
        const difficultySlider = document.getElementById('difficulty-slider');
        if (difficultySlider) {
            difficultySlider.addEventListener('input', (e) => {
                app.state.difficulty = parseInt(e.target.value);
                const display = document.getElementById('stat-difficulty');
                if (display) {
                    display.textContent = app.state.difficulty;
                    display.className = `font-mono ${app.state.difficulty >= 8 ? 'text-red-400' : (app.state.difficulty >= 6 ? 'text-yellow-400' : 'text-orange-400')}`;
                }
                console.log(`🎚️ 难度调整为: ${DIFFICULTY_PRESETS[app.state.difficulty].name} (${app.state.difficulty}/10)`);
            });
        }

        // Voice Selection Init
        const voiceSelect = document.getElementById('voice-select');
        if (voiceSelect) {
            voiceSelect.innerHTML = TTS_VOICES.map(v => `<option value="${v}">${v.charAt(0).toUpperCase() + v.slice(1)}</option>`).join('');
            
            // Load from localStorage or Random default
            const savedVoice = localStorage.getItem('easyinterview_voice');
            const defaultVoice = savedVoice && TTS_VOICES.includes(savedVoice) ? savedVoice : TTS_VOICES[Math.floor(Math.random() * TTS_VOICES.length)];
            
            app.state.currentVoice = defaultVoice;
            voiceSelect.value = defaultVoice;
            
            voiceSelect.addEventListener('change', (e) => {
                app.state.currentVoice = e.target.value;
                localStorage.setItem('easyinterview_voice', app.state.currentVoice);
                console.log('🎤 Voice manually set to:', app.state.currentVoice);
            });
        }

        // 初始化 MediaPipe Vision
        try {
            const vision = await FilesetResolver.forVisionTasks(
                "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.0/wasm"
            );
            app.state.visionModel = await FaceLandmarker.createFromOptions(vision, {
                baseOptions: {
                    modelAssetPath: `https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task`,
                    delegate: "GPU"
                },
                outputFaceBlendshapes: true,
                runningMode: "VIDEO",
                numFaces: 1
            });
            console.log("✅ 视觉模型加载完成");
        } catch (e) {
            console.error("❌ 视觉模型初始化失败", e);
        }
    },

    // 新增：加载场景列表
    loadScenarios: async () => {
        try {
            const res = await fetch('/api/scenarios');
            const data = await res.json();
            app.state.scenarios = data.scenarios;
            app.renderScenarioGrid();
            console.log(`✅ Loaded ${app.state.scenarios.length} scenarios`);
        } catch (err) {
            console.error("❌ Failed to load scenarios:", err);
        }
    },

    // 新增：渲染场景选择网格 (分组)
    renderScenarioGrid: () => {
        const grid = document.getElementById('scenario-grid');
        if (!grid) return;

        const categories = {
            'tech': '💻 Technical / 技术岗位',
            'non_tech': '👔 Product & Management / 产品与管理',
            'language': '🌍 Language / 语言考核',
            'fun': '🎉 Entertainment / 娱乐模式'
        };

        // Helper to check if a category has items
        const hasItems = (cat) => app.state.scenarios.some(s => s.category === cat);

        let html = '';

        // Loop through defined categories
        for (const [catKey, catName] of Object.entries(categories)) {
            const items = app.state.scenarios.filter(s => s.category === catKey);
            if (items.length === 0) continue;

            html += `
                <div class="col-span-full mt-6 mb-2 first:mt-0">
                    <h3 class="text-purple-400 font-bold text-sm tracking-widest border-b border-gray-700 pb-2 flex items-center gap-2">
                        ${catName}
                        <span class="text-xs text-gray-600 bg-gray-800 px-2 py-0.5 rounded-full">${items.length}</span>
                    </h3>
                </div>
            `;

            html += items.map((scenario, index) => {
                const diffColor = scenario.difficulty === 'Hard' ? 'text-red-400 border-red-500/30 bg-red-900/20' :
                    (scenario.difficulty === 'Medium' ? 'text-yellow-400 border-yellow-500/30 bg-yellow-900/20' : 'text-green-400 border-green-500/30 bg-green-900/20');

                return `
                <button
                    class="relative group p-5 border border-purple-500/20 bg-gray-900/40 backdrop-blur-md rounded-xl hover:border-purple-400/60 hover:bg-gray-800/60 transition-all duration-300 text-left flex flex-col h-full overflow-hidden hover:shadow-[0_0_30px_rgba(168,85,247,0.15)] hover:-translate-y-1"
                    data-scenario="${scenario.id}"
                    onclick="app.selectScenario('${scenario.id}')"
                >
                    <!-- Hover Scanning Effect -->
                    <div class="absolute inset-0 bg-gradient-to-r from-transparent via-purple-400/10 to-transparent -translate-x-full group-hover:animate-scan-fast pointer-events-none"></div>

                    <div class="flex items-start justify-between mb-3 relative z-10">
                        <div class="w-10 h-10 flex items-center justify-center border border-purple-500/30 rounded-lg bg-purple-950/30 text-purple-400 group-hover:scale-110 transition-transform group-hover:text-purple-300 shadow-inner">
                            <span class="text-sm font-bold font-mono">0${index + 1}</span>
                        </div>
                        <span class="text-[10px] uppercase font-mono px-2 py-1 rounded border ${diffColor}">
                            ${scenario.difficulty || 'Normal'}
                        </span>
                    </div>

                    <div class="relative z-10 flex-1">
                        <h3 class="text-white font-bold text-lg mb-1 group-hover:text-purple-300 transition-colors tracking-wide">${scenario.name}</h3>
                        <p class="text-xs text-gray-400 font-mono mb-3 uppercase tracking-wider opacity-70">${scenario.name_en}</p>
                        <p class="text-gray-300 text-sm leading-relaxed line-clamp-2 mb-4 group-hover:text-gray-100 transition-colors">${scenario.description}</p>
                    </div>

                    <div class="mt-auto pt-3 border-t border-gray-700/30 flex items-center justify-between relative z-10">
                        <div class="flex items-center gap-2 text-purple-600/80 text-xs font-mono">
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
                            <span class="group-hover:text-purple-400 transition-colors">${scenario.role}</span>
                        </div>
                        <svg class="w-4 h-4 text-gray-600 group-hover:text-purple-400 group-hover:translate-x-1 transition-all" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                        </svg>
                    </div>
                </button>
            `}).join('');
        }

        // Handle 'other' or undefined categories just in case
        const otherItems = app.state.scenarios.filter(s => !categories[s.category]);
        if (otherItems.length > 0) {
            html += `
                <div class="col-span-full mt-6 mb-2">
                    <h3 class="text-purple-400 font-bold text-sm tracking-widest border-b border-gray-700 pb-2">📂 Others / 其他</h3>
                </div>
            `;
            html += otherItems.map(scenario => `...`).join(''); // Simplified for now
        }

        grid.innerHTML = html;
    },

    // 新增：选择场景
    selectScenario: (scenarioId) => {
        app.state.selectedScenario = scenarioId;
        const scenario = app.state.scenarios.find(s => s.id === scenarioId);

        // Language Constraint Logic
        const langBtns = document.querySelectorAll('.lang-btn');
        if (scenario && scenario.id.includes('ielts') || scenario.id === 'english_only') { // Simple heuristic or property
            // Force English
            app.selectLanguage('en-US');
            langBtns.forEach(btn => {
                if (btn.dataset.lang !== 'en-US') {
                    btn.disabled = true;
                    btn.classList.add('opacity-30', 'cursor-not-allowed', 'line-through');
                    btn.title = "This scenario requires English";
                } else {
                    btn.disabled = false;
                    btn.innerHTML = 'EN <span class="text-[10px] ml-1">🔒</span>';
                }
            });
        } else {
            // Unlock
            langBtns.forEach(btn => {
                btn.disabled = false;
                btn.classList.remove('opacity-30', 'cursor-not-allowed', 'line-through');
                btn.title = "";
                btn.innerHTML = btn.dataset.lang === 'zh-CN' ? 'CN' : 'EN';
            });
        }

        // 更新UI选中状态
        document.querySelectorAll('button[data-scenario]').forEach(btn => {
            const isSelected = btn.dataset.scenario === scenarioId;
            // Reset base classes
            btn.classList.remove('shadow-[0_0_30px_rgba(168,85,247,0.15)]', 'border-purple-400/60', 'bg-gray-800/60');
            btn.classList.add('border-purple-500/20', 'bg-gray-900/40');

            if (isSelected) {
                btn.classList.remove('border-purple-500/20', 'bg-gray-900/40');
                btn.classList.add('border-purple-400', 'bg-purple-900/20', 'shadow-[0_0_30px_rgba(168,85,247,0.3)]', 'scale-[1.02]');

                // Add "Selected" indicator if not present
                if (!btn.querySelector('.selected-indicator')) {
                    const indicator = document.createElement('div');
                    indicator.className = 'selected-indicator absolute top-2 right-2 text-purple-400 animate-pulse';
                    indicator.innerHTML = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>';
                    btn.appendChild(indicator);
                }
            } else {
                // Remove indicator
                const indicator = btn.querySelector('.selected-indicator');
                if (indicator) indicator.remove();
            }
        });

        // 显示简历上传区域
        document.getElementById('resume-section').classList.remove('hidden');
        // Scroll to resume section smoothly
        document.getElementById('resume-section').scrollIntoView({ behavior: 'smooth', block: 'start' });

        console.log(`✅ Scenario selected: ${scenarioId}`);
    },

    // 新增：选择语言
    selectLanguage: (lang) => {
        app.state.selectedLanguage = lang;

        // Language Toggle
        document.querySelectorAll('.lang-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                // Update active state
                document.querySelectorAll('.lang-btn').forEach(b => {
                    b.classList.remove('active', 'bg-purple-900/20', 'border-purple-500/50', 'text-purple-400');
                    b.classList.add('bg-transparent', 'border-gray-600', 'text-gray-400');
                });

                const target = e.target;
                target.classList.remove('bg-transparent', 'border-gray-600', 'text-gray-400');
                target.classList.add('active', 'bg-purple-900/20', 'border-purple-500/50', 'text-purple-400');

                // Update State
                app.state.selectedLanguage = target.dataset.lang;
                console.log("Language switched to:", app.state.selectedLanguage);
            });
        });
    },

    gotoSetup: async () => {
        document.getElementById('page-landing').classList.add('hidden');
        document.getElementById('page-scenario').classList.remove('hidden');
        document.getElementById('page-scenario').classList.add('flex');

        // 绑定语言按钮事件
        document.querySelectorAll('.lang-btn').forEach(btn => {
            btn.addEventListener('click', () => app.selectLanguage(btn.dataset.lang));
        });
    },

    handleResumeUpload: async (e) => {
        const file = e.target.files[0];
        if (file) {
            app.state.selectedFile = file;
            // UI Update
            const infoEl = document.getElementById('file-name-display');
            if (infoEl) {
                infoEl.innerText = file.name;
                infoEl.classList.remove('hidden');
            }
            document.getElementById('drop-zone').classList.add('border-purple-500', 'bg-purple-900/20');
        }
    },

    submitContext: async () => {
        const file = app.state.selectedFile;
        const manualText = document.getElementById('manual-context')?.value.trim();

        if (!file && !manualText) {
            alert("请先上传文件或输入文本内容 / Please provide context material.");
            return;
        }

        const status = document.getElementById('upload-status');
        const btn = document.getElementById('btn-submit-context');
        const inputs = [
            document.getElementById('resume-input'),
            document.getElementById('manual-context'),
            ...document.querySelectorAll('.lang-btn'),
            ...document.querySelectorAll('#scenario-grid button')
        ];

        status.classList.remove('hidden');
        status.innerHTML = `<span class="animate-pulse">⏳ 正在深入分析资料... 请耐心等待 30-60 秒 / Analyzing context... Please wait</span>`;
        
        // Lock UI
        btn.disabled = true;
        btn.innerHTML = `<svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> PROCESSING...`;
        btn.classList.add('opacity-50', 'cursor-not-allowed');
        
        inputs.forEach(el => {
            if(el) {
                el.disabled = true;
                el.classList.add('pointer-events-none', 'opacity-50');
            }
        });

        const formData = new FormData();
        if (file) formData.append('file', file);
        if (manualText) formData.append('manual_text', manualText);

        formData.append('scenario', app.state.selectedScenario);
        formData.append('language', app.state.selectedLanguage);

        try {
            // Step 1: Analyze Context
            const res = await fetch('/api/analyze-resume', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                console.warn("Analyze failed, falling back to direct upload");
                // Pass manualText if analyze fails? Maybe just fallback to start
                await app.startInterviewRequest(file, manualText);
                return;
            }

            const data = await res.json();
            app.state.currentPlan = data;
            // Also store resume/context text for later
            if (data.resume_text) app.state.resumeText = data.resume_text;

            app.showPlanModal();

        } catch (err) {
            console.error("Context processing error:", err);
            app.startInterviewRequest(file, manualText);
        } finally {
            status.classList.add('hidden');
            // Unlock UI
            btn.disabled = false;
            btn.innerHTML = `<span>INITIALIZE MISSION</span>
                        <svg class="w-3 h-3 group-hover:translate-x-1 transition-transform" fill="none"
                            stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                d="M14 5l7 7m0 0l-7 7m7-7H3" />
                        </svg>`;
            btn.classList.remove('opacity-50', 'cursor-not-allowed');
            
            inputs.forEach(el => {
                if(el) {
                    el.disabled = false;
                    el.classList.remove('pointer-events-none', 'opacity-50');
                }
            });
        }
    },

    showPlanModal: () => {
        const plan = app.state.currentPlan?.interview_plan || app.state.currentPlan;
        if (!plan) return;

        document.getElementById('plan-summary').innerText = plan.summary || "无法生成摘要";
        const dirList = document.getElementById('plan-directions');
        dirList.innerHTML = ''; // Clear previous

        // Render Sections (H2/H3 Structure)
        if (plan.sections) {
            dirList.innerHTML = plan.sections.map(sec => `
                <div class="mb-6">
                    <h5 class="text-purple-500 font-bold text-sm mb-3 border-b border-gray-700 pb-2 uppercase tracking-wide">${sec.title}</h5>
                    <ul class="space-y-2 pl-2 border-l-2 border-gray-800 ml-1">
                        ${sec.items.map(item => `
                            <li class="flex items-start gap-3 pl-3 text-sm text-gray-400">
                                <span class="w-1.5 h-1.5 rounded-full bg-purple-900 mt-1.5 flex-shrink-0"></span>
                                <span class="leading-relaxed">${item.content}</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
             `).join('');
        } else {
            // Fallback for old format or error
            dirList.innerHTML = `<li class="text-red-500">无法解析计划结构</li>`;
        }

        // Init Side Panel
        app.renderSidePanel(plan);

        document.getElementById('plan-modal').classList.remove('hidden');
    },

    renderSidePanel: (plan) => {
        const container = document.getElementById('plan-checklist');
        if (!container) return;

        const currentPlan = plan || app.state.currentPlan;
        if (!currentPlan || !currentPlan.sections) return;

        // Initialize state tracking if not exists
        if (!app.state.itemStates) app.state.itemStates = {};

        container.innerHTML = currentPlan.sections.map(sec => `
            <div class="mb-6 animate-fade-in-up">
                <h4 class="text-purple-600 font-bold text-xs uppercase mb-3 border-l-2 border-purple-600 pl-2 tracking-wider">
                    ${sec.title}
                </h4>
                <div class="space-y-3">
                    ${sec.items.map(item => {
                        // Animation Logic
                        const prevState = app.state.itemStates[item.id];
                        const isNewItem = !prevState;
                        const isJustCompleted = item.status === 'done' && prevState && prevState.status !== 'done';
                        const isJustUpdated = prevState && (item.content !== prevState.content || item.evaluation !== prevState.evaluation);
                        
                        // Update cache
                        app.state.itemStates[item.id] = JSON.parse(JSON.stringify(item));

                        let animClass = "";
                        let borderClass = "border-gray-700/30";
                        let bgClass = "bg-gray-800/30";
                        let icon = `<div class="w-4 h-4 rounded-full border border-gray-500 flex items-center justify-center group-hover:border-purple-400 transition-colors"></div>`;
                        let textColor = "text-gray-300";
                        let statusText = "";

                        // Determine styles based on status and animation state
                        if (isJustCompleted) {
                            animClass = "animate-flash-success";
                        } else if (isJustUpdated) {
                            animClass = "animate-flash-update";
                        } else if (isNewItem) {
                            animClass = "animate-slide-in-right";
                        }

                        if (item.status === 'done') {
                            borderClass = "border-green-500/30";
                            bgClass = "bg-green-900/10";
                            icon = `<div class="w-4 h-4 rounded-full bg-green-500 flex items-center justify-center shadow-[0_0_10px_rgba(34,197,94,0.5)]">
                                <svg class="w-2.5 h-2.5 text-black" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path></svg>
                            </div>`;
                            textColor = "text-gray-400 line-through decoration-gray-600";
                        } else if (item.is_followup) {
                            borderClass = "border-purple-500/40";
                            bgClass = "bg-purple-900/10";
                            icon = `<div class="w-4 h-4 rounded-full border border-purple-400 flex items-center justify-center text-[8px] text-purple-400 font-bold">?</div>`;
                            textColor = "text-purple-200";
                            statusText = `<span class="text-[9px] bg-purple-900/50 text-purple-300 px-1.5 py-0.5 rounded border border-purple-500/30 ml-2">FOLLOW-UP</span>`;
                        }

                        // Evaluation result display
                        let evalHtml = "";
                        if (item.evaluation) {
                            evalHtml = `
                                <div class="mt-2 pt-2 border-t border-gray-700/30 text-[10px] space-y-1 animate-fade-in-up">
                                    <div class="flex justify-between items-center">
                                        <span class="text-gray-500 font-mono">EVALUATION:</span>
                                        <span class="font-mono ${item.score >= 60 ? 'text-green-400' : 'text-orange-400'}">${item.score}/100</span>
                                    </div>
                                    <p class="text-gray-400 leading-relaxed">${item.evaluation}</p>
                                    ${item.suggestion ? `<p class="text-purple-600/80 italic">💡 ${item.suggestion}</p>` : ''}
                                </div>
                            `;
                        }

                        return `
                            <div id="item-${item.id}" class="relative group p-3 rounded-lg border ${borderClass} ${bgClass} transition-all duration-300 hover:bg-gray-800/50 ${animClass}">
                                <div class="flex gap-3 items-start">
                                    <div class="mt-0.5 shrink-0 transition-transform duration-300 group-hover:scale-110">${icon}</div>
                                    <div class="flex-1 min-w-0">
                                        <div class="text-xs font-medium ${textColor} leading-relaxed break-words">
                                            ${item.content}
                                            ${statusText}
                                        </div>
                                        ${evalHtml}
                                    </div>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `).join('');

        // Auto-scroll to bottom if polling (optional UX choice, usually better to stay where user is unless it's initial load)
        // container.scrollTop = container.scrollHeight;
    },

    showScoreModal: (scoreData) => {
        const modal = document.getElementById('score-modal');
        const valEl = document.getElementById('final-score-val');
        const commentEl = document.getElementById('final-score-comment');

        if (modal && valEl) {
            valEl.innerText = scoreData.score || "??";
            commentEl.innerText = scoreData.comment || "Evaluation Complete.";
            modal.classList.remove('hidden');

            // Optional: Confetti or sound effect here
        }
    },

    confirmPlan: () => {
        document.getElementById('plan-modal').classList.add('hidden');
        app.startInterviewRequest(app.state.selectedFile, document.getElementById('manual-context')?.value.trim());
    },

    skipPlan: () => {
        document.getElementById('plan-modal').classList.add('hidden');
        app.startInterviewRequest(app.state.selectedFile, document.getElementById('manual-context')?.value.trim());
    },

    startInterviewRequest: async (file, manualText) => {
        const status = document.getElementById('upload-status');
        if (status) {
            status.classList.remove('hidden');
            status.innerText = "正在生成开场白... / Generating opening...";
        }

        const formData = new FormData();
        if (file) formData.append('file', file);
        if (manualText) formData.append('manual_text', manualText);

        formData.append('scenario', app.state.selectedScenario);
        formData.append('language', app.state.selectedLanguage);

        try {
            const res = await fetch('/api/upload-resume', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) throw new Error("Upload Failed");

            const data = await res.json();

            // Store final text context
            if (data.resume_text) app.state.resumeText = data.resume_text;

            app.enterRoom(data.reply);

        } catch (err) {
            console.error(err);
            alert("Error starting session. Check console.");
        } finally {
            if (status) status.classList.add('hidden');
        }
    },

    enterRoom: async (openingLine) => {
        try {
            // Ensure voice is set
            if (!app.state.currentVoice) {
                const voiceSelect = document.getElementById('voice-select');
                if (voiceSelect && voiceSelect.value) {
                    app.state.currentVoice = voiceSelect.value;
                } else {
                    app.state.currentVoice = TTS_VOICES[0]; // Default fallback
                }
            }
            console.log('🎤 Starting interview with voice:', app.state.currentVoice);

            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
            app.state.videoEl.srcObject = stream;

            document.getElementById('page-scenario').classList.add('hidden');
            document.getElementById('page-scenario').classList.remove('flex');
            document.getElementById('page-room').classList.remove('hidden');
            document.getElementById('page-room').classList.add('flex');

            app.predictWebcam();
            app.drawVisualizer();
            app.startAnalysisLoop();

            // Initial UI Update
            app.updateCurrentQuestion(openingLine);
            app.appendToHistory('AI', openingLine);
            app.state.history.push({ role: "assistant", content: openingLine });

            await app.playTTS(openingLine);

        } catch (err) {
            console.error(err);
            alert("⚠️ 无法获取设备权限！\n\n请点击浏览器地址栏左侧的【锁图标 🔒】或【设置图标】，选择【重置权限】或手动允许摄像头和麦克风，然后刷新页面重试。");
        }
    },

    startAnalysisLoop: () => {
        if (app.state.analysisLoopId) clearInterval(app.state.analysisLoopId);
        app.state.analysisLoopId = setInterval(app.analyzeVideoBatch, 5000);
    },

    analyzeVideoBatch: async () => {
        if (app.state.videoFrameBuffer.length === 0) return;

        // Use the last 5 frames to avoid payload too large
        const frames = app.state.videoFrameBuffer.slice(-5);
        app.state.videoFrameBuffer = []; // Clear buffer

        try {
            const res = await fetch('/api/analyze-video', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    images: frames,
                    current_topic: app.state.selectedScenario,
                    language: app.state.selectedLanguage
                })
            });

            if (res.ok) {
                const data = await res.json();
                app.updateAnalysisUI(data);
            }
        } catch (e) {
            // console.debug("Analysis update skipped");
        }
    },

    updateAnalysisUI: (data) => {
        // Update New Metrics
        const updateMetric = (id, score) => {
            const val = Math.min(100, Math.max(0, Math.round(score || 0)));
            const labelEl = document.getElementById(`stat-${id}`);
            const barEl = document.getElementById(`bar-${id}`);
            if (labelEl) labelEl.innerText = `${val}%`;
            if (barEl) {
                barEl.style.width = `${val}%`;
            }
        };

        if (data.metrics) {
            updateMetric('confidence', data.metrics.confidence);
            updateMetric('eye', data.metrics.eye_contact);
            updateMetric('attire', data.metrics.attire);
            updateMetric('clarity', data.metrics.clarity);
        }

        // Tiered Cheat Alert
        if (data.alert && data.alert.level !== 'none') {
            app.state.cheatCount++;
            
            // Show Top Toast
            const toast = document.getElementById('cheat-alert');
            const toastReason = document.getElementById('cheat-reason');
            const toastIcon = toast.querySelector('div.rounded-full'); // The icon container
            const toastTitle = toast.querySelector('div.font-bold');

            if (toast && toastReason) {
                const isCritical = data.alert.level === 'critical';
                
                // Style based on severity
                if (isCritical) {
                    toast.firstElementChild.className = "bg-red-900/90 border border-red-500/80 backdrop-blur-xl px-6 py-3 rounded-lg shadow-[0_0_30px_rgba(239,68,68,0.4)] flex items-center gap-4 animate-slide-in-top";
                    toastIcon.className = "w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center shrink-0 animate-pulse";
                    toastTitle.className = "text-red-400 font-bold text-sm tracking-widest uppercase";
                    toastTitle.innerText = "Security Alert // 安全警告";
                } else {
                    // Warning (Yellow)
                    toast.firstElementChild.className = "bg-yellow-900/90 border border-yellow-500/80 backdrop-blur-xl px-6 py-3 rounded-lg shadow-[0_0_30px_rgba(234,179,8,0.4)] flex items-center gap-4 animate-slide-in-top";
                    toastIcon.className = "w-10 h-10 rounded-full bg-yellow-500/20 flex items-center justify-center shrink-0 animate-pulse";
                    toastTitle.className = "text-yellow-400 font-bold text-sm tracking-widest uppercase";
                    toastTitle.innerText = "Attention // 提示";
                }

                toastReason.innerText = data.alert.message_cn || data.alert.message_en || "Please adjust your camera or lighting.";
                
                toast.classList.remove('hidden');
                
                // Auto hide
                if (app.state.cheatToastTimeout) clearTimeout(app.state.cheatToastTimeout);
                app.state.cheatToastTimeout = setTimeout(() => {
                    toast.classList.add('hidden');
                }, 5000);
            }
        }
    },

    toggleMirror: () => {
        const video = document.getElementById('webcam');
        if (video) {
            if (video.style.transform === 'scaleX(-1)') {
                video.style.transform = 'scaleX(1)';
            } else {
                video.style.transform = 'scaleX(-1)';
            }
        }
    },

    appendToHistory: (role, text) => {
        const container = document.getElementById('history-container');
        if (!container) return;

        const div = document.createElement('div');
        const isAI = role === 'AI' || role === 'assistant';

        div.className = `p-3 rounded-lg text-xs leading-relaxed animate-fade-in-up ${isAI ? 'bg-purple-900/20 border border-purple-500/30 text-purple-100' : 'bg-gray-800 border border-gray-700 text-gray-300'}`;
        div.innerHTML = `
            <div class="font-bold mb-1 tracking-wider ${isAI ? 'text-purple-400' : 'text-gray-400'}">${isAI ? 'AI PROFESSOR' : 'YOU'}</div>
            <div class="prose prose-invert prose-sm max-w-none">${marked.parse(text)}</div>
        `;
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    },

    updateCurrentQuestion: (text) => {
        const el = document.getElementById('ai-text-display');
        const box = document.getElementById('current-question-box');

        if (el) {
            // Strip HTML tags for clean display in overlay
            const plainText = text.replace(/<[^>]*>/g, '').substring(0, 500) + (text.length > 500 ? '...' : '');
            el.innerText = plainText;
        }

        if (box) {
            box.classList.remove('opacity-0', 'translate-y-4');
        }
    },

    predictWebcam: () => {
        const { videoEl, canvasEl, ctx, visionModel } = app.state;

        if (videoEl.videoWidth > 0 && videoEl.videoHeight > 0) {
            canvasEl.width = videoEl.videoWidth;
            canvasEl.height = videoEl.videoHeight;
            let startTimeMs = performance.now();

            if (visionModel) {
                const results = visionModel.detectForVideo(videoEl, startTimeMs);
                ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);

                if (results.faceLandmarks.length > 0) {
                    const landmarks = results.faceLandmarks[0];
                    app.drawHUD(landmarks, results.faceBlendshapes[0]);
                }
            }

            // 新增：视频帧捕获（每秒1帧）
            app.captureVideoFrame();
        }
        window.requestAnimationFrame(app.predictWebcam);
    },

    // 新增：捕获视频帧
    captureVideoFrame: () => {
        const now = Date.now();
        if (now - app.state.lastFrameCapture > app.state.frameCaptureInterval) {
            try {
                const canvas = document.createElement('canvas');
                const size = 320; // Reduced size for bandwidth
                canvas.width = size;
                canvas.height = size * (app.state.videoEl.videoHeight / app.state.videoEl.videoWidth);
                const ctx = canvas.getContext('2d');
                ctx.drawImage(app.state.videoEl, 0, 0, canvas.width, canvas.height);

                // 转换为 base64
                const dataUrl = canvas.toDataURL('image/jpeg', 0.6);
                const base64 = dataUrl.split(',')[1];

                app.state.videoFrameBuffer.push(base64);
                app.state.lastFrameCapture = now;

                // 保持最近10帧
                if (app.state.videoFrameBuffer.length > 10) {
                    app.state.videoFrameBuffer.shift();
                }
            } catch (e) {
                console.warn("⚠️ Frame capture failed:", e);
            }
        }
    },

    drawHUD: (landmarks, blendshapes) => {
        const ctx = app.state.ctx;
        const width = app.state.canvasEl.width;
        const height = app.state.canvasEl.height;

        let minX = width, minY = height, maxX = 0, maxY = 0;
        for (const pt of landmarks) {
            const x = pt.x * width;
            const y = pt.y * height;
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
            if (y < minY) minY = y;
            if (y > maxY) maxY = y;
        }

        minX -= 20; minY -= 40; maxX += 20; maxY += 40;
        const boxW = maxX - minX;
        const boxH = maxY - minY;

        // Draw basic tracking box only, logic moved to analysis endpoint
        ctx.strokeStyle = '#a855f7';
        ctx.lineWidth = 1;

        // Corners only
        const len = 20;
        ctx.beginPath();
        // TL
        ctx.moveTo(minX, minY + len); ctx.lineTo(minX, minY); ctx.lineTo(minX + len, minY);
        // TR
        ctx.moveTo(maxX - len, minY); ctx.lineTo(maxX, minY); ctx.lineTo(maxX, minY + len);
        // BR
        ctx.moveTo(maxX, maxY - len); ctx.lineTo(maxX, maxY); ctx.lineTo(maxX - len, maxY);
        // BL
        ctx.moveTo(minX + len, maxY); ctx.lineTo(minX, maxY); ctx.lineTo(minX, maxY - len);
        ctx.stroke();

        ctx.fillStyle = '#a855f7';
        ctx.font = "10px monospace";
        ctx.fillText("TRACKING_ACTIVE", minX, minY - 10);
    },

    toggleRecording: async () => {
        const btn = document.getElementById('mic-btn');
        const icon = document.getElementById('mic-icon');
        const text = document.getElementById('mic-text');

        if (!app.state.isRecording) {
            // Stop any playing TTS when user wants to talk
            app.stopCurrentTTS();

            app.state.isRecording = true;
            app.state.audioBuffers = [];

            app.state.audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            const stream = app.state.videoEl.srcObject;
            app.state.mediaStreamSource = app.state.audioContext.createMediaStreamSource(stream);
            app.state.scriptProcessor = app.state.audioContext.createScriptProcessor(4096, 1, 1);

            app.state.scriptProcessor.onaudioprocess = (e) => {
                if (!app.state.isRecording) return;
                const inputData = e.inputBuffer.getChannelData(0);
                app.state.audioBuffers.push(new Float32Array(inputData));
            };

            app.state.mediaStreamSource.connect(app.state.scriptProcessor);
            app.state.scriptProcessor.connect(app.state.audioContext.destination);

            btn.classList.add('bg-red-900/50', 'border-red-500');
            icon.classList.add('animate-ping', 'bg-red-500', 'border-red-500');
            icon.querySelector('div').classList.remove('bg-purple-400');
            icon.querySelector('div').classList.add('bg-white');
            if (text) text.innerText = "正在录音 / RECORDING";
            if (text) text.classList.add('text-red-500', 'animate-pulse');

        } else {
            app.state.isRecording = false;

            if (app.state.mediaStreamSource) app.state.mediaStreamSource.disconnect();
            if (app.state.scriptProcessor) app.state.scriptProcessor.disconnect();
            if (app.state.audioContext) app.state.audioContext.close();

            btn.classList.remove('bg-red-900/50', 'border-red-500');
            icon.classList.remove('animate-ping', 'bg-red-500', 'border-red-500');
            icon.querySelector('div').classList.add('bg-purple-400');
            icon.querySelector('div').classList.remove('bg-white');
            if (text) text.innerText = "发送回答 / SENDING...";
            if (text) text.classList.remove('text-red-500', 'animate-pulse');

            app.processAndSendWav();
        }
    },

    processAndSendWav: async () => {
        const buffers = app.state.audioBuffers;
        if (buffers.length === 0) return;

        let totalLength = 0;
        for (let i = 0; i < buffers.length; i++) {
            totalLength += buffers[i].length;
        }

        const result = new Float32Array(totalLength);
        let offset = 0;
        for (let i = 0; i < buffers.length; i++) {
            result.set(buffers[i], offset);
            offset += buffers[i].length;
        }

        const view = encodeWAV(result, 16000);
        const blob = new Blob([view], { type: 'audio/wav' });
        app.sendAudioToAI(blob);
    },

    sendAudioToAI: async (blob) => {
        const formData = new FormData();
        formData.append("file", blob, "recording.wav");
        formData.append("history", JSON.stringify(app.state.history));
        formData.append("resume_text", app.state.resumeText);
        formData.append("scenario", app.state.selectedScenario);
        formData.append("language", app.state.selectedLanguage);
        formData.append("difficulty", app.state.difficulty.toString());  // Add difficulty level

        // Include Current Plan State for AI
        if (app.state.currentPlan && app.state.currentPlan.interview_plan) {
            formData.append("interview_plan", JSON.stringify(app.state.currentPlan.interview_plan));
        } else if (app.state.currentPlan) {
            formData.append("interview_plan", JSON.stringify(app.state.currentPlan));
        }

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                const errText = await res.text();
                throw new Error("AI Backend Error: " + errText);
            }
            const data = await res.json();

            // Update session key if provided
            if (data.session_key) {
                app.state.currentSessionKey = data.session_key;
            }

            // 解析 <hear> 标签 或 使用 data.transcript
            let aiResponseText = data.reply;
            let userHeardText = data.transcript || "(Audio)";

            const hearMatch = data.reply.match(/<hear>(.*?)<\/hear>/s);
            if (hearMatch) {
                userHeardText = hearMatch[1].trim();
                aiResponseText = data.reply.replace(/<hear>.*?<\/hear>/s, '').trim();
            }

            // 1. Text to Speech
            app.closeMicIfOpen(); // Ensure mic is closed before AI speaks
            // await app.playTTS(aiResponseText); // Removed duplicate call

            // 2. Plan Update (From Backend)
            if (data.plan_update) {
                app.state.currentPlan = data.plan_update;
                app.renderSidePanel(data.plan_update);
                console.log("✅ 计划已从后端更新");
            }

            // 3. Interview Completion Check
            if (data.interview_complete) {
                console.log("🏁 面试结束!");
                app.state.interviewComplete = true;

                // Show final score modal
                if (data.final_result) {
                    app.showScoreModal(data.final_result);
                }

                // Disable recording button
                const micBtn = document.getElementById('mic-btn');
                if (micBtn) {
                    micBtn.disabled = true;
                    micBtn.classList.add('opacity-50', 'cursor-not-allowed');
                    micBtn.title = "Interview Complete";
                }
            }

            // Update History: You
            app.appendToHistory('You', userHeardText);

            // Update History: AI
            app.appendToHistory('AI', aiResponseText);

            // Update history state
            app.state.history.push({ role: "assistant", content: aiResponseText });

            // Update Current Question Overlay
            app.updateCurrentQuestion(aiResponseText);

            // Play TTS (Single call)
            await app.playTTS(aiResponseText);

            // 3. 计划已由后端同步更新，无需轮询


        } catch (err) {
            console.error(err);
            alert("API连接错误，请检查后台日志。\n" + err.message);
        } finally {
            const text = document.getElementById('mic-text');
            if (text) text.innerText = "按住说话";
        }
    },

    playTTS: async (text) => {
        try {
            const res = await fetch('/api/tts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text, voice: app.state.currentVoice })
            });
            if (!res.ok) throw new Error("TTS Failed");

            const blob = await res.blob();
            if (blob.size === 0) {
                console.warn("TTS returned empty audio blob");
                return;
            }
            const url = URL.createObjectURL(blob);

            if (app.state.currentAudio) {
                app.state.currentAudio.pause();
                app.state.currentAudio = null;
            }

            const audio = new Audio(url);
            app.state.currentAudio = audio;
            audio.play();

            // Auto-scroll logic if needed
        } catch (e) {
            console.error(e);
        }
    },

    stopCurrentTTS: () => {
        if (app.state.currentAudio) {
            app.state.currentAudio.pause();
            app.state.currentAudio = null;
        }
    },

    closeMicIfOpen: () => {
        if (app.state.isRecording) {
            app.toggleRecording(); // Toggle off
        }
    },


    endInterview: (plan) => {
        // Calculate final score
        let totalScore = 0;
        let count = 0;

        if (plan && plan.sections) {
            plan.sections.forEach(sec => {
                sec.items.forEach(item => {
                    if (item.score) {
                        totalScore += item.score;
                        count++;
                    }
                });
            });
        }

        const avgScore = count > 0 ? Math.round(totalScore / count) : 0;

        // Wait a bit for TTS to finish mostly
        setTimeout(() => {
            app.showScoreModal({
                score: avgScore,
                comment: "所有计划项已完成。感谢参加本次面试！ All items completed. Thanks for attending!"
            });
        }, 3000);
    },

    drawVisualizer: () => {
        const canvas = document.getElementById('audio-visualizer');
        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;

        ctx.fillStyle = 'rgba(10, 5, 20, 0.3)';
        ctx.fillRect(0, 0, width, height);

        ctx.lineWidth = 2;
        ctx.strokeStyle = '#a855f7';
        ctx.beginPath();

        const sliceWidth = width / 50;
        let x = 0;

        for (let i = 0; i < 50; i++) {
            const v = app.state.isRecording ? (Math.random() * 0.8 + 0.1) : 0.1;
            const y = (v * height) / 2 + height / 4;

            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);

            x += sliceWidth;
        }

        ctx.stroke();
        requestAnimationFrame(app.drawVisualizer);
    }
};

window.app = app;
app.init();
