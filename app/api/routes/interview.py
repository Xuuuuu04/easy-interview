import json
import base64
import hashlib
import re
import uuid
import httpx
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from app.schemas.requests import VideoAnalysisRequest, TTSRequest
from app.services import file_service, llm_service, interview_service
from app.core.config import settings
from app.core.logger import logger
from app.interview_templates import INTERVIEW_TEMPLATES
from app.question_bank import get_question_pack
from app.question_bank.service import render_pack_for_prompt

router = APIRouter()

@router.post("/api/analyze-resume")
async def analyze_resume(
    file: UploadFile = File(None),
    manual_text: str = Form(None),
    scenario: str = Form("tech_backend"),
    language: str = Form("zh-CN")
):
    if not settings.API_KEY: raise HTTPException(status_code=500, detail="API Key not configured")

    session_id = uuid.uuid4().hex

    resume_text = ""
    if file:
        resume_text = file_service.parse_resume(file)
    elif manual_text:
        resume_text = manual_text.strip()
    
    if not resume_text:
        resume_text = "No specific background context provided. Please proceed with a standard interview based on the Role and Scenario."
    
    template = INTERVIEW_TEMPLATES.get(scenario, INTERVIEW_TEMPLATES["tech_backend"])
    pack_id = template.get("question_pack_id") or scenario
    question_bank_json = None
    question_bank_version = None
    try:
        pack = get_question_pack(pack_id)
        question_bank_json = render_pack_for_prompt(pack, max_questions=200)
        question_bank_version = pack.version
    except Exception as e:
        logger.warning(f"Question pack unavailable for {pack_id}: {str(e)}")

    system_prompt = f"""{template['system_prompt']}

    Current Task: Analyze the candidate's resume/context and generate a structured INTERVIEW PLAN.
    
    **MANDATORY CONSTRAINTS**:
    1. **Language**: The entire plan (titles, questions, summary) MUST be in {language}.
    2. **Role & Scenario**: You are acting strictly as {template['role']} in a {template['name']} setting.
       - Use the provided QUESTION BANK as the source of truth for interview questions.
       - You MUST vary the selection/order across sessions using the RANDOM_SEED below.
    3. **Structure**: 
       - Break down the interview into 3-5 logical phases (e.g., Intro, Specific Tech 1, Specific Tech 2, System Design, Soft Skills).
       - Ensure questions are deep, specific, and challenging (not generic).
    4. **Question Sourcing**:
       - Each plan item MUST be sourced from the QUESTION BANK below.
       - You MAY lightly tailor the wording for the candidate, but MUST keep the original meaning.
       - Every item MUST include `bank_id` referencing the original question id from the bank.
    
    RANDOM_SEED: {session_id}
    
    QUESTION BANK (JSON):
    {question_bank_json if question_bank_json else '{"pack_id": null, "version": null, "questions": []}'}
    
    Return ONLY a valid JSON object (no markdown, no extra text) with the following structure:
    {{
        "summary": "Brief professional summary of the candidate (in {language})",
        "meta": {{
            "scenario": "{scenario}",
            "session_id": "{session_id}",
            "question_pack_id": "{pack_id}",
            "question_pack_version": "{question_bank_version if question_bank_version else ''}"
        }},
        "sections": [
            {{
                "title": "Section Title (e.g. Work Experience, Java Core, etc.)",
                "items": [
                    {{ "id": "1", "bank_id": "be.001", "content": "Specific topic or question to cover", "status": "pending" }},
                    {{ "id": "2", "bank_id": "be.002", "content": "Another topic or question", "status": "pending" }}
                ]
            }}
        ],
        "initial_greeting": "Opening greeting and first question"
    }}
    
    Assign unique incrementing IDs to items (1, 2, 3...). Ensure the plan is substantial and specific.
    """

    user_prompt = f"""
    [Candidate Resume START]
    {resume_text}
    [Candidate Resume END]

    Interview Language: {language}
    Scenario: {template['name']}
    Random Seed: {session_id}

    Generate the Interview Plan JSON now in the specified language.
    """

    try:
        reply_text = await llm_service.generate_thought_response([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])

        code_block = re.search(r'```json\s*(.*?)\s*```', reply_text, re.DOTALL)
        if code_block:
            json_str = code_block.group(1)
        else:
            json_match = re.search(r'\{.*\}', reply_text, re.DOTALL)
            json_str = json_match.group(0) if json_match else ""

        if json_str:
            try:
                plan_data = json.loads(json_str)
            except json.JSONDecodeError as je:
                logger.error(f"JSON Parse Error: {je} | Content: {json_str}")
                json_str_clean = json_str.replace('\n', '')
                try:
                    plan_data = json.loads(json_str_clean)
                except:
                     plan_data = {"raw": reply_text, "summary": "Error parsing plan JSON", "sections": []}
        else:
             plan_data = {"raw": reply_text, "summary": "No JSON found in response", "sections": []}

        if isinstance(plan_data, dict):
            meta = plan_data.get("meta") if isinstance(plan_data.get("meta"), dict) else {}
            meta.setdefault("scenario", scenario)
            meta.setdefault("session_id", session_id)
            meta.setdefault("question_pack_id", pack_id)
            if question_bank_version:
                meta.setdefault("question_pack_version", question_bank_version)
            plan_data["meta"] = meta

        return {
            "resume_text": resume_text,
            "interview_plan": plan_data,
            "scenario": scenario,
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Error analyzing resume: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/analyze-video")
async def analyze_video(req: VideoAnalysisRequest):
    if not settings.API_KEY: raise HTTPException(status_code=500, detail="API Key not configured")

    if not req.images or len(req.images) == 0:
        raise HTTPException(status_code=422, detail="No images provided")

    images = req.images[:3]
    lang_instruction = "Respond in Simplified Chinese." if req.language.startswith("zh") else "Respond in English."

    system_instruction = f"""
You are an AI Interview Proctor & Analyst. Analyze the candidate's video frames.

Return a single JSON object only. No markdown. No code fences. No extra keys. No extra text.
All metric values MUST be integers between 0 and 100.

Keys MUST be exactly:
- metrics.confidence
- metrics.eye_contact
- metrics.attire
- metrics.clarity
- alert.level (one of: "none", "warning", "critical")
- alert.message_cn (string or null)
- alert.message_en (string or null)

Scoring guidance (0-100):
- confidence: facial expression + posture
- eye_contact: connection with camera/screen; do NOT penalize natural screen reading
- attire: professionalism of dress (0=messy, 100=business formal)
- clarity: video quality + lighting

Cheat detection (strictly conservative):
- ignore looking at screen, brief look-away, thinking, natural movement
- warning: lighting too dark/bright, face partially out of frame, background too messy
- critical: explicit cheating tools (phone/tablet), another person in frame, AI teleprompter glasses, black screen

Example (format must match, values are examples):
{{"metrics":{{"confidence":55,"eye_contact":60,"attire":75,"clarity":70}},"alert":{{"level":"none","message_cn":null,"message_en":null}}}}

{lang_instruction}
""".strip()

    def extract_json_object(text: str):
        if not text:
            return None
        cleaned = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).replace("```", "").strip()
        start = None
        depth = 0
        in_string = False
        escape = False
        quote_char = ""
        for i, ch in enumerate(cleaned):
            if escape:
                escape = False
                continue
            if ch == "\\":
                if in_string:
                    escape = True
                continue
            if ch in ('"', "'"):
                if in_string:
                    if ch == quote_char:
                        in_string = False
                        quote_char = ""
                else:
                    in_string = True
                    quote_char = ch
                continue
            if in_string:
                continue
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start is not None:
                        candidate = cleaned[start : i + 1]
                        try:
                            return json.loads(candidate)
                        except Exception:
                            start = None
                            continue
        return None

    def to_int_0_100(value, default=0):
        if value is None:
            return default
        try:
            if isinstance(value, str):
                v = value.replace("%", "").strip()
                num = float(v)
            else:
                num = float(value)
            if 0 < num <= 1:
                num *= 100
            elif 1 < num <= 10:
                num *= 10
            num = round(num)
            if num < 0:
                return 0
            if num > 100:
                return 100
            return int(num)
        except Exception:
            return default

    content_list = [
        {"type": "text", "text": system_instruction}
    ]

    for img_b64 in images:
        if not img_b64 or len(img_b64) < 100:
            continue
        img_url = img_b64 if img_b64.startswith("data:") else f"data:image/jpeg;base64,{img_b64}"
        content_list.append({
            "type": "image_url",
            "image_url": {"url": img_url}
        })

    if len(content_list) <= 1:
        raise HTTPException(status_code=422, detail="No valid images after filtering")

    messages = [{"role": "user", "content": content_list}]

    try:
        content = await llm_service.call_vision_model(messages)
        analysis = extract_json_object(content)
        if not isinstance(analysis, dict):
            logger.warning(f"Vision model output not JSON. Raw: {content}")
            analysis = {}

        metrics = analysis.get("metrics") if isinstance(analysis.get("metrics"), dict) else {}
        alert = analysis.get("alert") if isinstance(analysis.get("alert"), dict) else {}

        normalized = {
            "metrics": {
                "confidence": to_int_0_100(metrics.get("confidence"), 0),
                "eye_contact": to_int_0_100(metrics.get("eye_contact"), 0),
                "attire": to_int_0_100(metrics.get("attire"), 0),
                "clarity": to_int_0_100(metrics.get("clarity"), 0),
            },
            "alert": {
                "level": alert.get("level") if alert.get("level") in ("none", "warning", "critical") else "none",
                "message_cn": alert.get("message_cn") if alert.get("message_cn") not in ("", None) else None,
                "message_en": alert.get("message_en") if alert.get("message_en") not in ("", None) else None,
            },
        }
        return normalized
    except BaseException as e:
        logger.error(f"Vision Analysis Error: {str(e)}")
        return {
            "metrics": {"confidence": 0, "eye_contact": 0, "attire": 0, "clarity": 0},
            "alert": {
                "level": "none",
                "message_cn": None,
                "message_en": None,
            },
            "analysis_error": True,
        }

