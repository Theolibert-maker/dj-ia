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
    min_segment_duration: float = 1.0,
) -> List[TrackMatch]:
    """
    End-to-end pipeline that produces timecoded matches for a DJ set.

    The function loads audio, detects coarse boundaries, fingerprints each slice, and
    looks up matches in the supplied fingerprint store.
    """

    y, sr = load_audio(audio_path, sr=target_sr)
    segments = onset_boundaries(y, sr, max_segments=max_segments, min_duration=min_segment_duration)
    segments = onset_boundaries(y, sr, max_segments=max_segments)
    fingerprints: Iterable[SegmentFingerprint] = fingerprint_segments(y, sr, segments)
    return build_matches(fingerprints, fingerprint_store)


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
