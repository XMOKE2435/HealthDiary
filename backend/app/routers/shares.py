from fastapi import APIRouter, HTTPException, Response
from pathlib import Path
from .doctor_pack import resolve_share


router = APIRouter(tags=["shares"])


@router.get("/shares/{token}")
def get_share(token: str):
    path: Path | None = resolve_share(token)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="invalid or expired token")
    data = path.read_bytes()
    return Response(content=data, media_type="application/pdf")


