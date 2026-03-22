from pathlib import Path

# Load .env so QWEN_ENDPOINT and QWEN_API_KEY work on Pi (and elsewhere)
try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parent.parent.parent
    load_dotenv(Path.cwd() / ".env")
    load_dotenv(_root / ".env")
    load_dotenv(_root / "backend" / ".env")
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .db.session import engine, Base
from .routers import diary, recommendations, doctor_pack, visit, shares, demo, checks, diary_chat, language_mode, meal


def create_app() -> FastAPI:
    app = FastAPI(title="HealthDiary MVP", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(diary.router)
    app.include_router(recommendations.router)
    app.include_router(doctor_pack.router)
    app.include_router(visit.router)
    app.include_router(shares.router)
    app.include_router(checks.router)
    app.include_router(diary_chat.router)
    app.include_router(language_mode.router)
    app.include_router(meal.router)
    app.include_router(demo.router)

    # Serve static assets (e.g., generated doctor-pack PDFs)
    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir), html=False), name="static")

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/env-check")
    def env_check():
        """Check if LLM env vars are loaded (no secrets)."""
        import os
        ep = (os.getenv("QWEN_ENDPOINT") or "").strip()
        key_set = bool((os.getenv("QWEN_API_KEY") or "").strip())
        return {"qwen_endpoint_configured": bool(ep), "qwen_api_key_set": key_set, "llm_ok": bool(ep) and key_set}

    return app


app = create_app()

# Create DB tables on import (demo simplicity)
Base.metadata.create_all(bind=engine)


