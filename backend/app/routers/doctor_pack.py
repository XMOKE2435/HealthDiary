from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from typing import Optional
from uuid import uuid4
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
from .diary import list_entries_for_user
from ..services.llm import QwenClient


router = APIRouter(tags=["doctor-pack"])

_SHARES: dict[str, dict] = {}
_STORAGE_DIR = Path(tempfile.gettempdir()) / "healthdiary_pdf"
_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


class DoctorPackRequest(BaseModel):
    user_id: str
    window_days: int = 30
    format: Optional[str] = "pdf"


@router.post("/doctor-pack")
def post_doctor_pack(req: DoctorPackRequest):
    all_entries = list_entries_for_user(req.user_id)
    if not all_entries:
        raise HTTPException(status_code=404, detail="no entries")

    # Filter entries by window_days
    cutoff_date = datetime.utcnow() - timedelta(days=req.window_days)
    entries = []
    for e in all_entries:
        try:
            # Parse ISO format timestamp
            entry_ts = datetime.fromisoformat(e.get("ts", "").replace("Z", "+00:00"))
            # Convert to UTC if timezone-aware, otherwise assume UTC
            if entry_ts.tzinfo:
                entry_ts = entry_ts.astimezone(datetime.utcnow().tzinfo).replace(tzinfo=None)
            if entry_ts >= cutoff_date:
                entries.append(e)
        except (ValueError, AttributeError, TypeError):
            # If date parsing fails, include the entry (better to show than hide)
            entries.append(e)
    
    if not entries:
        raise HTTPException(status_code=404, detail=f"no entries in the last {req.window_days} days")

    # Generate HTML "Doctor Pack" (demo format; can be upgraded to real PDF later)
    token = uuid4().hex
    pdf_name = f"pack_{token}.html"
    pdf_path = _STORAGE_DIR / pdf_name

    # LLM synthesis (best-effort, bilingual doctor pack)
    import asyncio
    llm = QwenClient()
    try:
        summary = asyncio.run(llm.summarize_doctor_pack(entries, req.window_days)) if llm.endpoint else {
            "english_summary": "",
            "chinese_summary": "",
            "symptom_groups": [],
            "suggestions": [],
            "structured_events": {},
        }
    except Exception as exc:
        import traceback
        print(f"Doctor pack LLM error: {exc}")
        print(traceback.format_exc())
        summary = {
            "english_summary": "",
            "chinese_summary": "",
            "symptom_groups": [],
            "suggestions": [],
            "structured_events": {},
        }

    english_summary = summary.get("english_summary", "") or ""
    chinese_summary = summary.get("chinese_summary", "") or ""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <title>My Health Summary - {req.user_id}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; line-height:1.6; }}
    h1 {{ color: #0066cc; }}
    h2 {{ color: #444; margin-top:24px; }}
    .symptom-group {{ margin: 16px 0; padding: 16px; background:#f5f5f5; border-left:4px solid #0066cc; border-radius:4px; }}
    .symptom-label {{ font-size:1.2em; font-weight:bold; color:#0066cc; margin-bottom:8px; }}
    .dates {{ color:#666; font-size:0.95em; margin:6px 0; }}
    .summary {{ margin:8px 0; color:#333; }}
    ul {{ margin-top:6px; }}
    .intro {{ background:#e8f4f8; padding:12px; border-radius:4px; margin-bottom:20px; }}
  </style>
</head>
<body>
  <h1>My Health Summary</h1>
  <div class="intro">
    <p><strong>This summary helps you answer your doctor's questions.</strong><br/>
       <span>本摘要帮助您在就诊时更好地向医生说明情况。</span></p>
    <p>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} | Period: Last {req.window_days} days</p>
  </div>

  <h2>Doctor-facing Summary (English)</h2>
  <p>{english_summary or "No structured summary is available yet."}</p>

  <h2>就诊概要（简体中文）</h2>
  <p>{chinese_summary or "当前暂时没有可用的结构化摘要。"}</p>

  <h2>Symptoms by Type</h2>
"""
    groups = summary.get("symptom_groups", [])
    # Fallback: if LLM returned no groups but we have entries, create basic groups
    if not groups and entries:
        # Group entries by symptom_label manually
        from collections import defaultdict
        grouped = defaultdict(lambda: {"dates": [], "entry_ids": []})
        for e in entries:
            fields = e.get("fields", {}) or {}
            label = (fields.get("symptom_label") or "symptom").lower()
            date_str = (e.get("ts", "") or "")[:10]
            if date_str:
                grouped[label]["dates"].append(date_str)
            grouped[label]["entry_ids"].append(e.get("id", ""))
        
        for label, data in grouped.items():
            groups.append({
                "symptom_label": label,
                "dates": sorted(set(data["dates"])),
                "summary": f"Reported {len(data['entry_ids'])} time(s) in the last {req.window_days} days."
            })
    
    if not groups:
        html_content += "  <p>No symptoms recorded in this period.</p>\n  <p>本时间段内没有记录到症状。</p>\n"
    else:
        for g in groups:
            label = g.get("symptom_label", "symptom").title()
            dates = g.get("dates", [])
            if not isinstance(dates, list):
                dates = []
            dates = [d for d in dates if d and isinstance(d, str) and len(d) >= 8]
            summary_text = g.get("summary", "")
            dates_str = ', '.join(sorted(set(dates))[:10])
            if len(dates) > 10:
                dates_str += f", ... ({len(dates)} total dates)"
            html_content += f"""  <div class="symptom-group">
    <div class="symptom-label">{label}</div>
    <div class="dates"><strong>Occurred on:</strong> {dates_str if dates_str else 'No dates available'}</div>
    <div class="summary">{summary_text}</div>
  </div>
"""

    html_content += "  <h2>Suggestions (non-medical)</h2>\n  <ul>\n"
    for s in summary.get("suggestions", []):
        html_content += f"    <li>{s.get('text','')}</li>\n"
    if not summary.get("suggestions"):
        html_content += "    <li>Continue monitoring and keep brief notes on triggers/relief.</li>\n"
    html_content += "  </ul>\n"

    html_content += """</body>
</html>"""
    pdf_path.write_text(html_content, encoding="utf-8")

    share_token = uuid4().hex
    _SHARES[share_token] = {
        "file": pdf_name,
        "expires_at": datetime.utcnow() + timedelta(hours=12)
    }

    return {
        "pdf_uri": f"/doctor-pack/pdf/{pdf_name}",
        "fhir": None,
        "provenance": [f"entry_id:{e.get('id')}" for e in entries[-30:]],
        "share_token": share_token,
        # Expose bilingual summaries so UI can render/toggle as needed
        "english_summary": english_summary,
        "chinese_summary": chinese_summary,
    }


def resolve_share(token: str) -> Optional[Path]:
    meta = _SHARES.get(token)
    if not meta:
        return None
    if meta["expires_at"] < datetime.utcnow():
        return None
    return _STORAGE_DIR / meta["file"]


@router.get("/doctor-pack/pdf/{filename}")
def get_doctor_pack_pdf(filename: str):
    path = _STORAGE_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="file not found")
    data = path.read_bytes()
    # Serve as HTML for browser display (demo format)
    media_type = "text/html" if filename.endswith(".html") else "application/pdf"
    return Response(content=data, media_type=media_type)


