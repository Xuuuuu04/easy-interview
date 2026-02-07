import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class QuestionPack:
    pack_id: str
    version: str
    questions: list[dict[str, Any]]


def _compute_version(file_bytes: bytes) -> str:
    return hashlib.sha1(file_bytes).hexdigest()[:12]


def load_pack_from_file(pack_id: str, file_path: Path) -> QuestionPack:
    raw = file_path.read_bytes()
    version = _compute_version(raw)
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid JSON in question pack: {file_path}") from e

    if not isinstance(data, list):
        raise ValueError(f"Question pack must be a JSON array: {file_path}")

    questions: list[dict[str, Any]] = []
    for i, q in enumerate(data):
        if not isinstance(q, dict):
            raise ValueError(f"Question #{i} must be an object in {file_path}")
        qid = q.get("id")
        question = q.get("question")
        if not qid or not isinstance(qid, str):
            raise ValueError(f"Question #{i} missing string field 'id' in {file_path}")
        if not question or not isinstance(question, str):
            raise ValueError(f"Question #{i} missing string field 'question' in {file_path}")
        questions.append(q)

    return QuestionPack(pack_id=pack_id, version=version, questions=questions)


def render_pack_for_prompt(
    pack: QuestionPack,
    *,
    max_questions: int | None = 200,
    fields: tuple[str, ...] = ("id", "question", "tags", "difficulty", "followups", "variants"),
) -> str:
    if max_questions is None:
        subset = pack.questions
    else:
        subset = pack.questions[: max(0, max_questions)]

    compact = []
    for q in subset:
        compact.append({k: q.get(k) for k in fields if k in q})

    payload = {
        "pack_id": pack.pack_id,
        "version": pack.version,
        "questions": compact,
    }
    return json.dumps(payload, ensure_ascii=False)