@router.post("/api/upload-resume")
async def upload_resume(
    file: UploadFile = File(None),
    manual_text: str = Form(None),
    scenario: str = Form("tech_backend"),
    language: str = Form("zh-CN"),
    interview_plan: str = Form("{}")  # Receive plan from frontend
):
    if not settings.API_KEY: raise HTTPException(status_code=500, detail="API Key not configured")

    resume_text = ""
    if file:
        resume_text = file_service.parse_resume(file)
    elif manual_text:
        resume_text = manual_text.strip()

    if not resume_text:
        resume_text = "No resume provided."

    # Parse the interview plan
    try:
        plan_data = json.loads(interview_plan) if interview_plan else {}
    except:
        plan_data = {}

    # Extract first question from plan
    first_question = None
    for sec in plan_data.get("sections", []):
        for item in sec.get("items", []):
            if item.get("status") != "done":
                first_question = item.get("content", "")
                break
        if first_question:
            break

    template = INTERVIEW_TEMPLATES.get(scenario, INTERVIEW_TEMPLATES["tech_backend"])

    system_prompt = f"""{template['system_prompt']}

[CRITICAL INSTRUCTION - OPENING QUESTION]

You are starting an interview session. You MUST use the FIRST question from the predefined plan below.

FIRST QUESTION FROM PLAN:
{first_question if first_question else "(No plan provided, ask a general opening question)"}

CANDIDATE CONTEXT:
{resume_text[:500] if resume_text else "No context"}

---

YOUR TASK:
1. Briefly introduce yourself as {template['role']} (1 sentence)
2. Transition naturally to ask the FIRST question above
3. Do NOT modify the question content
4. Do NOT add extra questions
5. Keep it concise and professional

Response format: "介绍语... [exact question from plan]"
"""

    try:
        reply_text = await llm_service.generate_thought_response([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate the opening with the first question. Candidate context: {resume_text[:300] if resume_text else 'None'}"}
        ])

        reply_text = re.sub(r'<think>.*?</think>', '', reply_text, flags=re.DOTALL).strip()

        return {
            "reply": reply_text,
            "resume_text": resume_text,
            "scenario": scenario,
            "language": language
        }
    except Exception as e:
        logger.error(f"Error generating opening: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/chat")
