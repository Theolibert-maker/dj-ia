"""Segment a DJ set into track-like regions using onset strength peaks."""
from __future__ import annotations

from typing import Iterable, List

import numpy as np

from .types import TrackSegment, samples_to_seconds


def onset_boundaries(
    y: np.ndarray,
    sr: int,
    hop_length: int = 512,
    max_segments: int | None = None,
    min_duration: float = 2.5,
) -> List[TrackSegment]:
    """
    Estimate track boundaries using onset peaks.

    The algorithm leverages librosa's onset detection to find large energy changes,
    which roughly correlate to mix transitions. Boundaries are clipped to the audio
    duration and deduplicated. Short blips are merged forward to avoid unstable
    fingerprint windows.
    """

    import librosa

    onset_frames = librosa.onset.onset_detect(
        y=y,
        sr=sr,
        hop_length=hop_length,
        backtrack=True,
        units="frames",
    )

    frame_boundaries = [0, *sorted(set(int(f) for f in onset_frames))]
    if max_segments:
        frame_boundaries = frame_boundaries[: max_segments + 1]

    frame_boundaries.append(len(y) // hop_length)
    times = samples_to_seconds([b * hop_length for b in frame_boundaries], sr)

    segments: List[TrackSegment] = []
    current_start = times[0]

    for end in times[1:]:
        duration = end - current_start
        if duration <= 0:
            current_start = end
            continue

        if duration < min_duration and segments:
            # Merge short blips into the previous segment to avoid tiny windows.
            segments[-1] = TrackSegment(start=segments[-1].start, end=end)
        elif duration >= min_duration:
            segments.append(TrackSegment(start=current_start, end=end))

        current_start = end

    # If the tail is still short, merge it backward to keep windows stable.
    if segments and segments[-1].duration() < min_duration:
        last = segments.pop()
        if segments:
            segments[-1] = TrackSegment(start=segments[-1].start, end=last.end)
        else:
            segments.append(last)

    return segments


def load_audio(path: str, sr: int = 22050) -> tuple[np.ndarray, int]:
    """Load audio as mono float32 using librosa."""

    import librosa

    y, sr = librosa.load(path, sr=sr, mono=True)
    return y, sr


def slice_audio(y: np.ndarray, sr: int, segments: Iterable[TrackSegment]) -> List[np.ndarray]:
    """Yield audio slices matching the provided segments."""

    slices: List[np.ndarray] = []
    for segment in segments:
        start = int(segment.start * sr)
        end = int(segment.end * sr)
        slices.append(y[start:end])
    return slices
