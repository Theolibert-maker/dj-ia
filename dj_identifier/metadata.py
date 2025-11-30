"""Metadata helpers for fingerprint lookups."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List

from .types import SegmentFingerprint, TrackMatch


class FingerprintStore:
    """Lightweight on-disk fingerprint database using JSON."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data: Dict[str, Dict[str, str]] = {}

    @property
    def data(self) -> Dict[str, Dict[str, str]]:
        if not self._data:
            self._data = self._load()
        return self._data

    def _load(self) -> Dict[str, Dict[str, str]]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save(self) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, sort_keys=True)

    def add_track(self, track_id: str, title: str, artist: str, hashes: Iterable[str]) -> None:
        self.data[track_id] = {
            "title": title,
            "artist": artist,
            "hashes": list(hashes),
        }

    def resolve(self, track_id: str) -> Dict[str, str]:
        return self.data.get(track_id, {})


from .fingerprinting import match_fingerprints


def build_matches(
    fingerprints: Iterable[SegmentFingerprint],
    store: FingerprintStore,
    min_score: float = 0.1,
) -> List[TrackMatch]:
    """Resolve fingerprint matches to full metadata records."""

    matches = []
    for fp, track_id, score in match_fingerprints(list(fingerprints), store.data, min_score=min_score):
        meta = store.resolve(track_id)
        matches.append(
            TrackMatch(
                segment=fp.segment,
                track_id=track_id,
                title=meta.get("title", track_id),
                artist=meta.get("artist", "unknown"),
                confidence=score,
            )
        )
    return matches
