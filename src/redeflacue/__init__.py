"""redeflacue: deflacue-compatible CUE splitter that is correct on hi-res FLAC."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("redeflacue")
except PackageNotFoundError:  # pragma: no cover - running from an uninstalled tree
    __version__ = "0.0.0+unknown"

from redeflacue.cli import main
from redeflacue.processor import Extraction, plan_extractions
from redeflacue.splitter import build_sox_command

__all__ = ["Extraction", "__version__", "build_sox_command", "main", "plan_extractions"]
