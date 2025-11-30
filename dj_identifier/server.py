"""Simple HTTP API to upload a DJ set and return identified tracks."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, File, HTTPException, UploadFile

from .pipeline import bootstrap_store, run_pipeline
from .types import TrackMatch

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent

DEFAULT_FINGERPRINT_DB = REPO_ROOT / "fingerprints.json"
DEFAULT_BOOTSTRAP = REPO_ROOT / "examples" / "fingerprints.json"


app = FastAPI(
    title="DJ Identifier",
    description="Upload a DJ set file and receive timecoded track guesses.",
)


def load_bootstrap(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def create_store(
    db_path: Path = DEFAULT_FINGERPRINT_DB, bootstrap_path: Path = DEFAULT_BOOTSTRAP
):
    bootstrap_data = load_bootstrap(bootstrap_path)
    return bootstrap_store(bootstrap_data, path=db_path)


def serialize_match(match: TrackMatch) -> Dict[str, object]:
    return {
        "track_id": match.track_id,
        "title": match.title,
        "artist": match.artist,
        "start": match.segment.start,
        "end": match.segment.end,
        "confidence": match.confidence,
    }


_store = create_store()


@app.post("/identify")
async def identify(file: UploadFile = File(...)) -> Dict[str, List[Dict[str, object]]]:
    """Accept an uploaded audio file and return ordered track matches."""

    if not file.filename:
        raise HTTPException(status_code=400, detail="Fichier audio manquant")

    suffix = Path(file.filename).suffix or ".wav"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_path = Path(tmp.name)

        matches = run_pipeline(str(temp_path), _store)
        return {"matches": [serialize_match(match) for match in matches]}
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
