from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .db.session import engine, Base
from .routers import diary, recommendations, doctor_pack, visit, shares, demo, checks, diary_chat, language_mode


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
    app.include_router(demo.router)

    # Serve static assets (e.g., generated doctor-pack PDFs)
    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir), html=False), name="static")

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    return app


app = create_app()

# Create DB tables on import (demo simplicity)
Base.metadata.create_all(bind=engine)


