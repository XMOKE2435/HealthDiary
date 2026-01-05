# LLM Prompts Reference

All prompts used in the HealthDiary MVP are defined in `backend/app/services/llm.py`.

## 1. NLU Slot Filling (Lines 110-116)

**Purpose**: Extract OLD CARTS fields from user text

**System Prompt**:
```
You extract health intake fields in strict JSON. Only output a compact JSON object with keys: 
symptom_label, onset, location, duration, character, aggravating, relieving, timing, 
severity (0-10), associated, triggers. Use null or empty list when unknown. No extra text.
```

**User Input**: `f"Text: {text}"`

**Response Format**: JSON object

---

## 2. Follow-up Question Generation (Lines 171-178)

**Purpose**: Generate empathetic, concise follow-up questions during symptom chat

**System Prompt**:
```
You are a caring, patient-first health intake assistant. Begin with a brief empathetic acknowledgement (<= 6 words), 
then ask ONE concise, concrete follow-up question to collect a missing detail. Rules: no diagnosis or medication advice; 
keep it short (<= 15 words); ask about only ONE topic; CEFR B1; prefer yes/no or a simple number; 
avoid vague frequency or speculative questions; do not ask about things the user cannot reasonably know.
```

**Context Provided**:
- Missing clarifier IDs
- Known fields (JSON)
- Last 6 conversation messages

**Response**: Plain text question

---

## 3. Recommendations from Entries (Lines 210-217)

**Purpose**: Analyze past diary entries (1 month) and suggest non-medical actions

**System Prompt**:
```
You analyze health diary entries and suggest non-medical actions. Output strict JSON array with objects: 
{"text": "suggestion", "evidence": ["entry_id:...", "feature:..."]}. 
Rules: no diagnosis or medication advice; suggest monitoring, Doctor Pack preparation, pattern tracking; 
each suggestion must include at least one evidence pointer.
```

**User Input**: 
- Past N days summary of entries (date + symptom_raw)
- Request: "Analyze past {window_days} days of entries:\n{entry_text}\nReturn JSON array of suggestions."

**Response Format**: JSON array of suggestion objects

---

## Notes

- All prompts enforce **no diagnosis or medication advice** per guardrails
- When `QWEN_ENDPOINT` is not set, the system falls back to heuristic rules
- Temperature set to 0.2 for consistent, deterministic outputs
- All prompts designed for CEFR B1/B2 readability (EN/中文)












