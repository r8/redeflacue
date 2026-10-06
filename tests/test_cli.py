from __future__ import annotations

import logging
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import redeflacue
from redeflacue import cli
from redeflacue.cli import build_parser, main

SOX = shutil.which("sox")


@pytest.fixture
def fake_sox(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend sox is installed so --dry-run tests don't need the binary."""
    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/usr/bin/{name}")


def logged_commands(caplog: pytest.LogCaptureFixture) -> list[list[str]]:
    prefix = "  cmd: "
    return [
        shlex.split(r.getMessage()[len(prefix) :])
        for r in caplog.records
        if r.getMessage().startswith(prefix)
    ]


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"redeflacue {redeflacue.__version__}"


def test_parser_defaults() -> None:
    args = build_parser().parse_args(["some/dir"])
    assert args.source == Path("some/dir")
    assert args.dest is None
    assert args.encoding is None
    assert args.recursive is False
    assert args.dry_run is False
    assert args.verbose is False


def test_parser_accepts_deflacue_flags() -> None:
    args = build_parser().parse_args(
        ["-e", "windows-1251", "-r", "-d", "/mnt/out", "--dry-run", "-v", "/raw"]
    )
    assert args.encoding == "windows-1251"
    assert args.recursive is True
    assert args.dest == Path("/mnt/out")
    assert args.dry_run is True
    assert args.verbose is True
    assert args.source == Path("/raw")


def test_source_is_required(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    assert "source" in capsys.readouterr().err


def test_missing_sox(
    album_dir: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)
    assert main([str(album_dir), "--dry-run"]) == 1
    assert "sox not found" in caplog.text


def test_missing_source_dir(
    tmp_path: Path, fake_sox: None, caplog: pytest.LogCaptureFixture
) -> None:
    assert main([str(tmp_path / "nope")]) == 1
    assert "does not exist" in caplog.text


def test_dry_run_end_to_end(
    album_dir: Path, fake_sox: None, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="redeflacue")

    assert main([str(album_dir), "--dry-run", "-v"]) == 0

    bundle = album_dir.resolve() / "deflacue" / "Test Artist" / "1988 - Hi-Res Image"
    src = str(album_dir.resolve() / "album_192k.flac")
    cmds = logged_commands(caplog)
    assert len(cmds) == 4
    for cmd in cmds:
        assert cmd[:4] == ["sox", "-V1", src, "--comment="]
    assert [c[c.index("trim") - 1 :] for c in cmds] == [
        [str(bundle / "1 - Opening.flac"), "trim", "00:00:00.000000", "=00:03:28.133333"],
        [str(bundle / "2 - Second Movement.flac"), "trim", "00:03:28.133333", "=00:06:57.986667"],
        [str(bundle / "3 - Before  After.flac"), "trim", "00:06:57.986667", "=01:02:05.493333"],
        [str(bundle / "4 - Long Coda.flac"), "trim", "01:02:05.493333"],
    ]
    assert "--add-comment=ARTIST=Guest Artist" in cmds[3]
    assert "--add-comment=ISRC=GBAAA8800004" in cmds[3]
    assert "--add-comment=TITLE=Before / After" in cmds[2]

    messages = [r.getMessage() for r in caplog.records]
    assert messages[0] == "Processing sample_192k.cue"
    assert "  -> 1 - Opening.flac" in messages
    assert messages[-1] == "Done."
    assert not (album_dir / "deflacue").exists()


def test_dry_run_without_verbose_hides_commands(
    album_dir: Path, fake_sox: None, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="redeflacue")
    assert main([str(album_dir), "--dry-run"]) == 0
    assert logged_commands(caplog) == []
    assert "  -> 4 - Long Coda.flac" in caplog.text


def test_dry_run_dest_and_recursive(
    album_dir: Path, tmp_path: Path, fake_sox: None, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="redeflacue")
    dest = tmp_path / "library"

    # Without -r the album subdirectory is not searched.
    assert main([str(tmp_path), "--dry-run", "-d", str(dest)]) == 0
    assert logged_commands(caplog) == []

    caplog.clear()
    assert main([str(tmp_path), "--dry-run", "-r", "-d", str(dest)]) == 0
    cmds = logged_commands(caplog)
    assert len(cmds) == 4
    expected_bundle = dest.resolve() / album_dir.name / "Test Artist" / "1988 - Hi-Res Image"
    assert all(Path(c[c.index("trim") - 1]).parent == expected_bundle for c in cmds)
    assert not dest.exists()


def test_dry_run_encoding(
    fixtures_dir: Path, tmp_path: Path, fake_sox: None, caplog: pytest.LogCaptureFixture
) -> None:
    shutil.copy(fixtures_dir / "sample_windows1251.cue", tmp_path)
    (tmp_path / "image.flac").touch()
    caplog.set_level(logging.DEBUG, logger="redeflacue")

    assert main([str(tmp_path), "--dry-run", "-v", "-e", "windows-1251"]) == 0

    cmds = logged_commands(caplog)
    assert [Path(c[c.index("trim") - 1]).name for c in cmds] == [
        "1 - Первая песня.flac",
        "2 - Вторая  последняя.flac",
    ]
    assert "--add-comment=ARTIST=Исполнитель" in cmds[0]


def test_python_dash_m() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "redeflacue", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout.strip() == f"redeflacue {redeflacue.__version__}"


def sox_info(flag: str, path: Path) -> str:
    assert SOX is not None
    return subprocess.run(
        [SOX, "--i", flag, str(path)], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.mark.integration
@pytest.mark.skipif(SOX is None, reason="sox not on PATH")
@pytest.mark.parametrize("rate", [44100, 96000, 192000])
def test_split_real_flac(tmp_path: Path, rate: int) -> None:
    """Split a synthesized 24-bit FLAC and check every track has the cue length."""
    assert SOX is not None
    album = tmp_path / "album"
    album.mkdir()
    image = album / "image.flac"
    subprocess.run(
        [
            SOX,
            "-n",
            "-r",
            str(rate),
            "-b",
            "24",
            "-c",
            "2",
            str(image),
            "synth",
            "6",
            "sine",
            "440",
        ],
        check=True,
    )
    (album / "image.cue").write_text(
        'PERFORMER "Synth"\n'
        'TITLE "Sine"\n'
        'FILE "image.flac" WAVE\n'
        '  TRACK 01 AUDIO\n    TITLE "One"\n    INDEX 01 00:00:00\n'
        '  TRACK 02 AUDIO\n    TITLE "Two"\n    INDEX 01 00:02:00\n'
        '  TRACK 03 AUDIO\n    TITLE "Three/Last"\n    INDEX 01 00:04:30\n',
        encoding="utf-8",
    )

    assert main([str(album)]) == 0

    bundle = album / "deflacue" / "Synth" / "Sine"
    tracks = [bundle / "1 - One.flac", bundle / "2 - Two.flac", bundle / "3 - ThreeLast.flac"]
    durations = [float(sox_info("-D", t)) for t in tracks]
    assert durations == pytest.approx([2.0, 2.4, 1.6], abs=1e-3)
    assert {sox_info("-r", t) for t in tracks} == {str(rate)}
    assert "TITLE=Three/Last" in sox_info("-a", tracks[2])
