Product Requirements Document — “Health Diary & Visit Summary” (EN/中文)
1) Summary

A patient-first mobile/web app that turns brief daily check-ins (text or voice) into a structured symptom diary, detects simple trends, and offers non-medical next steps. When symptoms escalate, it generates a clinician-ready Doctor Pack (timeline + meds/allergies/conditions + concise summary; PDF + optional FHIR). With consent, it records clinic visits, applies ASR/diarization, and produces a plain-language After-Visit Summary (EN/中文) that reflects only what was said. Safety: rule-based red flags, no diagnosis/dosing, and provenance for every generated sentence.

2) Goals (what success looks like)

G1. Capture: ≥80% of diary entries include core OLD CARTS fields; median entry time ≤30s.

G2. Utility: Clinician rating of Doctor Pack ≥4/5 on completeness/clarity (mini pilot).

G3. Comprehension: ≥20-point improvement in patient recall of plan/return precautions after the visit summary.

G4. Safety: ≥95% red-flag sensitivity in synthetic test sets; 0 unsupported lines in summaries.

G5. Engagement (seniors): response rate to scheduled prompts (meal/med/daily) ≥40% within 2h; ≥70% voice confirmation success.

3) Users & value

Seniors / low-tech users: voice-first, large UI, reminders anchored to daily habits (meals/meds), weekly two-line digest.

Caregivers (opt-in): weekly digest + “request Doctor Pack” button improves handoffs.

Clinicians: one-page, structured context reduces history-taking time; FHIR export can prefill intake.

4) Scope (MVP)

Must-have

Structured Symptom Diary (text/voice) with ≤2 whitelisted clarifiers per pathway.

Trend view (7/30 days) + non-medical suggestions based on derived features (trend, frequency, timing, triggers).

Doctor Pack generation (PDF + optional FHIR QuestionnaireResponse), time-boxed share links.

Visit Recorder → ASR/diarization → After-Visit Summary (EN/中文), extract-then-rewrite with provenance.

Rule-based red flags (deterministic) and refusal patterns for diagnosis/dosing requests.

Consent, retention, on-device options; delete/export.

Nice-to-have (engagement boosters)

Scheduled Meal Check, Medicine Intake Check, Daily Symptom Check (customizable times, Quiet Hours).

Sleep/Night Comfort and Mood/Companionship micro-chat (safe templates).

WhatsApp/WeChat mini-check-ins; IVR fallback (phone call) for non-smartphone users.

Out of scope

Diagnosis, dosing, treatment instructions; differential diagnosis; triage scores.

5) Key user journeys

Quick diary entry (≤30s): user speaks/types → NLU slot-filling → ≤2 clarifiers → confirm → save → trend updates → (optional) suggestion with “why”.

Escalation: user chooses “Generate Doctor Pack” → selects window (7/30d) → server builds PDF/FHIR → time-boxed share link.

Visit recording: consent → record → ASR/diarization → summary preview → user confirms → save + share.

Engagement: mealtime/med/daily prompt → 1–2 taps or a 5-second voice note → done.

6) Metrics (for PM and evaluation)

Acquisition: onboarding completion, consent accept rates (audio, cloud).

Activation: first entry ≤24h, % entries with complete OLD CARTS.

Engagement: weekly active rate, check-in streaks, prompt response rate, clarifier acceptance.

Utility: clinician rating of Doctor Pack, time saved (self-report), fewer callback questions.

Safety: red-flag sensitivity; 0 unsupported lines (provenance gate).

Cost/latency: p95 for /diary, /summary, token/ASR costs per user.

7) Timeline (build order)

/diary + analytics + trends → 2. recommendations → 3. Doctor Pack (PDF/FHIR) →

visit recorder + summary → 5. notifications/schedules → 6. usability + polish.