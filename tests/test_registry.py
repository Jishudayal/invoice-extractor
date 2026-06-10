from pathlib import Path

import pytest

from invoice_extractor import pipelines
from invoice_extractor.config import Settings
from invoice_extractor.models import InvoiceFields, PipelineResult


class _DummyPipeline:
    name = "dummy"

    def extract(self, image_path: Path) -> PipelineResult:
        return PipelineResult(file_name=image_path.name, pipeline=self.name, fields=InvoiceFields())


def test_register_build_and_available():
    pipelines.register("dummy", lambda settings: _DummyPipeline())
    try:
        assert "dummy" in pipelines.available()
        built = pipelines.build("dummy", Settings())
        assert built.name == "dummy"
        assert built.extract(Path("some/dir/batch1-0331.jpg")).file_name == "batch1-0331.jpg"
    finally:
        pipelines._FACTORIES.pop("dummy", None)


def test_building_unknown_pipeline_raises():
    with pytest.raises(KeyError):
        pipelines.build("does-not-exist", Settings())


def test_load_builtin_pipelines_registers_rules():
    # No OCR/binary needed — this only exercises import-time registration.
    pipelines.load_builtin_pipelines()
    assert "rules" in pipelines.available()
