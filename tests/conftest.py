from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def album_dir(tmp_path: Path) -> Path:
    album = tmp_path / "Hi-Res Image"
    album.mkdir()
    shutil.copy(FIXTURES / "sample_192k.cue", album)
    (album / "album_192k.flac").touch()
    return album
