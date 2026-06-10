import shutil
from pathlib import Path

import pytest

from invoice_extractor import cli, runner
from invoice_extractor.cli import main
from invoice_extractor.config import Settings
from invoice_extractor.models import InvoiceFields, PipelineResult
from invoice_extractor.runner import select_pipeline_names

_ENABLED = Settings(
    _env_file=None,
    azure_openai_endpoint="https://example.openai.azure.com/",
    azure_openai_api_key="key",
    azure_openai_deployment_name="gpt-4o",
)
_ALL_ENABLED = _ENABLED.model_copy(
    update={
        "azure_di_endpoint": "https://example.cognitiveservices.azure.com/",
        "azure_di_key": "k",
    }
)
_DISABLED = Settings(_env_file=None)


def _locate(name: str) -> Path | None:
    for base in (Path("data/batch1_1"), Path("batch1_1")):
        candidate = base / name
        if candidate.exists():
            return candidate
    return None


def test_select_pipelines_offline_is_rules_only():
    assert select_pipeline_names(offline=True, settings=_ENABLED) == ["rules"]


def test_select_pipelines_adds_llm_when_enabled_and_online():
    assert select_pipeline_names(offline=False, settings=_ENABLED) == ["rules", "llm"]


def test_select_pipelines_rules_only_when_llm_not_configured():
    assert select_pipeline_names(offline=False, settings=_DISABLED) == ["rules"]


def test_select_pipelines_azure_is_opt_in():
    # Configured DI alone does not select azure — it needs the explicit flag.
    assert select_pipeline_names(offline=False, settings=_ALL_ENABLED) == ["rules", "llm"]
    assert select_pipeline_names(
        offline=False, settings=_ALL_ENABLED, include_azure=True
    ) == ["rules", "llm", "azure"]


def test_select_pipelines_azure_still_needs_credentials():
    # The flag without DI creds does not select azure.
    assert select_pipeline_names(offline=False, settings=_ENABLED, include_azure=True) == [
        "rules",
        "llm",
    ]


def test_cli_exits_nonzero_when_requested_pipeline_missing(tmp_path, monkeypatch):
    # LLM is configured + online (so it's requested), but the run produced only
    # rules results — the missing comparison must not pass as success.
    monkeypatch.setattr(cli, "load_settings", lambda: _ENABLED)
    only_rules = PipelineResult(
        file_name="f.jpg", pipeline="rules", fields=InvoiceFields(invoice_number="1")
    )
    monkeypatch.setattr(cli.runner, "run", lambda *a, **k: [only_rules])

    assert main(["--input-dir", str(tmp_path), "--output-dir", str(tmp_path / "out")]) == 1


def test_cli_writes_comparison_trio_for_two_pipelines(tmp_path, monkeypatch):
    # Pin settings to llm-only so the requested set matches the mocked results
    # regardless of what's in the local .env.
    monkeypatch.setattr(cli, "load_settings", lambda: _ENABLED)
    fields = InvoiceFields(invoice_number="94138597")
    fake_results = [
        PipelineResult(file_name="f.jpg", pipeline="rules", fields=fields),
        PipelineResult(file_name="f.jpg", pipeline="llm", fields=fields),
    ]
    monkeypatch.setattr(cli.runner, "run", lambda *a, **k: fake_results)
    out_dir = tmp_path / "out"

    assert main(["--input-dir", str(tmp_path), "--output-dir", str(out_dir)]) == 0
    assert (out_dir / "output.csv").exists()
    assert (out_dir / "comparison_report.csv").exists()
    assert (out_dir / "summary.csv").exists()


def test_cli_single_pipeline_writes_only_output(tmp_path, monkeypatch):
    only_rules = PipelineResult(
        file_name="f.jpg", pipeline="rules", fields=InvoiceFields(invoice_number="1")
    )
    monkeypatch.setattr(cli.runner, "run", lambda *a, **k: [only_rules])
    out_dir = tmp_path / "out"

    assert main(["--input-dir", str(tmp_path), "--output-dir", str(out_dir), "--offline"]) == 0
    assert (out_dir / "output.csv").exists()
    assert not (out_dir / "comparison_report.csv").exists()


def test_run_returns_empty_for_dir_without_images(tmp_path):
    assert runner.run(tmp_path, offline=True, settings=Settings(_env_file=None)) == []


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
