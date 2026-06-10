"""Download the exact invoice slice used by this project from Kaggle.

Fetches ``batch1-0331.jpg`` .. ``batch1-0381.jpg`` (the range named in the brief)
from the public dataset and places them in ``data/batch1_1/``. Re-running is
safe: files already present are skipped.

Credentials: set ``KAGGLE_USERNAME`` / ``KAGGLE_KEY`` (in the environment or in a
local ``.env``), or place ``kaggle.json`` at ``~/.kaggle/kaggle.json``.

Usage:
    pip install -e ".[data]"
    python scripts/download_invoices.py
"""

from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

DATASET = "osamahosamabdellatif/high-quality-invoice-images-for-ocr"
# Location of the working slice inside the dataset archive.
DATASET_DIR = "batch_1/batch_1/batch1_1"
FIRST, LAST = 331, 381  # inclusive => 51 files (the brief says 50; see README)
DEST = Path("data/batch1_1")


def expected_filenames() -> list[str]:
    return [f"batch1-{n:04d}.jpg" for n in range(FIRST, LAST + 1)]


def load_kaggle_credentials_from_env_file(path: Path = Path(".env")) -> None:
    """Populate KAGGLE_* vars from a local .env so creds can live alongside the
    Azure ones. The kaggle library still also reads ~/.kaggle/kaggle.json."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]  # strip matching surrounding quotes
        if key in {"KAGGLE_USERNAME", "KAGGLE_KEY"} and key not in os.environ:
            os.environ[key] = value


def _fetch_one(api, name: str) -> bool:
    """Download a single image into DEST, flattening any compressed delivery."""
    target = DEST / name
    api.dataset_download_file(DATASET, f"{DATASET_DIR}/{name}", path=str(DEST), quiet=True)
    if target.exists():
        return True
    # Kaggle sometimes returns the file compressed; unpack and flatten if so.
    for archive in DEST.glob("*.zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(DEST)
        archive.unlink()
    if not target.exists():
        found = next((p for p in DEST.rglob(name) if p.is_file()), None)
        if found is not None:
            found.replace(target)
    return target.exists()


def main() -> int:
    load_kaggle_credentials_from_env_file()

    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError:
        print('The "kaggle" package is required: pip install -e ".[data]"', file=sys.stderr)
        return 1
    except SystemExit:
        # kaggle 1.8.x authenticates at import time and exits when creds are missing.
        print("Kaggle credentials required to download the dataset.", file=sys.stderr)
        print("Set KAGGLE_USERNAME / KAGGLE_KEY or add ~/.kaggle/kaggle.json.", file=sys.stderr)
        return 1

    api = KaggleApi()
    try:
        api.authenticate()
    except Exception as exc:
        print(f"Kaggle authentication failed: {exc}", file=sys.stderr)
        print("Set KAGGLE_USERNAME / KAGGLE_KEY, or add ~/.kaggle/kaggle.json.", file=sys.stderr)
        return 1

    DEST.mkdir(parents=True, exist_ok=True)
    downloaded = skipped = failed = 0

    for name in expected_filenames():
        if (DEST / name).exists():
            skipped += 1
            continue
        try:
            ok = _fetch_one(api, name)
        except Exception as exc:
            print(f"  failed: {name} ({exc})", file=sys.stderr)
            failed += 1
            continue
        if ok:
            downloaded += 1
        else:
            print(f"  missing after download: {name}", file=sys.stderr)
            failed += 1

    expected = LAST - FIRST + 1
    present = sum((DEST / n).exists() for n in expected_filenames())
    print(f"downloaded={downloaded} skipped={skipped} failed={failed}")
    print(f"present {present}/{expected} in {DEST}/")

    if present != expected:
        print("ERROR: incomplete invoice slice — see messages above.", file=sys.stderr)
        return 1
    print("OK: complete invoice slice ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
