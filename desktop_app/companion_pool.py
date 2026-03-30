"""Companion check-in question pool from bundled companion_questions.json."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import List, Optional


def bundled_pool_path() -> Path:
    return Path(__file__).resolve().parent / "companion_questions.json"


def _normalize_entries(raw_questions: object) -> List[str]:
    out: List[str] = []
    if not isinstance(raw_questions, list):
        return out
    for item in raw_questions:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            zh = (item.get("zh") or "").strip()
            en = (item.get("en") or "").strip()
            if zh and en:
                out.append(f"{zh}\n{en}")
            elif zh:
                out.append(zh)
            elif en:
                out.append(en)
    return out


def _fallback_strings() -> List[str]:
    return [
        "今天过得怎么样？有没有好好吃饭？\nHow has your day been—have you had something to eat?",
        "昨晚睡得还好吗？\nDid you sleep alright last night?",
        "今天有没有出门走走、晒晒太阳？\nDid you get a little walk or sunshine today?",
    ]


def load_question_pool() -> List[str]:
    p = bundled_pool_path()
    if p.is_file():
        try:
            with p.open(encoding="utf-8") as f:
                data = json.load(f)
            rows = _normalize_entries(data.get("questions", []))
            if rows:
                return rows
        except Exception:
            pass
    return _fallback_strings()


def pick_question(pool: List[str], avoid_last: Optional[str] = None) -> str:
    if not pool:
        return _fallback_strings()[0]
    candidates = [q for q in pool if q != avoid_last] or pool
    return random.choice(candidates)
