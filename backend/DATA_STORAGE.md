# Data Storage Guide

## Database (SQLite)

**Location**: `backend/app/data/healthdiary.db`

**Persistence**: ✅ **YES** - Data persists across server restarts. The database file remains on disk unless manually deleted.

**Tables**:
- `symptom_entries`: All diary entries with timestamps, fields, and provenance

**Backup**: The `.db` file can be copied/backed up. It's a standard SQLite database.

**To view data manually**:
```bash
sqlite3 backend/app/data/healthdiary.db
.tables
SELECT * FROM symptom_entries LIMIT 10;
```

---

## Doctor Pack Files (Temporary)

**Location**: System temp directory (varies by OS)
- Windows: `C:\Users\<USER>\AppData\Local\Temp\healthdiary_pdf\`
- Linux/Mac: `/tmp/healthdiary_pdf/`

**Persistence**: ❌ **NO** - Files are stored in temp directory and may be cleared by:
- OS cleanup routines
- Server restart (if temp directory is cleared)
- Manual deletion

**Format**: Currently HTML files (`.html`) that open in browsers. Can be upgraded to real PDFs later.

**Share tokens**: Stored in-memory (`_SHARES` dict in `doctor_pack.py`), so they are **lost on server restart**.

---

## During Testing

**If you restart the demo app**:
- ✅ **Diary entries persist** (stored in SQLite)
- ❌ **Doctor Pack share links expire** (tokens in memory, files in temp)

**To start fresh**:
- Delete `backend/app/data/healthdiary.db` to clear all diary entries
- Doctor Pack files in temp will be regenerated as needed

**To keep data for production**:
- Move database to a persistent location (e.g., mounted volume)
- Use proper object storage (S3/MinIO) for Doctor Pack PDFs
- Implement proper share token storage (database or cache like Redis)












