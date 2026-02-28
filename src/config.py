import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
RUBRIC_PATH = BASE_DIR / "rubric.json"

LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")
VISION_MODEL = os.getenv("VISION_MODEL", "gemini-2.5-flash")


def load_rubric() -> dict:
    with open(RUBRIC_PATH) as f:
        return json.load(f)


def get_dimensions_for_artifact(artifact: str) -> list[dict]:
    """Return rubric dimensions matching a target_artifact type."""
    rubric = load_rubric()
    return [
        d for d in rubric["dimensions"] if d["target_artifact"] == artifact
    ]


def get_synthesis_rules() -> dict:
    rubric = load_rubric()
    return rubric["synthesis_rules"]
