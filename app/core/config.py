import os
import sys
from dotenv import load_dotenv
from app.core.logger import logger

# Load .env
# We want to look in current_dir (app/core), parent (app), and parent's parent (root)
current_file = os.path.abspath(__file__)
core_dir = os.path.dirname(current_file)
app_dir = os.path.dirname(core_dir)
root_dir = os.path.dirname(app_dir)

_env_paths = [
    os.path.join(app_dir, '.env'),
    os.path.join(root_dir, '.env'),
    '.env',
]
loaded = False
for path in _env_paths:
    if os.path.exists(path):
        load_dotenv(path, override=True)
        logger.info(f"✅ Loaded .env from: {path}")
        loaded = True
        break

if not loaded:
    logger.warning("⚠️ WARNING: No .env file found in any location!")

class Settings:
    API_KEY = os.getenv("SILICONFLOW_API_KEY")
    BASE_URL = "https://api.siliconflow.cn/v1"

    # --- Models Configuration ---
    MODEL_SENSE = "Qwen/Qwen3-Omni-30B-A3B-Instruct"
    MODEL_VISION = "Qwen/Qwen3-VL-30B-A3B-Instruct"

    # Fallback Chain Configuration
    MODEL_CHAIN = [
        {
            "model": "zai-org/GLM-4.6",
            "extra_body": {},  # Disable thinking
            "name": "GLM-4.6"
        },
        {
            "model": "Qwen/Qwen3-Next-80B-A3B-Instruct",
            "extra_body": {},
            "name": "Qwen3-Next-80B"
        }
    ]

    MODEL_THINK = MODEL_CHAIN[0]["model"]
    MODEL_TOOL = MODEL_CHAIN[0]["model"]
    
settings = Settings()

if not settings.API_KEY:
    logger.error("未找到 API_KEY!")
