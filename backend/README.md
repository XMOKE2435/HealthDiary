HealthDiary MVP Backend (Demo)

Quick start

1) Create virtual env and install deps
  - python -m venv .venv
  - . .venv/Scripts/activate  (PowerShell: .venv\\Scripts\\Activate.ps1)
  - pip install -r backend/requirements.txt

2) Run the server
  - uvicorn backend.app.main:app --reload --port 8000

3) Open the demo UI
  - http://localhost:8000/demo

Endpoints (demo stubs)
  - POST /diary
  - GET /recommendations
  - POST /doctor-pack
  - GET /shares/:token
  - POST /visit/transcribe
  - POST /visit/summary
  - POST /checks/meal
  - POST /checks/sleep
  - POST /checks/medication

Contracts per docs/docs/ARCHITECTURE.md (mock analytics/ASR/LLM for demo purposes).

LLM (optional)
  - Set env vars if you have a hosted Qwen endpoint:
    - QWEN_ENDPOINT=https://your-qwen-endpoint
    - QWEN_API_KEY=your_token
  - Without these, the server returns safe heuristics for demo.

