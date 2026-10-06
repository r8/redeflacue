"""Command-line interface (argument surface mirrors deflacue)."""

from __future__ import annotations

import argparse
import logging
import shutil
from collections.abc import Sequence
from pathlib import Path

from redeflacue import __version__
from redeflacue.processor import iter_cue_files, process_cue

LOGGER = logging.getLogger("redeflacue")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="redeflacue",
        description="deflacue-compatible CLI that splits high-res FLAC "
        "correctly (24-bit, 96/192 kHz) by using time-based "
        "sox trim instead of 44.1 kHz-assumed sample counts.",
    )
    ap.add_argument("source", type=Path, help="Directory containing .cue files")
    ap.add_argument(
        "-d",
        "--dest",
        type=Path,
        default=None,
        help="Output root (default: ./deflacue next to each cue)",
    )
    ap.add_argument(
        "-e", "--encoding", default=None, help="Encoding of the .cue file (e.g. windows-1251)"
    )
    ap.add_argument("-r", "--recursive", action="store_true", help="Recurse into subdirectories")
    ap.add_argument("--dry-run", action="store_true", help="Log commands without executing them")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if shutil.which("sox") is None:
        LOGGER.error("sox not found. Install: sudo apt install sox libsox-fmt-all")
        return 1

    src_root = args.source.resolve()
    if not src_root.exists():
        LOGGER.error("Path %s does not exist", src_root)
        return 1

    for cue in iter_cue_files(src_root, args.recursive):
        target_root = (
            args.dest.resolve() / cue.parent.name if args.dest else cue.parent / "deflacue"
        )
        if not args.dry_run:
            target_root.mkdir(parents=True, exist_ok=True)
        process_cue(cue, target_root, args.encoding, args.dry_run)

    LOGGER.info("Done.")
    return 0
