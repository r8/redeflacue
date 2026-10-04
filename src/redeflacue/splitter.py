"""sox invocation and time formatting.

deflacue converts cue positions to sample counts at a hardcoded 44100 Hz and
passes them to ``sox trim {n}s``. sox interprets those in the *input* rate,
so on 96/192 kHz sources every cut lands at ``actual_rate / 44100`` of the
intended position. Here the positions are handed to sox as wall-clock
times instead, which is independent of the sample rate.
"""

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
    """Seconds -> HH:MM:SS.ssssss for sox trim."""
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:09.6f}"


def sanitize(name: str) -> str:
    """Make a cue string safe to use as a single path component."""
    return name.replace("/", "")


def build_sox_command(
    src: Path,
    dst: Path,
    start_s: float,
    end_s: float | None,
    tags: Mapping[str, str | None],
) -> list[str]:
    """Return the sox argv that extracts ``[start_s, end_s)`` of ``src`` into ``dst``.

    ``end_s=None`` means "until the end of the file". Cue tags are mapped to
    Vorbis comments via :data:`CUE_TO_VORBIS`; source comments are dropped.
    """
    cmd = ["sox", "-V1", str(src), "--comment="]
    for cue_key, vorbis_key in CUE_TO_VORBIS.items():
        val = tags.get(cue_key)
        if val:
            cmd.append(f"--add-comment={vorbis_key}={val}")
    cmd += [str(dst), "trim", fmt_time(start_s)]
    if end_s is not None:
        cmd.append(f"={fmt_time(end_s)}")  # '=' makes 2nd arg absolute
    return cmd


def run_sox(cmd: list[str]) -> None:
    """Run a sox command, raising :class:`subprocess.CalledProcessError` on failure."""
    subprocess.run(cmd, check=True)
