from __future__ import annotations

import locale
import logging
import shutil
from pathlib import Path

import pytest
from deflacue.exceptions import ParserError
from deflacue.parser import CueParser

from redeflacue import processor
from redeflacue.processor import (
    Extraction,
    bundle_dir,
    iter_cue_files,
    plan_extractions,
    process_cue,
)

OUT = Path("/out")


def parse(path: Path, encoding: str | None = None) -> object:
    return CueParser.from_file(fpath=path, encoding=encoding).run()


def test_plan_single_file_192k(fixtures_dir: Path) -> None:
    cue = parse(fixtures_dir / "sample_192k.cue")
    plan = plan_extractions(cue, fixtures_dir, OUT)

    src = (fixtures_dir / "album_192k.flac").resolve()
    bundle = OUT / "Test Artist" / "1988 - Hi-Res Image"
    assert [(e.src, e.dst.name) for e in plan] == [
        (src, "1 - Opening.flac"),
        (src, "2 - Second Movement.flac"),
        (src, "3 - Before  After.flac"),
        (src, "4 - Long Coda.flac"),
    ]
    assert all(e.dst.parent == bundle for e in plan)

    # Hand-computed from the INDEX 01 positions (mm*60 + ss + ff/75).
    starts = [0.0, 208 + 10 / 75, 417 + 74 / 75, 3725 + 37 / 75]
    assert [e.start_s for e in plan] == pytest.approx(starts, abs=1e-9)
    assert [e.end_s for e in plan[:-1]] == pytest.approx(starts[1:], abs=1e-9)
    assert plan[-1].end_s is None


def test_plan_ignores_index_00(fixtures_dir: Path) -> None:
    # Track 2 has INDEX 00 03:27:50 (pregap); the cut must use INDEX 01 03:28:10.
    plan = plan_extractions(parse(fixtures_dir / "sample_192k.cue"), fixtures_dir, OUT)
    assert plan[1].start_s == pytest.approx(208 + 10 / 75, abs=1e-9)
    assert plan[0].end_s == pytest.approx(208 + 10 / 75, abs=1e-9)


def test_plan_tags(fixtures_dir: Path) -> None:
    plan = plan_extractions(parse(fixtures_dir / "sample_192k.cue"), fixtures_dir, OUT)

    first, last = plan[0].tags, plan[-1].tags
    assert first["TRACK_NUM"] == "1"
    assert first["TITLE"] == "Opening"
    assert first["PERFORMER"] == "Test Artist"
    assert first["ALBUM"] == "Hi-Res Image"
    assert first["GENRE"] == "Art Rock"
    assert first["DATE"] == "1988"
    # Track-level PERFORMER/ISRC override/extend the album-level values.
    assert last["PERFORMER"] == "Guest Artist"
    assert last["ISRC"] == "GBAAA8800004"
    assert "ISRC" not in first


def test_plan_multi_file_gapless(fixtures_dir: Path) -> None:
    plan = plan_extractions(parse(fixtures_dir / "sample_multi_file.cue"), fixtures_dir, OUT)

    side_a = (fixtures_dir / "side_a.flac").resolve()
    side_b = (fixtures_dir / "side_b.flac").resolve()
    bundle = OUT / "Gapless Band" / "2001 - Two Sides"
    assert plan == [
        Extraction(side_a, bundle / "1 - Side A Opener.flac", 0.0, 252 + 33 / 75, plan[0].tags),
        Extraction(side_a, bundle / "2 - Crossfade Into B.flac", 252 + 33 / 75, None, plan[1].tags),
        Extraction(side_b, bundle / "3 - Side B Continues.flac", 0.0, 301 + 1 / 75, plan[2].tags),
        Extraction(side_b, bundle / "4 - Closer.flac", 301 + 1 / 75, None, plan[3].tags),
    ]


def test_plan_windows1251(fixtures_dir: Path) -> None:
    cue = parse(fixtures_dir / "sample_windows1251.cue", encoding="windows-1251")
    plan = plan_extractions(cue, fixtures_dir, OUT)

    bundle = OUT / "Исполнитель" / "1995 - Альбом"
    assert [e.dst for e in plan] == [
        bundle / "1 - Первая песня.flac",
        bundle / "2 - Вторая  последняя.flac",
    ]
    assert plan[0].end_s == pytest.approx(165 + 60 / 75, abs=1e-9)
    assert plan[1].tags["TITLE"] == "Вторая / последняя"


