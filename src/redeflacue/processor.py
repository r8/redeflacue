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

# deflacue stores cue positions at 44.1 kHz; dividing by that rate recovers
# the original 75-frames-per-second cue timestamp.
CUE_SAMPLE_RATE = 44100.0


@dataclass(frozen=True)
class Extraction:
    src: Path
    dst: Path
    start_s: float
    end_s: float | None
    tags: dict[str, Any] = field(default_factory=dict)


def iter_cue_files(root: Path, recursive: bool) -> Iterator[Path]:
    """Yield cue sheets, excluding previous output directories."""
    walker = root.rglob("*.cue") if recursive else root.glob("*.cue")
    for p in sorted(walker):
        if "deflacue" in p.parts:
            continue
        yield p


def bundle_dir(cue: Any, target_root: Path) -> Path:
    """Return the album output directory for a parsed cue sheet."""
    meta = cue.meta.data
    performer = sanitize(meta.get("PERFORMER", "Unknown"))
    album_raw = meta.get("ALBUM", "Unknown")
    date = meta.get("DATE")
    album = sanitize(f"{date} - {album_raw}" if date else album_raw)
    return target_root / performer / album


def plan_extractions(cue: Any, cue_dir: Path, target_root: Path) -> list[Extraction]:
    """Build track extractions without touching SoX or the filesystem."""
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
    """Parse a cue sheet and extract its tracks."""
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
