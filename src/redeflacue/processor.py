"""Cue sheet discovery, extraction planning and the per-cue run loop."""

from __future__ import annotations

import logging
import shlex
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from deflacue.parser import CueParser

from redeflacue.splitter import build_sox_command, run_sox, sanitize

LOGGER = logging.getLogger(__name__)

# deflacue stores TrackContext.start as 44.1 kHz samples. 44100 and the
# CD-frame grid (75 Hz) are commensurate (588 samples/frame), so dividing
# yields the exact cue position in seconds regardless of the source rate.
CUE_SAMPLE_RATE = 44100.0


@dataclass(frozen=True)
class Extraction:
    """One planned track cut: ``[start_s, end_s)`` of ``src`` written to ``dst``."""

    src: Path
    dst: Path
    start_s: float
    end_s: float | None
    tags: dict[str, Any] = field(default_factory=dict)


def iter_cue_files(root: Path, recursive: bool) -> Iterator[Path]:
    """Yield .cue files under ``root``, skipping previous ``deflacue`` output dirs."""
    walker = root.rglob("*.cue") if recursive else root.glob("*.cue")
    for p in sorted(walker):
        if "deflacue" in p.parts:
            continue
        yield p


def bundle_dir(cue: Any, target_root: Path) -> Path:
    """Return ``target_root/<performer>/<[date - ]album>`` for a parsed cue."""
    meta = cue.meta.data
    performer = sanitize(meta.get("PERFORMER", "Unknown"))
    album_raw = meta.get("ALBUM", "Unknown")
    date = meta.get("DATE")
    album = sanitize(f"{date} - {album_raw}" if date else album_raw)
    return target_root / performer / album


def plan_extractions(cue: Any, cue_dir: Path, target_root: Path) -> list[Extraction]:
    """Turn a parsed :class:`deflacue.parser.CueData` into a list of track cuts.

    Pure: touches neither sox nor the filesystem. Relative ``FILE`` paths are
    resolved against ``cue_dir``; output files go under :func:`bundle_dir`.
    """
    bundle = bundle_dir(cue, target_root)
    width = len(str(len(cue.tracks)))
    plan: list[Extraction] = []

    for fctx in cue.files:
        src = fctx.path
        if not src.is_absolute():
            src = (cue_dir / src).resolve()

        for i, t in enumerate(fctx.tracks):
            start_s = t.start / CUE_SAMPLE_RATE
            end_s = fctx.tracks[i + 1].start / CUE_SAMPLE_RATE if i + 1 < len(fctx.tracks) else None
            num = str(t.num).rjust(width, "0")
            dst = bundle / f"{num} - {sanitize(t.title)}.flac"
            plan.append(Extraction(src, dst, start_s, end_s, dict(t.data)))

    return plan


def process_cue(cue_file: Path, target_root: Path, encoding: str | None, dry_run: bool) -> None:
    """Parse ``cue_file`` and extract all of its tracks under ``target_root``."""
    LOGGER.info("Processing %s", cue_file.name)
    cue = CueParser.from_file(fpath=cue_file, encoding=encoding).run()

    if not dry_run:
        bundle_dir(cue, target_root).mkdir(parents=True, exist_ok=True)

    missing: set[Path] = set()
    for ex in plan_extractions(cue, cue_file.parent, target_root):
        if ex.src in missing:
            continue
        if not ex.src.exists():
            LOGGER.error("Source %s not found; skipping its tracks.", ex.src)
            missing.add(ex.src)
            continue

        cmd = build_sox_command(ex.src, ex.dst, ex.start_s, ex.end_s, ex.tags)
        LOGGER.info("  -> %s", ex.dst.name)
        LOGGER.debug("  cmd: %s", shlex.join(cmd))
        if not dry_run:
            run_sox(cmd)
