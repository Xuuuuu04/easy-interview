import httpx
import json
from fastapi import HTTPException
from app.core.config import settings
from app.core.logger import logger

async def generate_thought_response(messages, tools=None, tool_choice="auto", model=None):
    """Call LLM with fallback chain logic"""
    
    # Logic copied from main.py, using settings
    last_exception = None

    # If model is explicitly provided (and not None), user might want to bypass chain?
    # Original logic: "So we ignore the `model` param unless we want to force something else, instead we iterate through MODEL_CHAIN."
    # But current code ignores `model` param passed to function and iterates chain.
    # We will keep that behavior but allow override if we really want to? 
    # Actually the original code just ignored `model` arg completely in the loop.
    
    chain = settings.MODEL_CHAIN
    
    for config in chain:
        current_model = config["model"]
        extra_body = config["extra_body"]
        logger.info(f"尝试模型: {config['name']} ({current_model})...")

        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "model": current_model,
                "messages": messages,
                "stream": False,
                "max_tokens": 4096,
                "temperature": 0.3,
            }
            
            if extra_body:
                payload.update(extra_body)
            
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = tool_choice

            try:
                response = await client.post(
                    f"{settings.BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )

                if response.status_code == 200:
                    data = response.json()
                    choice = data['choices'][0]
                    if choice['message'].get('tool_calls'):
                         return {"tool_calls": choice['message']['tool_calls']}
                    return choice['message']['content']
                
                logger.warning(f"Model {config['name']} Failed: {response.status_code} - {response.text}")
                last_exception = f"HTTP {response.status_code}: {response.text}"

            except Exception as e:
                logger.warning(f"Model {config['name']} Exception: {str(e)}")
                last_exception = str(e)
                continue 
    
    logger.critical("All models in chain failed.")
    raise HTTPException(status_code=500, detail=f"All AI models failed. Last error: {last_exception}")

async def call_vision_model(messages):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{settings.BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {settings.API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": settings.MODEL_VISION,
                    "messages": messages,
                    "max_tokens": 512,
                    "temperature": 0.1
                }
            )

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=f"Vision API Error: {response.text}")

            data = response.json()
            return data['choices'][0]['message']['content']

        except Exception as e:
            logger.error(f"Vision Analysis Error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

async def transcribe_audio(audio_b64, mime_type="audio/wav"):
    sense_messages = [
        {
            "role": "system",
            "content": "You are a professional transcriber. Transcribe the user's speech accurately. Output ONLY the transcription text."
        },
        {
            "role": "user",
            "content": [
                {"type": "audio_url", "audio_url": {"url": f"data:{mime_type};base64,{audio_b64}"}},
                {"type": "text", "text": "Please transcribe this audio."}
            ]
        }
    ]

    async with httpx.AsyncClient(timeout=90.0) as client:  # Increased from 30s to 90s
        response = await client.post(
            f"{settings.BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {settings.API_KEY}", "Content-Type": "application/json"},
            json={"model": settings.MODEL_SENSE, "messages": sense_messages, "stream": False}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"Sense Error: {response.text}")

        return response.json()['choices'][0]['message']['content']
