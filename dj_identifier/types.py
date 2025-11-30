"""Data structures shared across the DJ identification pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence


@dataclass
class TrackSegment:
    """Audio slice boundaries in seconds."""

    start: float
    end: float

    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class SegmentFingerprint:
    """Fingerprint data for a track segment."""

    segment: TrackSegment
    hash: str


@dataclass
class TrackMatch:
    """Match between a fingerprint and known track metadata."""

    segment: TrackSegment
    track_id: str
    title: str
    artist: str
    confidence: float


def seconds_to_samples(seconds: float, sr: int) -> int:
    return int(seconds * sr)


def samples_to_seconds(samples: Sequence[int], sr: int) -> List[float]:
    return [sample / float(sr) for sample in samples]
