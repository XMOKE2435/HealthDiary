Architecture & Contracts
1) System overview

App (Flutter): capture (text/voice), confirm, trends, Doctor Pack request, visit record/summary, notifications.

Backend (FastAPI): APIs, DB, object storage, rules engine, analytics, LLM services (NLU, clarifier select, extract-then-rewrite, recs), PDF/FHIR, provenance layer.

Storage: Postgres (encrypted), S3/MinIO for audio/PDF (presigned URLs).

LLM/ASR: abstracted behind service layer (can swap providers).

Future ESP32: publishes audio via MQTT → gateway → /visit/transcribe; otherwise same contracts.

2) Data model (tables)

users(user_id, locale, consent_flags_json, retention_days)

symptom_entries(id, user_id, ts, symptom_raw, input_mode, fields_json, provenance_json, created_at)

features(id, user_id, label, window_days, features_json, computed_at) ← trend, frequency, trigger ratios

summaries(id, user_id, type['doctor_pack'|'visit'], body_md, lang, provenance_json, storage_uri, created_at)

shares(id, user_id, target_id, token, expires_at) ← PDF share links

3) API contracts (v1)

POST /diary (client → server)

{
  "id": "optional-uuid",
  "user_id": "uuid",
  "ts": "2025-10-28T10:00:00Z",
  "symptom_raw": "stomachache after lunch",
  "input_mode": "voice|text",
  "fields": {
    "symptom_label": "abdominal pain",
    "onset": "2025-10-20",
    "location": "epigastric",
    "duration": "30m",
    "character": "cramping",
    "aggravating": ["spicy"],
    "relieving": ["antacid"],
    "timing": "post-meal",
    "severity": 6,
    "associated": ["nausea"],
    "triggers": ["spicy"]
  },
  "provenance": { "nlu": true, "user_confirmed": true }
}


200 → { "id": "uuid", "ok": true }

GET /recommendations?user_id=...&window_days=14&label=abdominal%20pain
200 →

{
  "type": "non_medical",
  "suggestions": [
    {
      "text": "You often log pain after dinner; try noting what you ate.",
      "evidence": ["entry_id:abc123", "feature:post_meal_ratio"]
    }
  ]
}


Must include at least one evidence pointer per suggestion.

POST /doctor-pack

{ "user_id": "uuid", "window_days": 30, "format": "pdf|fhir" }


200 →

{
  "pdf_uri": "s3://.../pack_123.pdf",
  "fhir": { "...": "QuestionnaireResponse (optional)" },
  "provenance": ["entry_id:...", "entry_id:..."]
}


POST /visit/transcribe

{ "user_id":"uuid", "audio_uri":"s3://bucket/visit123.wav", "lang":"en|zh" }


200 → { "transcript":"...", "spans":[{"speaker":"doctor","start":1.2,"end":3.4,"text":"..."}] }

POST /visit/summary

{ "user_id":"uuid", "transcript":"...", "lang":"en|zh" }


200 →

{
  "summary_md":"- Tests: ...\n- Med changes: ...\n- Return precautions: ...",
  "provenance":[{"text":"Start medicine once daily","source_span_id":"s42"}]
}


Reject any line with no source_span_id.

GET /shares/:token → serves PDF with expiry.

4) Services (backend)

rules.py — deterministic red flags; unit-tested.

analytics.py — rolling features (severity slope, episode frequency, trigger ratios, time-of-day/meal relation, response to self-care).

llm.py —

nlu_slot_fill(text) → JSON;

clarifier_select(fields, pathway) → ≤2 from whitelist;

summarize_doctor_pack(entries) → bullets with provenance;

summarize_visit(transcript_spans) → EN/中文 B1/B2 with provenance;

recommend_from_features(features) → non-medical suggestions with evidence.

asr.py — on-device/cloud integrators, diarization labels.

pdf.py — 1-page Doctor Pack, sparkline, bullets, footer.

fhir.py — QuestionnaireResponse builder.

provenance.py — sentence-to-source mapping enforcement.

storage.py — S3/MinIO presigned URLs.

5) Workflow diagrams (textual)

Diary save

App → /diary → DB.insert → rules(red-flags?) → analytics.recompute(7/30d)
→ cache recommendations → return OK


Doctor Pack

App → /doctor-pack(window) → fetch entries → summarize (provenance gate) → PDF/FHIR
→ store → presign → return links


Visit summary

App → /visit/transcribe → transcript, spans
→ /visit/summary → extract-then-rewrite (provenance gate)
→ save → return summary

6) Environments

Dev: Docker compose (Postgres, MinIO), backend hot-reload.

Staging/Prod: small VM or K8s; managed Postgres; object storage; HTTPS.

7) Telemetry & tests

Metrics: p95 latency per endpoint; token/ASR cost; red-flag trigger counts; diary completion time; prompt response rate.

Tests: rules, analytics, provenance gate (no unsupported lines), contracts (golden JSON).