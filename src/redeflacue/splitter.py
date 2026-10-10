"""Build and run SoX commands."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path

CUE_TO_VORBIS = {
    "TRACK_NUM": "TRACKNUMBER",
    "TITLE": "TITLE",
    "PERFORMER": "ARTIST",
    "ALBUM": "ALBUM",
    "GENRE": "GENRE",
    "DATE": "DATE",
    "ISRC": "ISRC",
    "COMMENT": "DESCRIPTION",
}


def fmt_time(seconds: float) -> str:
    """Format seconds for `sox trim`."""
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:09.6f}"


def sanitize(name: str) -> str:
    """Remove path separators from a cue-sheet value."""
    return name.replace("/", "")


def build_sox_command(
    src: Path,
    dst: Path,
    start_s: float,
    end_s: float | None,
    tags: Mapping[str, str | None],
) -> list[str]:
    """Build the SoX command for one track."""
    cmd = ["sox", "-V1", str(src), "--comment="]
    for cue_key, vorbis_key in CUE_TO_VORBIS.items():
        val = tags.get(cue_key)
        if val:
            cmd.append(f"--add-comment={vorbis_key}={val}")
    cmd += [str(dst), "trim", fmt_time(start_s)]
    if end_s is not None:
        cmd.append(f"={fmt_time(end_s)}")  # Absolute end time, not duration.
    return cmd


def run_sox(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)