async def chat_audio(
    file: UploadFile = File(None),
    transcript: str = Form(None),
    history: str = Form("[]"),
    resume_text: str = Form(""),
    interview_plan: str = Form("{}"),
    scenario: str = Form("tech_backend"),
    language: str = Form("zh-CN"),
    difficulty: int = Form(5),
    session_id: str = Form(None)
):
    if not settings.API_KEY: raise HTTPException(status_code=500, detail="API Key not configured")

    # Difficulty presets mapping
    DIFFICULTY_PRESETS = {
        1: {"name": "极温柔", "style": "gentle, encouraging, patient, use simple words", "tone": "warm, supportive, comforting"},
        2: {"name": "温柔", "style": "friendly, approachable, easygoing", "tone": "kind, soft, positive"},
        3: {"name": "温和", "style": "polite, respectful, moderate pace", "tone": "balanced, courteous"},
        4: {"name": "友好", "style": "professional but warm, clear instructions", "tone": "constructive, helpful"},
        5: {"name": "中等", "style": "neutral, professional, standard interview style", "tone": "objective, balanced"},
        6: {"name": "严格", "style": "formal, demanding, precise expectations", "tone": "serious, expectant"},
        7: {"name": "较严厉", "style": "challenging, probing, critical thinking", "tone": "sharp, analytical"},
        8: {"name": "严厉", "style": "tough, skeptical, deep-digging into answers", "tone": "stern, pressing"},
        9: {"name": "极严厉", "style": "harsh, grueling, relentless questioning", "tone": "severe, uncompromising"},
        10: {"name": "地狱", "style": "brutal, impossible standards, crushing pressure", "tone": "merciless, devastating"}
    }

    diff_preset = DIFFICULTY_PRESETS.get(max(1, min(10, difficulty)), DIFFICULTY_PRESETS[5])

    try:
        user_transcript = ""
        
        if transcript:
             user_transcript = transcript
             logger.info(f"🎤 User input (manual): {user_transcript}")
        elif file:
            audio_content = await file.read()
            audio_b64 = base64.b64encode(audio_content).decode('utf-8')
            mime_type = file.content_type or "audio/wav"
            user_transcript = await llm_service.transcribe_audio(audio_b64, mime_type)
            logger.info(f"🎤 用户说: {user_transcript}")
        else:
            raise HTTPException(status_code=400, detail="No audio file or transcript provided")

        try: history_list = json.loads(history)
        except: history_list = []

        try: plan_data = json.loads(interview_plan)
        except: plan_data = {}
        
        if session_id:
            session_key = hashlib.md5(f"{session_id}_{scenario}".encode()).hexdigest()
        else:
            session_key = hashlib.md5(f"{resume_text[:100]}_{scenario}".encode()).hexdigest()
        
        if session_key in interview_service.plan_cache:
            logger.info(f"📥 使用缓存计划 ({session_key[:8]})...")
            plan_data = interview_service.plan_cache[session_key]
        elif plan_data and "sections" in plan_data:
            logger.info(f"💧 从前端数据恢复计划缓存 ({session_key[:8]})...")
            interview_service.plan_cache[session_key] = plan_data

        asked_set = False
        for sec in plan_data.get("sections", []):
            for item in sec.get("items", []):
                if item.get("status") != "done" and "asked" in item:
                    item.pop("asked", None)
        for sec in plan_data.get("sections", []):
            if asked_set:
                break
            for item in sec.get("items", []):
                if item.get("status") != "done":
                    item["asked"] = True
                    asked_set = True
                    break
        
        plan_desc = "CURRENT INTERVIEW PLAN STATUS:\n"
        for sec in plan_data.get("sections", []):
            plan_desc += f"- {sec['title']}:\n"
            for item in sec['items']:
                status_icon = "[x]" if item.get("status") == "done" else "[ ]"
                plan_desc += f"  {status_icon} (ID: {item['id']}) {item['content']}\n"
                
        plan_context = f"\n{plan_desc}\n\nCandidate Summary: {plan_data.get('summary', '')}"

        template = INTERVIEW_TEMPLATES.get(scenario, INTERVIEW_TEMPLATES["tech_backend"])

        system_instruction = f"""{template['system_prompt']}

        [CRITICAL INSTRUCTION - MANDATORY COMPLIANCE]

        You are executing a PRE-DEFINED interview plan with DIFFICULTY LEVEL {difficulty}/10 ({diff_preset['name']}).

        CURRENT DIFFICULTY SETTINGS:
        - Interview Style: {diff_preset['style']}
        - Tone: {diff_preset['tone']}

        IMPORTANT: Adjust your questioning and follow-up style according to this difficulty level!
        - Lower levels (1-3): Be gentle, give hints, encourage the candidate
        - Higher levels (8-10): Be relentless, challenge every answer, expose weaknesses, demand perfection

        CURRENT INTERVIEW PLAN STATUS:
        {plan_context}

        CANDIDATE SUMMARY: {plan_data.get('summary', '')}

        ---

        YOUR RESPONSE FORMAT (Strictly follow):
        1. Brief evaluation of user's answer (1-2 sentences) - Match the difficulty tone
        2. Then ask the NEXT unchecked question from the plan above

        ---

        MANDATORY RULES:
        1. **ONLY ask questions that appear in the "CURRENT INTERVIEW PLAN STATUS" above**
        2. Find the FIRST item with [ ] (unchecked) status
        3. Copy that item's content EXACTLY as your next question
        4. Do NOT add your own questions
        5. Do NOT skip questions
        6. Do NOT explore topics outside the plan
        7. If user's answer is incomplete/vague, still move to next planned question (don't digress)

        WORKFLOW:
        - Review the plan status above
        - Identify the FIRST [ ] unchecked item
        - Use that EXACT item content as your question
        - Do not ask anything else

        If ALL items are [x] checked, say "面试已结束，感谢你的参与。" and stop.
        """

        messages = [{"role": "system", "content": system_instruction}]
        messages.extend(history_list)
        messages.append({
            "role": "user",
            "content": f"[User's Spoken Answer Transcribed]:\n{user_transcript}"
        })

        import asyncio
        # Step 1: Generate main response (blocking)
        reply_text = await llm_service.generate_thought_response(messages, model=settings.MODEL_TOOL)

        logger.info(f"📝 回复内容: {reply_text[:100]}...")

        # Step 2: Immediately return response to frontend
        # Step 3: Start background plan evaluation while user is listening to TTS
        
        # Create a copy of messages and append the AI's reply so the evaluator sees the full context
        # This ensures the evaluator knows if the AI decided to follow up or move on
        eval_messages = list(messages)
        eval_messages.append({"role": "assistant", "content": reply_text})

        asyncio.create_task(
            interview_service.evaluate_plan_async(
                eval_messages, resume_text, plan_data, scenario, language, settings.API_KEY, session_key, difficulty
            )
        )

        # Ensure current_plan is defined (using cache or fallback to request data)
        current_plan = interview_service.plan_cache.get(session_key, plan_data)

        # Return session key for polling
        return {
            "reply": reply_text,
            "transcript": user_transcript,
            "plan_update": current_plan, # Return old plan, client will poll for new one
            "session_key": session_key,
            "plan_updated": False,
            "interview_complete": current_plan.get("interview_complete", False),
            "final_result": current_plan.get("final_result")
        }

    except Exception as e:
        error_msg = str(e) or repr(e) or "Unknown Error"
        logger.error(f"Chat Error: {error_msg}", exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/api/plan-status/{session_key}")
async def get_plan_status(session_key: str):
    """Poll endpoint to get latest plan status"""
    if session_key in interview_service.plan_cache:
        return {"plan": interview_service.plan_cache[session_key]}
    return {"plan": None}

@router.post("/api/tts")
async def generate_tts(req: TTSRequest):
    if not settings.API_KEY: raise HTTPException(status_code=500, detail="API Key not configured")

    text = req.text
    voice = req.voice or "anna"

    # Preprocessing: Remove thinking tags if present
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    # Simple regex to remove markdown bold/italic
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)

    if not text:
        raise HTTPException(status_code=400, detail="No text to speak")

    # Add speaker tag [S1] as required by MOSS-TTSD model
    text_with_tag = f"[S1]{text}"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.BASE_URL}/audio/speech",
                headers={
                    "Authorization": f"Bearer {settings.API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "fnlp/MOSS-TTSD-v0.5",
                    "input": text_with_tag,
                    "voice": f"fnlp/MOSS-TTSD-v0.5:{voice}",
                    "response_format": "mp3",
                    "speed": 1.15
                }
            )

            if response.status_code != 200:
                logger.error(f"TTS Error {response.status_code}: {response.text}")
                raise HTTPException(status_code=response.status_code, detail=f"TTS Provider Error: {response.text}")

            # Read complete audio data and return as Response
            from fastapi.responses import Response
            audio_data = response.content
            return Response(content=audio_data, media_type="audio/mpeg")

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e) or repr(e) or "Unknown Error"
        logger.error(f"TTS Error: {error_msg}", exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)
