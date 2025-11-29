"""Fingerprint audio slices using chroma features and hashing."""
from __future__ import annotations

import hashlib
from typing import Dict, Iterable, List, Sequence

import numpy as np

from .types import SegmentFingerprint, TrackSegment


def chroma_fingerprint(y: np.ndarray, sr: int) -> str:
    """Create a compact, deterministic fingerprint string from chroma features."""

    import librosa

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    normalized = chroma / np.maximum(np.linalg.norm(chroma, axis=0, keepdims=True), 1e-6)
    pooled = normalized.mean(axis=1)
    quantized = np.clip((pooled * 100).astype(int), -128, 127)
    digest = hashlib.sha1(quantized.tobytes()).hexdigest()
    return digest


def fingerprint_segments(
    y: np.ndarray,
    sr: int,
    segments: Sequence[TrackSegment],
    fingerprint_fn=chroma_fingerprint,
    min_samples: int = 2048,
) -> List[SegmentFingerprint]:
    """Fingerprint each segment individually."""

    fingerprints: List[SegmentFingerprint] = []
    for segment in segments:
        start = int(segment.start * sr)
        end = int(segment.end * sr)
        slice_ = y[start:end]
        if len(slice_) < min_samples:
            continue
        digest = fingerprint_fn(slice_, sr)
        fingerprints.append(SegmentFingerprint(segment=segment, hash=digest))
    return fingerprints


FingerprintDB = Dict[str, Dict[str, str]]


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    set_a = set(a)
    set_b = set(b)
    if not set_a and not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def match_fingerprints(
    fingerprints: Sequence[SegmentFingerprint],
    database: FingerprintDB,
    min_score: float = 0.1,
) -> List[tuple[SegmentFingerprint, str, float]]:
    """Return (fingerprint, track_id, score) matches ordered by segment order."""

    results: List[tuple[SegmentFingerprint, str, float]] = []
    for fp in fingerprints:
        best_track = None
        best_score = 0.0
        for track_id, entry in database.items():
            db_hashes = entry.get("hashes", [])
            score = jaccard([fp.hash], db_hashes)
            if score > best_score:
                best_score = score
                best_track = track_id
        if best_track is not None and best_score >= min_score:
            results.append((fp, best_track, best_score))
    return results
