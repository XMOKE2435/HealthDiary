Safety, Privacy, and LLM Guardrails
1) Non-negotiables

No diagnosis, dosing, or treatment instructions. Ever.

Red-flag checks are deterministic and override any conversational flow.

Every generated sentence must have provenance (entry IDs, transcript spans, or explicit derived features). Block otherwise.

Consent required for recording; short default retention; one-tap delete/export; on-device options whenever possible.

2) LLM usage patterns (allowed)

NLU / Slot-Filling (Diary)
Input: short text/voice transcript.
Output: JSON (OLD CARTS fields), keep patient wording in symptom_raw.
Post-process: validate types/ranges; never invent values.

Clarifier Selection (≤2)
Input: current fields + symptom pathway.
Output: IDs from a whitelist (e.g., clarifier.meal_relation, clarifier.fever).
Disallowed: free-form medical advice.

Extract-then-Rewrite Summaries
Sources: diary entries or transcript spans.
Output: CEFR B1/B2 EN/中文; glossary-locked terms; sentence-level provenance.
Block: any sentence without a source pointer.

Recommendations (non-medical)
Input: derived features only (trend slope, frequency, timing, trigger ratios) + optional entry refs.
Output: actions like “continue monitoring”, “log specific triggers”, “prepare a Doctor Pack”, “consider booking a visit”.
Disallowed: diagnosis, dosing, treatment.

Bilingual consistency
Use a locked glossary for critical terms (med names, symptoms) to avoid ambiguity.

3) What’s disallowed

Symptom-to-disease mapping, triage scoring, or clinical probabilities.

Dosing schedules or med switches.

Overriding red-flag outcomes.

Writing summaries from memory without sources.

4) Red-flag policy (examples; configure in policies/red_flags_rules.yml)

Severe chest pain at rest; chest pain + fainting; sudden one-sided weakness; heavy uncontrolled bleeding; fever >39.5°C with persistent severe pain; etc.
Action: stop flow → show urgent-care guidance; do not proceed to clarifiers or suggestions.

5) Refusal templates (examples; policies/refusal_templates.yml)

“I can’t provide a diagnosis or medication advice. If your symptoms are worrying or getting worse, consider seeking medical care. If you think this is an emergency, call your local emergency number.”

6) Privacy & PDPA

Purpose & consent: clear notices for audio, cloud processing, data sharing.

Minimization: store only what’s needed; short default retention; rotate presigned links.

User rights: export (PDF/FHIR/JSON) and delete; caregiver access is opt-in and revocable.

Security: encryption at rest/in transit; audit logs for access/shares.

7) Evaluation gates (release checklist)

Safety: ≥95% sensitivity on synthetic red-flags; 0 unsupported lines in summaries.

Comprehension: readability at B1/B2; bilingual checks pass glossary lock.

Latency: p95 diary save <3–5s; visit summary <30–60s for short recordings.

Provenance QA: random 10% of summaries sampled per build; failing sentence blocks release.

8) Logging & audit

Store only hashed IDs in logs; redact PII.

Log: rule triggers, refusals, provenance failures, share-link creation/access.

Provide a privacy log to users on request.