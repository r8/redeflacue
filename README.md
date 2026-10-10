# redeflacue

Split CUE + FLAC album images into tracks, correctly at any sample rate.

[deflacue](https://github.com/idlesign/deflacue) assumes every image is 44.1 kHz. On a 24/192
FLAC that turns a track of about 3:28 into **0:47**, and the last track soaks up the rest of the
disc. redeflacue keeps deflacue's cue parser and command line, and only changes how cut points
reach sox: as times (`trim 00:03:28.133333`) instead of sample counts (`trim 9178680s`).

## What it does

deflacue's parser turns cue positions (`MM:SS:FF`) into sample offsets using a hardcoded
`rate = 44100`, then passes them to `sox trim {n}s`. sox reads `{n}s` at the *input file's*
rate, so on hi-res sources every cut lands at `44100 / actual_rate` of where it should be
(×0.46 at 96 kHz, ×0.23 at 192 kHz). redeflacue converts those offsets back to exact
seconds and gives sox wall-clock times, which sox maps onto whatever rate the file really has.
Everything else works like deflacue: same flags, output layout and tag mapping. The name is a
pun: "re-deflacue", or "redo deflacue".

## Why not just patch deflacue?

That would be the better long-term fix, and an upstream PR is welcome, but none has landed yet.
In the meantime redeflacue is a drop-in alternative with the same CLI. It installs next to
deflacue (it depends on it), so you can switch per album.

## Install

```sh
uv tool install redeflacue
# or
pipx install redeflacue
```

redeflacue calls the `sox` binary, just like deflacue:

```sh
sudo apt install sox libsox-fmt-all   # Debian / Ubuntu
brew install sox                      # macOS
```

## Usage

The flags mirror deflacue's:

```sh
# Split every .cue in a directory; output goes to ./deflacue/ next to each cue.
redeflacue /home/me/cues_to_process/

# Cue sheets in windows-1251, recurse into subdirectories, write into a library.
redeflacue -e windows-1251 -r -d /mnt/library/ /home/me/cues_to_process/

# Show what would run, including the full sox commands.
redeflacue --dry-run -v /home/me/cues_to_process/
```

| Flag | Meaning |
| --- | --- |
| `-d, --dest DIR` | Output root (default: `deflacue/` next to each cue) |
| `-e, --encoding ENC` | Encoding of the .cue file, e.g. `windows-1251` |
| `-r, --recursive` | Recurse into subdirectories |
| `--dry-run` | Log what would be done without running sox |
| `-v, --verbose` | Also log every sox command |
| `--version` | Print the version and exit |

Tracks are written as `<dest>/<Performer>/<Date - Album>/<NN - Title>.flac`, with
`TRACKNUMBER`, `TITLE`, `ARTIST`, `ALBUM`, `GENRE`, `DATE`, `ISRC` and `DESCRIPTION` taken
from the cue sheet.

### The motivating case

A 24/192 Talk Talk rip with tracks of roughly 3:28 each, split with deflacue:

```text
$ deflacue "Talk Talk/"
1 - ....flac   0:47
2 - ....flac   0:46
3 - ....flac   0:48
4 - ....flac  12:48    <- the remainder of the image
```

The same directory with redeflacue:

```sh
$ redeflacue "Talk Talk/"
```

Every track comes out at the length given in the cue sheet.

## How it works

deflacue's `CueParser` stores each `INDEX 01` as 44.1 kHz samples:
`(mm * 60 + ss) * 44100 + ff * 588`. A CD frame is 1/75 s, and 44100 / 75 = 588 exactly, so
every such offset is a whole number of frames. Dividing by 44100 therefore gives the exact cue
time; nothing is lost in the conversion. redeflacue does that division and formats the result
as `HH:MM:SS.ssssss` for `sox trim <start> =<end>`.

Worked example for a track at `INDEX 01 03:28:10` in a 192 kHz file:

| | deflacue | redeflacue |
| --- | --- | --- |
| Position from parser | 208 × 44100 + 10 × 588 = 9,178,680 samples | same |
| Argument passed to sox | `trim 9178680s` | `trim 00:03:28.133333` |
| What sox does at 192 kHz | sample 9,178,680 = **47.81 s** | 208.1333 s × 192000 = sample 39,961,600 = **3:28.13** |

At 44.1 kHz both columns agree, which is why the bug only appears on hi-res images.

## Alternatives

redeflacue does one thing: deflacue's job, made correct at any sample rate. Depending on what
you need, one of these may suit you better:

| Tool | Notes |
| --- | --- |
| [mp3splt](https://mp3splt.sourceforge.net/) | Splits FLAC, MP3 and Ogg Vorbis by cue sheet. Mature, widely packaged. **The best choice for most people.** |
| [shntool](http://shnutils.freeshell.org/shntool/) (`shnsplit`) | Classic CUE splitter, but fails on WAVE_FORMAT_EXTENSIBLE (`0xFFFE`) headers, which hi-res and multichannel decodes commonly use. |
| [flacon](https://flacon.github.io/) | GUI. Handles many formats, encodings and output codecs. |
| cuetools + ffmpeg | `cuebreakpoints` with `ffmpeg -ss/-to`. Flexible, but you have to script it yourself. |
| [deflacue](https://github.com/idlesign/deflacue) | The original. Fine for 44.1 kHz images; redeflacue relies on its parser. |

## Development

```sh
git clone https://github.com/r8/redeflacue.git
cd redeflacue
uv sync                    # creates .venv with dev dependencies, from uv.lock
uv run pytest              # tests marked "integration" are skipped without sox
uv run ruff check
uv run ruff format --check
uv run mypy src
uvx pre-commit install     # ruff, ruff-format and mypy on every commit
uv run redeflacue --help   # run the local checkout
```

redeflacue also works as a library:

```python
from pathlib import Path
from deflacue.parser import CueParser
from redeflacue import build_sox_command, plan_extractions

cue = CueParser.from_file(fpath=Path("album.cue")).run()
for ex in plan_extractions(cue, Path("."), Path("out")):
    print(build_sox_command(ex.src, ex.dst, ex.start_s, ex.end_s, ex.tags))
```

## License and credits

BSD-3-Clause, see [LICENSE](LICENSE). The cue sheet parsing is
[deflacue](https://github.com/idlesign/deflacue)'s `CueParser`, by Igor Starikov (idlesign),
also BSD-3-Clause. redeflacue is a derivative tool and would not exist without it.
