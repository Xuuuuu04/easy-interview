from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from app.interview_templates import INTERVIEW_TEMPLATES, LANGUAGE_OPTIONS

router = APIRouter()

@router.get("/")
async def read_root():
    return RedirectResponse(url="/static/index.html")

@router.get("/api/scenarios")
async def get_scenarios():
    scenarios = []
    for key, template in INTERVIEW_TEMPLATES.items():
        scenarios.append({
            "id": key,
            "category": template.get("category", "other"),
            "name": template["name"],
            "name_en": template.get("name_en", ""),
            "description": template["description"],
            "role": template["role"],
            "focus_areas": template["focus_areas"]
        })
    return {"scenarios": scenarios}

@router.get("/api/languages")
async def get_languages():
    return {"languages": LANGUAGE_OPTIONS}
