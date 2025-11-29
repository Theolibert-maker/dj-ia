"""Outil en ligne de commande pour identifier un set vidéo (.mp4/.mkv).

Ce script extrait l'audio avec ffmpeg, lance le pipeline existant et
imprime les titres/horodatages trouvés.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List

from dj_identifier.pipeline import bootstrap_store, run_pipeline
from dj_identifier.types import TrackMatch

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_FINGERPRINT_DB = REPO_ROOT / "fingerprints.json"
DEFAULT_BOOTSTRAP = REPO_ROOT / "examples" / "fingerprints.json"
SUPPORTED_VIDEO_EXTS = {".mp4", ".mkv"}


def load_bootstrap(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_store(db_path: Path = DEFAULT_FINGERPRINT_DB, bootstrap_path: Path = DEFAULT_BOOTSTRAP):
    """Charge ou initialise la base d'empreintes."""

    bootstrap_data = load_bootstrap(bootstrap_path)
    store = bootstrap_store(bootstrap_data, path=db_path)
    store.save()
    return store


def extract_audio(video_path: Path, workdir: Path) -> Path:
    """Utilise ffmpeg pour extraire l'audio mono du conteneur vidéo."""

    output = workdir / f"{video_path.stem}.wav"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "44100",
        "-ac",
        "1",
        str(output),
    ]
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output


def format_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def render_matches(matches: Iterable[TrackMatch]) -> str:
    lines: List[str] = []
    for match in matches:
        start = format_time(match.segment.start)
        end = format_time(match.segment.end)
        lines.append(
            f"[{start} - {end}] {match.artist} - {match.title} (confiance {match.confidence:.2f})"
        )
    if not lines:
        return "Aucun titre détecté."
    return "\n".join(lines)


def validate_video_path(path_str: str) -> Path:
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {path}")
    if path.suffix.lower() not in SUPPORTED_VIDEO_EXTS:
        raise ValueError("Merci de fournir un .mp4 ou .mkv")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Identifie les morceaux d'un set vidéo")
    parser.add_argument(
        "video",
        nargs="?",
        help="Chemin vers un fichier .mp4 ou .mkv (sinon une invite demandera le chemin)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    video_input = args.video or input("Chemin du fichier .mp4/.mkv : ").strip()

    try:
        video_path = validate_video_path(video_input)
    except (FileNotFoundError, ValueError) as exc:
        print(exc)
        return 1

    store = ensure_store()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = extract_audio(video_path, Path(tmpdir))
            matches = run_pipeline(str(audio_path), store)
    except subprocess.CalledProcessError as exc:
        print("Extraction audio échouée (ffmpeg)")
        print(exc.stderr.decode("utf-8", errors="ignore"))
        return 1

    print(render_matches(matches))
    return 0


if __name__ == "__main__":
    sys.exit(main())
