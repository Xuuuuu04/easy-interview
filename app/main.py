from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from app.core.logger import logger
from app.api.routes import system, interview

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")

@app.get("/")
async def root():
    from fastapi.responses import FileResponse
    return FileResponse(os.path.join(static_dir, "index.html"))

app.include_router(system.router)
app.include_router(interview.router)

logger.info("Application initialized with modular structure.")

if __name__ == "__main__":
    import uvicorn
    # When running directly, we might need to adjust path or run as module
    # But usually 'python app/main.py' might have relative import issues if we use 'app.' in imports
    # If running from root as 'python -m app.main', it works.
    uvicorn.run(app, host="0.0.0.0", port=8000)
