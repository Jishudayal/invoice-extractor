import shutil
from pathlib import Path

import pytest

from invoice_extractor import runner
from invoice_extractor.cli import main
from invoice_extractor.config import Settings


def _locate(name: str) -> Path | None:
    for base in (Path("data/batch1_1"), Path("batch1_1")):
        candidate = base / name
        if candidate.exists():
            return candidate
    return None


def test_run_returns_empty_for_dir_without_images(tmp_path):
    assert runner.run(tmp_path, offline=True, settings=Settings()) == []


def test_cli_returns_nonzero_when_no_images(tmp_path):
    assert main(["--input-dir", str(tmp_path), "--offline"]) == 1


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="requires the tesseract binary")
def test_run_processes_images_with_per_image_results(tmp_path):
    src = _locate("batch1-0331.jpg")
    if src is None:
        pytest.skip("sample image not available")
    shutil.copy(src, tmp_path / "batch1-0331.jpg")

    results = runner.run(tmp_path, offline=True, settings=Settings())

    assert len(results) == 1
    assert results[0].pipeline == "rules"
    assert results[0].error is None
    assert results[0].fields.invoice_number == "94138597"


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="requires the tesseract binary")
def test_cli_returns_zero_on_successful_run(tmp_path):
    src = _locate("batch1-0331.jpg")
    if src is None:
        pytest.skip("sample image not available")
    shutil.copy(src, tmp_path / "batch1-0331.jpg")

    assert main(["--input-dir", str(tmp_path), "--offline"]) == 0
