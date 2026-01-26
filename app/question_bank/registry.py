from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .service import QuestionPack, load_pack_from_file


_PACK_DIR = Path(__file__).resolve().parent / "packs"


def list_available_packs() -> list[str]:
    if not _PACK_DIR.exists():
        return []
    packs: list[str] = []
    for p in _PACK_DIR.glob("*.json"):
        packs.append(p.stem)
    packs.sort()
    return packs


def _pack_path(pack_id: str) -> Path:
    return _PACK_DIR / f"{pack_id}.json"


@lru_cache(maxsize=64)
def get_question_pack(pack_id: str) -> QuestionPack:
    path = _pack_path(pack_id)
    if not path.exists():
        raise FileNotFoundError(f"Question pack not found: {pack_id}")
    return load_pack_from_file(pack_id, path)

