import logging
import sys
import os
from datetime import datetime

logger = logging.getLogger("server")

def setup_logging():
    # Configure logging
    os.makedirs("logs", exist_ok=True)
    log_filename = f"logs/server_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logger.setLevel(logging.DEBUG)

    # File Handler
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d - %(message)s'))
    logger.addHandler(file_handler)

    # Stream Handler (Console)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s'))
    logger.addHandler(stream_handler)

    logger.info(f"日志已初始化。写入文件: {log_filename}")

# Initialize on import or explicit call?
# Currently in main.py it runs at top level. 
# We can run it on import safe-ishly or allow main to call it.
# Let's run it if not already configured?
if not logger.handlers:
    setup_logging()
