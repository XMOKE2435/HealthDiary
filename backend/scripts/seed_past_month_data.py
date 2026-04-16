import argparse
import json
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.models import MealEntry, SymptomEntry
from backend.app.db.session import Base, SessionLocal, engine


@dataclass(frozen=True)
class SymptomTemplate:
    label: str
    location: str
    character: str
    aggravating: list[str]
    relieving: list[str]
    associated: list[str]
    triggers: list[str]
    text_examples: list[str]


ABDOMINAL_SYMPTOM = SymptomTemplate(
    label="abdominal pain",
    location="lower abdomen",
    character="cramping",
    aggravating=["after spicy food", "stress", "late meals"],
    relieving=["warm compress", "rest", "hydration"],
    associated=["bloating", "mild nausea"],
    triggers=["spicy dinner", "irregular meals"],
    text_examples=[
        "Felt cramping pain in my lower abdomen after dinner.",
        "Mild abdominal pain this afternoon with bloating.",
        "Stomach discomfort came in waves after a spicy meal.",
    ],
)

OTHER_SYMPTOMS = [
    SymptomTemplate(
        label="headache",
        location="temples",
        character="throbbing",
        aggravating=["screen time", "bright light"],
        relieving=["rest in dark room", "hydration"],
        associated=["fatigue"],
        triggers=["poor sleep"],
        text_examples=[
            "Had a throbbing headache around my temples.",
            "Headache started after long laptop use.",
        ],
    ),
    SymptomTemplate(
        label="heartburn",
        location="upper abdomen",
        character="burning",
        aggravating=["lying down after meals", "acidic foods"],
        relieving=["upright posture", "light walk"],
        associated=["sour taste"],
        triggers=["late dinner"],
        text_examples=[
            "Burning feeling in upper abdomen after dinner.",
            "Mild heartburn at night after a heavy meal.",
        ],
    ),
    SymptomTemplate(
        label="back pain",
        location="lower back",
        character="aching",
        aggravating=["long sitting", "lifting items"],
        relieving=["light stretching", "rest"],
        associated=["stiffness"],
        triggers=["poor posture"],
        text_examples=[
            "My lower back felt sore after sitting too long.",
            "Back pain increased in the evening after work.",
        ],
    ),
    SymptomTemplate(
        label="dizziness",
        location="head",
        character="lightheaded",
        aggravating=["standing up quickly", "skipping meals"],
        relieving=["sitting down", "drinking water"],
        associated=["mild fatigue"],
        triggers=["dehydration"],
        text_examples=[
            "Felt dizzy when I stood up quickly this morning.",
            "Had brief lightheadedness before lunch.",
        ],
    ),
    SymptomTemplate(
        label="cough",
        location="throat",
        character="dry cough",
        aggravating=["cold air", "talking for long periods"],
        relieving=["warm water", "resting voice"],
        associated=["mild sore throat"],
        triggers=["air conditioning"],
        text_examples=[
            "Dry cough started in the afternoon.",
            "Cough got worse in air-conditioned rooms.",
        ],
    ),
]

MEAL_TEXTS = {
    "breakfast": [
        "Oatmeal with banana and almonds, plus green tea.",
        "Whole wheat toast, boiled egg, and apple slices.",
        "Greek yogurt with berries and granola.",
    ],
    "lunch": [
        "Brown rice, grilled chicken, and steamed broccoli.",
        "Turkey sandwich on whole grain bread and salad.",
        "Tofu stir-fry with mixed vegetables and quinoa.",
    ],
    "dinner": [
        "Salmon, roasted sweet potato, and spinach.",
        "Chicken noodle soup with side salad.",
        "Rice, stir-fried vegetables, and baked tofu.",
    ],
    "snack": [
        "Handful of nuts and a pear.",
        "Rice crackers with hummus.",
        "Small yogurt and banana.",
    ],
}


def _j(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False)


