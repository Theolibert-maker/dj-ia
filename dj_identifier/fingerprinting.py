"""Fingerprint audio slices using chroma features and hashing."""
from __future__ import annotations

import hashlib
import inspect
import warnings
from typing import Dict, Iterable, List, Sequence

import numpy as np

from .types import SegmentFingerprint, TrackSegment


def _safe_n_fft(length: int, max_n_fft: int = 1024, min_n_fft: int = 32) -> int:
    """Select an FFT size that never exceeds the available samples."""

    if length <= 0:
        return min_n_fft

    capped = min(max_n_fft, length)
    if capped < min_n_fft:
        return length
    return capped


def chroma_fingerprint(y: np.ndarray, sr: int, *, max_n_fft: int = 1024) -> str:
    """Create a compact, deterministic fingerprint string from chroma features."""

    import librosa

    n_fft = _safe_n_fft(len(y), max_n_fft=max_n_fft)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r".*n_fft=.*too large for input signal.*",
            category=UserWarning,
        )
        chroma = librosa.feature.chroma_stft(y=y, sr=sr, n_fft=n_fft)
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
    min_samples: int = 4096,
    min_duration: float | None = None,
) -> List[SegmentFingerprint]:
    """Fingerprint each segment individually."""

    fingerprints: List[SegmentFingerprint] = []
    minimum = max(min_samples, int(sr * (min_duration or 0)))

    total = len(segments)
    print(f"[Empreintes] Préparation des empreintes pour {total} segment(s)…")

    for idx, segment in enumerate(segments, start=1):
        print(f"  - Segment {idx}/{total} : empreinte en cours…")
        start = int(segment.start * sr)
        end = int(segment.end * sr)
        slice_ = y[start:end]
        if len(slice_) < minimum:
            print("    > Segment trop court, ignoré")
            continue
        try:
            kwargs = {}
            signature = inspect.signature(fingerprint_fn)
            if "max_n_fft" in signature.parameters:
                kwargs["max_n_fft"] = _safe_n_fft(len(slice_))
            digest = fingerprint_fn(slice_, sr, **kwargs)
        except Exception:
            # Skip unstable slices instead of crashing the pipeline.
            print("    > Erreur d'empreinte, segment ignoré")
            continue
        fingerprints.append(SegmentFingerprint(segment=segment, hash=digest))
        print("    > Empreinte générée")
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
    total = len(fingerprints)
    for idx, fp in enumerate(fingerprints, start=1):
        print(f"→ Processing segment {idx} / {total}")
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
        else:
            print("No match for this segment")
    return results
