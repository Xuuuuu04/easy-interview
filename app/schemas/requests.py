from pydantic import BaseModel
from typing import Optional, List

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "anna"  # Random voice selected by frontend

class VideoAnalysisRequest(BaseModel):
    images: List[str]
    current_topic: Optional[str] = ""
    language: Optional[str] = "zh-CN"
