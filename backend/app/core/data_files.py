"""
app/core/data_files.py
=======================
Shared helpers for reading data files safely.

Key guarantee: a Git LFS pointer file is detected BEFORE pandas ever sees it.
pandas.read_csv() does NOT raise on an LFS pointer — it silently parses it as
a 2-row, 1-column DataFrame, producing wrong results with no error.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# First 47 bytes of every Git LFS pointer file
LFS_MAGIC = b"version https://git-lfs.github.com/spec/v1"

# Columns that must be present in holdout_manifest.csv
MANIFEST_REQUIRED_COLS = {"split", "rows"}


def assert_real_file(path: Path) -> None:
    """
    Raise if *path* is a Git LFS pointer rather than real content.

    Raises:
        FileNotFoundError  — path does not exist
        RuntimeError       — path is an LFS pointer (132-byte stub)
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist")
    head = path.open("rb").read(len(LFS_MAGIC))
    if head == LFS_MAGIC:
        raise RuntimeError(
            f"{path} is a Git LFS pointer, not real data "
            f"({path.stat().st_size} bytes). "
            f"Run: git lfs install && git lfs pull"
        )


def resolve_actuals_dir() -> Path:
    """
    Return the actuals_real directory, trying multiple candidate paths so the
    function works regardless of the process working directory.
    """
    from app.core.config import get_settings
    settings = get_settings()

    candidates = [
        Path(settings.actuals_dir),
        Path(settings.raw_data_dir).parent / "actuals_real",
        Path(__file__).resolve().parent.parent.parent / "data" / "actuals_real",
    ]
    for p in candidates:
        if p.exists():
            return p
    # Return the settings value even if it doesn't exist — callers handle that
    return Path(settings.actuals_dir)
