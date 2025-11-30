"""Outil en ligne de commande pour identifier un set vidéo (.mp4/.mkv).

Ce script extrait l'audio avec ffmpeg, lance le pipeline existant et
imprime les titres/horodatages trouvés.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List

FFMPEG_ENV_VAR = "FFMPEG_PATH"

REPO_ROOT = Path(__file__).resolve().parent
REQUIREMENTS_PATH = REPO_ROOT / "requirements.txt"


def _ensure_dependencies() -> None:
    """Fail fast with a helpful message if runtime deps are missing."""

    pip_cmd = " ".join(
        [
            shlex.quote(sys.executable),
            "-m",
            "pip",
            "install",
            "-r",
            shlex.quote(str(REQUIREMENTS_PATH)),
        ]
    )
    pip_cmd = f"{sys.executable} -m pip install -r {REQUIREMENTS_PATH}"
    required = [
        "numpy",
        "librosa",
        "soundfile",
    ]
    missing: list[str] = []
    for module in required:
        if importlib.util.find_spec(module) is None:
            missing.append(f"- {module}")

    if missing:
        message = "\n".join(
            [
                "Dépendances manquantes pour lancer l'identification :",
                *missing,
                "\nInstallez-les dans le même environnement Python :",
                f"  {pip_cmd}",
            ]
        )
        raise SystemExit(message)


_ensure_dependencies()


def _resolve_ffmpeg() -> str:
    """Return an ffmpeg executable path or exit with a helpful hint."""

    candidates: list[str] = []
    seen: set[str] = set()
    candidates = []

    # 1) Explicit override from env
    env_value = os.environ.get(FFMPEG_ENV_VAR)
    if env_value:
        direct_env_path = Path(env_value).expanduser()
        if direct_env_path.exists():
            candidates.append(str(direct_env_path))
        env_path = shutil.which(env_value)
        if env_path:
            candidates.append(env_path)

    # 2) Standard PATH discovery
    candidates.extend(filter(None, [shutil.which("ffmpeg"), shutil.which("ffmpeg.exe")]))

    # 3) Local copies near the repo (common Windows unzip pattern)
    for local_candidate in [
        REPO_ROOT / "ffmpeg.exe",
        REPO_ROOT / "ffmpeg" / "bin" / "ffmpeg.exe",
        REPO_ROOT / "ffmpeg" / "bin" / "ffmpeg",
    ]:
        if local_candidate.exists():
            candidates.append(str(local_candidate))

    for candidate in candidates:
        if not candidate:
            continue

        candidate_path = Path(candidate).expanduser().resolve()
        candidate_key = str(candidate_path)
        if candidate_key in seen:
            continue
        seen.add(candidate_key)

        if candidate_path.exists():
            return candidate_key
    local_ffmpeg = REPO_ROOT / "ffmpeg.exe"
    if local_ffmpeg.exists():
        candidates.append(str(local_ffmpeg))

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))

    hint = (
        "ffmpeg introuvable. Installez-le et ajoutez-le au PATH, ou fournissez "
        f"un chemin explicite via la variable d'environnement {FFMPEG_ENV_VAR} "
        "(ex: setx FFMPEG_PATH C:\\chemin\\vers\\ffmpeg.exe sous Windows)."
    )
    raise SystemExit(hint)
def _ensure_ffmpeg() -> None:
    """Check ffmpeg availability with a clear, user-friendly hint."""

    if shutil.which("ffmpeg") is None:
        hint = (
            "ffmpeg introuvable. Installez-le et assurez-vous que la commande "
            "`ffmpeg` est accessible via le PATH (ex: `sudo apt-get install ffmpeg` "
            "sur Linux, ou installer le zip Windows puis ajouter `bin` au PATH)."
        )
        raise SystemExit(hint)

from dj_identifier.pipeline import bootstrap_store, run_pipeline
from dj_identifier.types import TrackMatch

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


def extract_audio(video_path: Path, workdir: Path, ffmpeg_path: str) -> Path:
def extract_audio(video_path: Path, workdir: Path) -> Path:
    """Utilise ffmpeg pour extraire l'audio mono du conteneur vidéo."""

    output = workdir / f"{video_path.stem}.wav"
    command = [
        ffmpeg_path,
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
    subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
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
    parser.add_argument(
        "--min-segment-duration",
        type=float,
        default=1.0,
        help="Fusionne/ignore les segments plus courts que cette durée (secondes)",
    )
    parser.add_argument(
        "--max-segments",
        type=int,
        default=None,
        help="Limite facultative du nombre de segments détectés",
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

    try:
        ffmpeg_path = _resolve_ffmpeg()
        _ensure_ffmpeg()
    except SystemExit as exc:
        print(exc)
        return 1

    store = ensure_store()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = extract_audio(video_path, Path(tmpdir), ffmpeg_path)
            matches = run_pipeline(
                str(audio_path),
                store,
                max_segments=args.max_segments,
                min_segment_duration=args.min_segment_duration,
            )
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
