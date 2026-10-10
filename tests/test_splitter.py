from __future__ import annotations

import re
from fractions import Fraction
from pathlib import Path

import pytest
from deflacue.parser import pos_to_frames

from redeflacue import splitter
from redeflacue.splitter import CUE_TO_VORBIS, build_sox_command, fmt_time, run_sox, sanitize


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "00:00:00.000000"),
        (0.0, "00:00:00.000000"),
        (0.5, "00:00:00.500000"),
        (1 / 75, "00:00:00.013333"),  # one CD frame
        (0.000001, "00:00:00.000001"),
        (59.0, "00:00:59.000000"),
        (60.0, "00:01:00.000000"),
        (61.25, "00:01:01.250000"),
        (120.0, "00:02:00.000000"),
        (3599.0, "00:59:59.000000"),
        (3600.0, "01:00:00.000000"),
        (3725.5, "01:02:05.500000"),
        (36000.0, "10:00:00.000000"),
    ],
)
def test_fmt_time(seconds: float, expected: str) -> None:
    assert fmt_time(seconds) == expected


def test_fmt_time_cd_frames_never_round_up_to_sixty() -> None:
    # Fractional parts on the 75 Hz grid are at least 1/75 s away from the
    # next whole second, so 6-digit rounding can never yield "60.000000".
    for ss in range(60):
        for ff in range(75):
            seconds_field = float(fmt_time(ss + ff / 75).rsplit(":", 1)[1])
            assert seconds_field < 60


@pytest.mark.parametrize("mm", [0, 1, 3, 9, 42, 59, 74, 99])
def test_cue_positions_divide_exactly_by_44100(mm: int) -> None:
    """Converting deflacue's sample offsets back to cue time loses no precision."""
    for ss in range(60):
        for ff in range(75):
            samples = pos_to_frames(f"{mm:02d}:{ss:02d}:{ff:02d}")
            exact = mm * 60 + ss + Fraction(ff, 75)

            assert samples % 588 == 0
            assert Fraction(samples, 44100) == exact
            assert samples / 44100.0 == pytest.approx(float(exact), abs=1e-9)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("AC/DC", "ACDC"),
        ("Before / After", "Before  After"),
        ("a/b/c", "abc"),
        ("No slashes here", "No slashes here"),
        ("back\\slash", "back\\slash"),
        ("", ""),
    ],
)
def test_sanitize(raw: str, expected: str) -> None:
    assert sanitize(raw) == expected


def test_build_sox_command_full() -> None:
    tags = {
        "TRACK_NUM": "2",
        "TITLE": "Second Movement",
        "PERFORMER": "Test Artist",
        "ALBUM": "Hi-Res Image",
        "GENRE": "Art Rock",
        "DATE": "1988",
        "ISRC": "GBAAA8800002",
        "COMMENT": "fixture",
    }
    cmd = build_sox_command(
        Path("/music/album.flac"), Path("/out/2 - Second Movement.flac"), 208 + 10 / 75, 300.0, tags
    )
    assert cmd == [
        "sox",
        "-V1",
        "/music/album.flac",
        "--comment=",
        "--add-comment=TRACKNUMBER=2",
        "--add-comment=TITLE=Second Movement",
        "--add-comment=ARTIST=Test Artist",
        "--add-comment=ALBUM=Hi-Res Image",
        "--add-comment=GENRE=Art Rock",
        "--add-comment=DATE=1988",
        "--add-comment=ISRC=GBAAA8800002",
        "--add-comment=DESCRIPTION=fixture",
        "/out/2 - Second Movement.flac",
        "trim",
        "00:03:28.133333",
        "=00:05:00.000000",
    ]


def test_build_sox_command_last_track_has_no_end() -> None:
    cmd = build_sox_command(Path("in.flac"), Path("out.flac"), 3725 + 37 / 75, None, {})
    assert cmd == ["sox", "-V1", "in.flac", "--comment=", "out.flac", "trim", "01:02:05.493333"]


def test_build_sox_command_skips_empty_and_unknown_tags() -> None:
    tags = {"TITLE": "", "DATE": None, "PERFORMER": "X", "INDEX 01": "00:00:00", "FLAGS": "DCP"}
    cmd = build_sox_command(Path("in.flac"), Path("out.flac"), 0.0, 1.0, tags)
    comments = [a for a in cmd if a.startswith("--add-comment=")]
    assert comments == ["--add-comment=ARTIST=X"]


def test_build_sox_command_tag_order_follows_mapping() -> None:
    tags = {cue_key: "v" for cue_key in reversed(list(CUE_TO_VORBIS))}
    cmd = build_sox_command(Path("in.flac"), Path("out.flac"), 0.0, None, tags)
    comments = [a.split("=")[1] for a in cmd if a.startswith("--add-comment=")]
    assert comments == list(CUE_TO_VORBIS.values())


def test_build_sox_command_uses_times_not_sample_counts() -> None:
    # The deflacue bug was `trim <n>s`; positions must be rate-agnostic times.
    cmd = build_sox_command(Path("in.flac"), Path("out.flac"), 12.5, 99.0, {})
    trim_args = cmd[cmd.index("trim") + 1 :]
    assert trim_args == ["00:00:12.500000", "=00:01:39.000000"]
    assert not any(re.fullmatch(r"=?\d+s", a) for a in trim_args)


def test_run_sox_calls_subprocess_with_check(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []
    monkeypatch.setattr(splitter.subprocess, "run", lambda cmd, **kw: calls.append((cmd, kw)))

    run_sox(["sox", "a.flac", "b.flac"])

    assert calls == [(["sox", "a.flac", "b.flac"], {"check": True})]
