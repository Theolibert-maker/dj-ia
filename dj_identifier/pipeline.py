"""High-level pipeline for DJ set segmentation and identification."""
from __future__ import annotations

from typing import Iterable, List

from .fingerprinting import FingerprintDB, fingerprint_segments
from .metadata import FingerprintStore, build_matches
from .segmentation import load_audio, onset_boundaries
from .types import SegmentFingerprint, TrackMatch


def run_pipeline(
    audio_path: str,
    fingerprint_store: FingerprintStore,
    target_sr: int = 22050,
    max_segments: int | None = None,
    min_segment_duration: float = 2.5,
    min_fingerprint_samples: int = 4096,
) -> List[TrackMatch]:
    """
    End-to-end pipeline that produces timecoded matches for a DJ set.

    The function loads audio, detects coarse boundaries, fingerprints each slice, and
    looks up matches in the supplied fingerprint store.
    """

    print("[Chargement] Chargement de l'audio…")
    y, sr = load_audio(audio_path, sr=target_sr)
    print(f"[Chargement] Audio chargé (échantillons: {len(y)}, sr: {sr})")

    print("[Segmentation] Détection des segments…")
    segments = onset_boundaries(y, sr, max_segments=max_segments, min_duration=min_segment_duration)
    print(f"[Segmentation] {len(segments)} segment(s) détecté(s)")

    print("[Empreintes] Génération des empreintes digitales…")
    fingerprints: List[SegmentFingerprint] = fingerprint_segments(
        y,
        sr,
        segments,
        min_samples=min_fingerprint_samples,
        min_duration=min_segment_duration,
    )
    print(f"[Empreintes] Génération terminée ({len(fingerprints)} empreinte(s))")

    print("[Correspondances] Recherche des correspondances…")
    matches = build_matches(fingerprints, fingerprint_store)
    print(f"[Correspondances] {len(matches)} correspondance(s) trouvée(s)")
    return matches


def bootstrap_store(samples: FingerprintDB, path: str | None = None) -> FingerprintStore:
    """Create a FingerprintStore preloaded with sample hashes."""

    store = FingerprintStore(path or "fingerprints.json")
    for track_id, record in samples.items():
        store.add_track(
            track_id=track_id,
            title=record.get("title", track_id),
            artist=record.get("artist", "unknown"),
            hashes=record.get("hashes", []),
        )
    return store
