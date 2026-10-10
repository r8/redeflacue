# redeflacue

`redeflacue` splits CUE + FLAC album images without assuming a 44.1 kHz sample rate.

It uses [deflacue](https://github.com/idlesign/deflacue) to parse cue sheets and keeps its
command-line interface, output layout, and tag mapping. The difference is in the arguments sent
to SoX: cue positions are passed as times instead of sample counts. This avoids misplaced track
boundaries on 96 kHz, 192 kHz, and other non-44.1 kHz files.

## Install

Install the package with `uv` or `pipx`:

```sh
uv tool install redeflacue
# or
pipx install redeflacue
```

SoX is also required:

```sh
sudo apt install sox libsox-fmt-all  # Debian / Ubuntu
brew install sox                     # macOS
```

## Usage

```sh
# Split .cue files in a directory.
redeflacue /home/me/cues/

# Read Windows-1251 cue sheets recursively and choose an output directory.
redeflacue -e windows-1251 -r -d /mnt/library/ /home/me/cues/

# Print the SoX commands without running them.
redeflacue --dry-run -v /home/me/cues/
```

| Flag | Description |
| --- | --- |
| `-d, --dest DIR` | Output root; defaults to `deflacue/` beside each cue sheet |
| `-e, --encoding ENC` | Cue-sheet encoding, such as `windows-1251` |
| `-r, --recursive` | Search subdirectories |
| `--dry-run` | Print planned work without running SoX |
| `-v, --verbose` | Print each SoX command |
| `--version` | Print the version |

Tracks are written to:

```text
<destination>/<performer>/<date - album>/<track number - title>.flac
```

The cue sheet supplies the track number, title, artist, album, genre, date, ISRC, and
description tags.

## Sample-rate fix

deflacue stores cue positions as 44.1 kHz sample offsets and passes them to `sox trim` as sample
counts. SoX interprets those counts using the input file's actual sample rate, so boundaries are
wrong when that rate is not 44.1 kHz.

A cue position is based on 75 frames per second. Because deflacue uses 588 samples per cue frame
(`44100 / 75`), dividing its stored offset by 44100 recovers the cue time. redeflacue sends that
time to SoX as `HH:MM:SS.ssssss`, which works independently of the input rate.

## Python API

```python
from pathlib import Path

from deflacue.parser import CueParser
from redeflacue import build_sox_command, plan_extractions

cue = CueParser.from_file(fpath=Path("album.cue")).run()
for extraction in plan_extractions(cue, Path("."), Path("out")):
    print(
        build_sox_command(
            extraction.src,
            extraction.dst,
            extraction.start_s,
            extraction.end_s,
            extraction.tags,
        )
    )
```

## Development

```sh
git clone https://github.com/r8/redeflacue.git
cd redeflacue
uv sync
uv run pytest
uv run ruff check
uv run ruff format --check
uv run mypy src
```

Integration tests are skipped when SoX is not installed.

## License

BSD-3-Clause. Cue-sheet parsing is provided by Igor Starikov's BSD-licensed
[deflacue](https://github.com/idlesign/deflacue).
