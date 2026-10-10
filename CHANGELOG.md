# Changelog

## [Unreleased]

## [0.1.0] - 2026-10-10

### Added

- deflacue-compatible CLI (`redeflacue`, `python -m redeflacue`) with these flags:
  `-d/--dest`, `-e/--encoding`, `-r/--recursive`, `--dry-run`, `-v/--verbose`; plus
  `--version`.
- Library API: `plan_extractions()`, `build_sox_command()`, `Extraction`.

### Fixed

- Track boundaries on non-44.1 kHz FLAC images. Cut points are passed to SoX as times instead of
  44.1 kHz sample counts.

[Unreleased]: https://github.com/r8/redeflacue/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/r8/redeflacue/releases/tag/v0.1.0
