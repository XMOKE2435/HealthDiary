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

LLM / ASR configuration
  - Reasoning/chat (diary, recommendations, summaries) can run on your Pi local model:
    - LOCAL_LLM_ENDPOINT=http://<pi-ip>:8080/v1/chat/completions
    - LOCAL_LLM_MODEL=qwen2.5-1.5b-instruct-q4_k_m.gguf (or your served model id)
    - LOCAL_LLM_API_KEY= (optional; leave empty if your local server has no auth)
  - ASR stays on Qwen/DashScope:
    - QWEN_ENDPOINT=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
    - QWEN_API_KEY=your_dashscope_token
  - Backward compatibility: if LOCAL_LLM_* is not set, reasoning falls back to QWEN_ENDPOINT.
  - Without any endpoint vars, the server returns safe heuristics for demo.

