# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-10

### Added

- deflacue-compatible CLI (`redeflacue`, `python -m redeflacue`) with the same flags:
  `-d/--dest`, `-e/--encoding`, `-r/--recursive`, `--dry-run`, `-v/--verbose`; plus
  `--version`.
- Library API: `plan_extractions()`, `build_sox_command()`, `Extraction`.

### Fixed

- Track boundaries on hi-res (96/192 kHz) FLAC images. Cut points are passed to sox as
  times (`trim HH:MM:SS.ssssss =HH:MM:SS.ssssss`) instead of deflacue's 44.1 kHz sample
  counts, so splits are correct at any sample rate.

[Unreleased]: https://github.com/r8/redeflacue/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/r8/redeflacue/releases/tag/v0.1.0