@pytest.mark.skipif(
    locale.getpreferredencoding(False).lower().replace("-", "") != "utf8",
    reason="needs a UTF-8 default locale for the cp1251 bytes to be undecodable",
)
def test_windows1251_without_encoding_fails(fixtures_dir: Path) -> None:
    with pytest.raises(ParserError):
        parse(fixtures_dir / "sample_windows1251.cue")


def test_plan_pads_track_numbers_to_track_count(tmp_path: Path) -> None:
    lines = ['PERFORMER "P"', 'TITLE "A"', 'FILE "x.flac" WAVE']
    for n in range(1, 13):
        lines += [f"TRACK {n:02d} AUDIO", f'TITLE "T{n}"', f"INDEX 01 {n:02d}:00:00"]
    plan = plan_extractions(CueParser(lines).run(), tmp_path, OUT)

    assert plan[0].dst.name == "01 - T1.flac"
    assert plan[-1].dst.name == "12 - T12.flac"


def test_plan_keeps_absolute_file_path_and_defaults(tmp_path: Path) -> None:
    lines = ['FILE "/abs/image.flac" WAVE', "TRACK 01 AUDIO", "INDEX 01 00:00:00"]
    cue = CueParser(lines).run()
    (ex,) = plan_extractions(cue, tmp_path, OUT)

    assert ex.src == Path("/abs/image.flac")
    # No PERFORMER/TITLE/DATE: deflacue's defaults, no "date - " prefix.
    assert bundle_dir(cue, OUT) == OUT / "Unknown" / "Unknown"
    assert ex.dst == OUT / "Unknown" / "Unknown" / "1 - Unknown.flac"


def test_bundle_dir_sanitizes_performer_and_album() -> None:
    lines = ['PERFORMER "AC/DC"', 'TITLE "Live / Studio"', 'FILE "x.flac" WAVE']
    assert bundle_dir(CueParser(lines).run(), OUT) == OUT / "ACDC" / "Live  Studio"


def test_iter_cue_files(tmp_path: Path) -> None:
    (tmp_path / "b.cue").touch()
    (tmp_path / "a.cue").touch()
    (tmp_path / "notes.txt").touch()
    (tmp_path / "disc2").mkdir()
    (tmp_path / "disc2" / "c.cue").touch()
    (tmp_path / "deflacue").mkdir()
    (tmp_path / "deflacue" / "old.cue").touch()

    assert list(iter_cue_files(tmp_path, recursive=False)) == [
        tmp_path / "a.cue",
        tmp_path / "b.cue",
    ]
    assert list(iter_cue_files(tmp_path, recursive=True)) == [
        tmp_path / "a.cue",
        tmp_path / "b.cue",
        tmp_path / "disc2" / "c.cue",
    ]


def test_process_cue_dry_run_creates_nothing(
    album_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(processor, "run_sox", lambda cmd: pytest.fail("sox must not run"))
    out = tmp_path / "out"

    process_cue(album_dir / "sample_192k.cue", out, None, dry_run=True)

    assert not out.exists()


def test_process_cue_runs_sox_per_track(
    album_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(processor, "run_sox", calls.append)
    out = tmp_path / "out"

    process_cue(album_dir / "sample_192k.cue", out, None, dry_run=False)

    bundle = out / "Test Artist" / "1988 - Hi-Res Image"
    assert bundle.is_dir()
    assert [c[c.index("trim") + 1 :] for c in calls] == [
        ["00:00:00.000000", "=00:03:28.133333"],
        ["00:03:28.133333", "=00:06:57.986667"],
        ["00:06:57.986667", "=01:02:05.493333"],
        ["01:02:05.493333"],
    ]
    assert [Path(c[c.index("trim") - 1]) for c in calls] == [
        bundle / "1 - Opening.flac",
        bundle / "2 - Second Movement.flac",
        bundle / "3 - Before  After.flac",
        bundle / "4 - Long Coda.flac",
    ]


def test_process_cue_skips_missing_source_once(
    fixtures_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    album = tmp_path / "album"
    album.mkdir()
    shutil.copy(fixtures_dir / "sample_multi_file.cue", album)
    (album / "side_a.flac").touch()  # side_b.flac is missing
    calls: list[list[str]] = []
    monkeypatch.setattr(processor, "run_sox", calls.append)
    caplog.set_level(logging.INFO, logger="redeflacue")

    process_cue(album / "sample_multi_file.cue", tmp_path / "out", None, dry_run=False)

    assert [Path(c[2]).name for c in calls] == ["side_a.flac", "side_a.flac"]
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == [f"Source {(album / 'side_b.flac').resolve()} not found; skipping its tracks."]
