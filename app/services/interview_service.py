import json
import httpx
from app.core.config import settings
from app.core.logger import logger

# Session storage for updated plans
plan_cache = {}

async def evaluate_plan_async(history_list, resume_text, plan_data, scenario, language, api_key, session_key, difficulty=5):
    """Evaluate conversation and update interview plan using function calling"""
    try:
        # Difficulty context
        DIFFICULTY_DESC = {
            1: "Extremely Lenient: Accept almost any answer, give high scores easily.",
            5: "Standard: Expect clear, correct answers. Deduct points for vagueness.",
            10: "Hardcore/Hell: Demanding perfection. If the answer is not deep/specific enough, DO NOT mark as complete. Instead, use modify_pending_item to ask a harder follow-up."
        }
        diff_instruction = DIFFICULTY_DESC.get(10 if difficulty >= 8 else (1 if difficulty <= 3 else 5))

        # Define Function Calling Tools - Three tools for complete plan management
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "mark_item_complete",
                    "description": "Mark an interview item as COMPLETED after the candidate answered. Rate their answer quality.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "ID of the completed item (e.g. '1', '2')"},
                            "score": {"type": "integer", "description": "Score 0-100. If answer is acceptable/good, score MUST be 60+. Only score <60 for refusal/complete failure."},
                            "evaluation": {"type": "string", "description": "Evaluation of the CANDIDATE'S ANSWER - what they did well or poorly (for candidate to review)"},
                            "suggestion": {"type": "string", "description": "Improvement suggestion FOR THE CANDIDATE - how they could have answered better (for candidate's learning)"}
                        },
                        "required": ["item_id", "score", "evaluation", "suggestion"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "modify_pending_item",
                    "description": "Modify an UNCOMPLETED item to optimize the question based on conversation context.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "ID of the pending item to modify"},
                            "new_content": {"type": "string", "description": "Updated question text optimized for this candidate"}
                        },
                        "required": ["item_id", "new_content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "insert_followup_question",
                    "description": "Insert a NEW follow-up question immediately after a pending item. Use this when you want to dig deeper or challenge the candidate.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "after_item_id": {"type": "string", "description": "ID of the item to insert AFTER (e.g. '2')"},
                            "new_id": {"type": "string", "description": "New ID for the inserted item (e.g. '2.1')"},
                            "content": {"type": "string", "description": "The follow-up question text"}
                        },
                        "required": ["after_item_id", "new_id", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "complete_interview",
                    "description": "Call this ONLY when ALL items are marked as done to end the interview.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "final_score": {"type": "integer", "description": "Overall interview score 0-100"},
                            "summary": {"type": "string", "description": "Final evaluation summary of the candidate"}
                        },
                        "required": ["final_score", "summary"]
                    }
                }
            }
        ]
        
        # Build Plan Context with status tracking
        plan_desc = "CURRENT INTERVIEW PLAN:\n"
        pending_items = []
        completed_items = []
        total_items = 0
        
        for sec in plan_data.get("sections", []):
            plan_desc += f"\n## {sec['title']}:\n"
            for item in sec['items']:
                total_items += 1
                if item.get("status") == "done":
                    plan_desc += f"  ✅ [DONE] (ID: {item['id']}) {item['content']} - Score: {item.get('score', 'N/A')}\n"
                    completed_items.append(item['id'])
                else:
                    plan_desc += f"  ⬜ [PENDING] (ID: {item['id']}) {item['content']}\n"
                    pending_items.append(f"ID {item['id']}: {item['content'][:40]}")
        
        all_done = len(pending_items) == 0
        
        # Strict system prompt to prevent chatting
        system_prompt = f"""You are a background process that updates an interview checklist.
        
DO NOT CONVERSATE WITH THE USER.
DO NOT OUTPUT ANY TEXT.
ONLY CALL TOOLS.

CURRENT DIFFICULTY LEVEL: {difficulty}/10
EVALUATION STANDARD: {diff_instruction}

INTERVIEW PLAN:
{plan_desc}

PENDING ITEMS: {', '.join(pending_items) if pending_items else 'ALL DONE!'}

INSTRUCTIONS:
    1. Analyze the *latest* user answer.
    2. If it answers a PENDING item:
       - Check if the answer quality meets the DIFFICULTY STANDARD.
       - If YES: call `mark_item_complete` (score 60-100).
       - If NO (and difficulty is high): call `insert_followup_question`.
       - If NO (and answer is total nonsense): call `mark_item_complete` (score 0-59).
    3. If you want to change the next question, call `modify_pending_item`.
    4. If everything is done, call `complete_interview`.
    
    Force yourself to call at least one tool if there is ANY progress.
    """
        
        # Construct messages strictly for tool calling
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history_list[-4:])  # Keep context short
        messages.append({"role": "user", "content": "Analyze the above conversation and update the plan immediately. Call tools now."})

        # Use the same GLM-4.6 model for plan evaluation (with Function Calling)
        eval_model = settings.MODEL_TOOL  # Reuse GLM-4.6

        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"📡 发送计划评估请求至 {eval_model}...")

            response = await client.post(
                f"{settings.BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": eval_model,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "temperature": 0.01  # Low temperature for deterministic tool calling
                }
            )
            
            if response.status_code != 200:
                logger.error(f"❌ 计划 API 错误 ({response.status_code}): {response.text}")
                return {"updated": False, "interview_complete": False}
            
            data = response.json()
            logger.debug(f"📥 计划 API 响应: {json.dumps(data, indent=2, ensure_ascii=False)[:1000]}")
            
            message = data['choices'][0]['message']
            
            if not message.get('tool_calls'):
                logger.info(f"ℹ️ 无工具调用。内容: {message.get('content', 'empty')[:100]}")
                return {"updated": False, "interview_complete": False}
            
            # Process tool calls
            updated_plan = plan_data.copy()
            interview_complete = False
            final_result = None
            updates_made = 0
            
            logger.info(f"🛠️ 处理 {len(message['tool_calls'])} 个工具调用")
            
            for tool_call in message['tool_calls']:
                fn_name = tool_call['function']['name']
                try:
                    fn_args = json.loads(tool_call['function']['arguments'])
                except:
                    logger.error(f"❌ Failed to parse args: {tool_call['function']['arguments']}")
                    continue
                    
                logger.info(f"🔧 工具: {fn_name} | 参数: {fn_args}")
                
                if fn_name == 'mark_item_complete':
                    item_id = str(fn_args.get('item_id'))
                    raw_score = fn_args.get('score', 0)
                    evaluation = fn_args.get('evaluation', '')
                    suggestion = fn_args.get('suggestion', '')
                    
                    # Logic Check: Prevent 0 score for obviously good evaluation or default
                    # If evaluation doesn't explicitly mention "refusal" or "failure", bump score to passing
                    score = raw_score
                    if score < 60 and "good" in evaluation.lower() or "correct" in evaluation.lower():
                         score = 70
                    if score == 0: # Fallback if model forgot to assign score
                         score = 60

                    for sec in updated_plan.get('sections', []):
                        for item in sec['items']:
                            if str(item['id']) == item_id:
                                item['status'] = 'done'
                                item['score'] = score
                                item['evaluation'] = evaluation
                                item['suggestion'] = suggestion
                                item['locked'] = True  # Lock completed items
                                updates_made += 1
                                logger.info(f"✅ Marked item {item_id} complete: Score {score}")
                                
                elif fn_name == 'modify_pending_item':
                    item_id = str(fn_args.get('item_id'))
                    new_content = fn_args.get('new_content', '')
                    
                    for sec in updated_plan.get('sections', []):
                        for item in sec['items']:
                            if str(item['id']) == item_id and item.get('status') != 'done':
                                item['content'] = new_content
                                updates_made += 1
                                logger.info(f"📝 Modified pending item {item_id}")
                                
                elif fn_name == 'insert_followup_question':
                    after_id = str(fn_args.get('after_item_id'))
                    new_id = str(fn_args.get('new_id'))
                    content = fn_args.get('content', '')
                    
                    inserted = False
                    for sec in updated_plan.get('sections', []):
                        if inserted: break
                        items = sec['items']
                        for i, item in enumerate(items):
                            if str(item['id']) == after_id:
                                items.insert(i + 1, {
                                    "id": new_id,
                                    "content": content,
                                    "status": "pending",
                                    "is_followup": True
                                })
                                inserted = True
                                updates_made += 1
                                logger.info(f"➕ Inserted follow-up {new_id} after {after_id}")
                                break
                                
                elif fn_name == 'complete_interview':
                    interview_complete = True
                    final_result = {
                        "final_score": fn_args.get('final_score', 0),
                        "summary": fn_args.get('summary', '')
                    }
                    logger.info(f"🏁 Interview completed! Final score: {final_result['final_score']}")
            
            # Cache updated plan
            if updates_made > 0 or interview_complete:
                updated_plan['interview_complete'] = interview_complete
                if final_result:
                    updated_plan['final_result'] = final_result
                plan_cache[session_key] = updated_plan
                logger.info(f"💾 Cached plan for {session_key[:8]} ({updates_made} updates)")
            
            return {
                "updated": updates_made > 0,
                "interview_complete": interview_complete,
                "final_result": final_result
            }
            
    except Exception as e:
        logger.error(f"❌ Plan eval error: {str(e)}", exc_info=True)
        return {"updated": False, "interview_complete": False}