def create_symptom_entry(user_id: str, ts: datetime, rng: random.Random) -> SymptomEntry:
    template = ABDOMINAL_SYMPTOM if rng.random() < 0.38 else rng.choice(OTHER_SYMPTOMS)
    severity = rng.randint(2, 7 if template.label == "abdominal pain" else 6)
    duration_hours = rng.choice([1, 2, 3, 4, 6, 8])
    onset = (ts - timedelta(hours=duration_hours)).isoformat()

    fields = {
        "symptom_label": template.label,
        "onset": onset,
        "location": template.location,
        "duration": f"{duration_hours} hours",
        "character": template.character,
        "aggravating": rng.sample(template.aggravating, k=min(2, len(template.aggravating))),
        "relieving": rng.sample(template.relieving, k=min(2, len(template.relieving))),
        "timing": rng.choice(["morning", "afternoon", "evening", "night"]),
        "severity": severity,
        "associated": rng.sample(template.associated, k=min(2, len(template.associated))),
        "triggers": rng.sample(template.triggers, k=min(1, len(template.triggers))),
    }
    symptom_raw = rng.choice(template.text_examples)
    provenance = {
        "source": "presentation_seed_script",
        "confidence": round(rng.uniform(0.84, 0.99), 2),
    }
    return SymptomEntry(
        id=uuid4().hex,
        user_id=user_id,
        ts=ts,
        symptom_raw=symptom_raw,
        input_mode=rng.choice(["typed", "voice"]),
        fields_json=_j(fields),
        provenance_json=_j(provenance),
    )


def create_meal_entry(user_id: str, meal_type: str, ts: datetime, rng: random.Random) -> MealEntry:
    text_raw = rng.choice(MEAL_TEXTS[meal_type])
    items = [i.strip() for i in text_raw.replace(" and ", ", ").split(",") if i.strip()]
    provenance = {
        "source": "presentation_seed_script",
        "parsed": {"meal_type": meal_type, "items": items},
    }
    return MealEntry(
        id=uuid4().hex,
        user_id=user_id,
        ts=ts,
        meal_type=meal_type,
        items_json=_j(items),
        text_raw=text_raw,
        provenance_json=_j(provenance),
    )


def seed_data(user_id: str, days: int, seed: int, clear_existing: bool) -> tuple[int, int]:
    rng = random.Random(seed)
    Base.metadata.create_all(bind=engine)

    symptom_count = 0
    meal_count = 0
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

    with SessionLocal() as db:
        if clear_existing:
            db.query(SymptomEntry).filter(SymptomEntry.user_id == user_id).delete()
            db.query(MealEntry).filter(MealEntry.user_id == user_id).delete()
            db.commit()

        for day_offset in range(days):
            day = now - timedelta(days=day_offset)

            for meal_type, hour in [("breakfast", 8), ("lunch", 13), ("dinner", 19)]:
                ts = day.replace(hour=hour) + timedelta(minutes=rng.randint(-35, 35))
                db.add(create_meal_entry(user_id, meal_type, ts, rng))
                meal_count += 1

            if rng.random() < 0.65:
                snack_ts = day.replace(hour=16) + timedelta(minutes=rng.randint(-25, 25))
                db.add(create_meal_entry(user_id, "snack", snack_ts, rng))
                meal_count += 1

            symptom_events = 1 if rng.random() < 0.78 else 2
            for _ in range(symptom_events):
                hour = rng.choice([9, 11, 14, 17, 20, 22])
                ts = day.replace(hour=hour) + timedelta(minutes=rng.randint(-30, 30))
                db.add(create_symptom_entry(user_id, ts, rng))
                symptom_count += 1

        db.commit()

    return symptom_count, meal_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed realistic symptom + meal data for the past month.")
    parser.add_argument("--user-id", default="demo-user-1", help="Target user_id in database.")
    parser.add_argument("--days", type=int, default=30, help="How many days of history to generate.")
    parser.add_argument("--seed", type=int, default=20260416, help="Random seed for deterministic output.")
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Delete existing symptom/meal rows for this user before insert.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    symptoms, meals = seed_data(
        user_id=args.user_id,
        days=args.days,
        seed=args.seed,
        clear_existing=args.clear_existing,
    )
    print(
        f"Inserted {symptoms} symptom entries and {meals} meal entries "
        f"for user_id='{args.user_id}' over last {args.days} days."
    )
