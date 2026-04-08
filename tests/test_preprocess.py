from pathlib import Path

import pytest

from imarisha_scan.preprocess import PreprocessConfig, PreprocessPipeline


def test_assess_quality_thresholds() -> None:
    pipeline = PreprocessPipeline(PreprocessConfig(min_dpi=200, preferred_dpi=300))

    assert pipeline.assess_quality(150).status == "reject"
    assert pipeline.assess_quality(250).status == "warn"
    assert pipeline.assess_quality(300).status == "pass"


def test_preprocess_file_creates_processed_copy(tmp_path: Path) -> None:
    src = tmp_path / "scan.jpg"
    src.write_bytes(b"fake-image-data")

    pipeline = PreprocessPipeline()
    result = pipeline.preprocess_file(src, tmp_path / "processing", dpi=300)

    assert result.output_path.exists()
    assert result.output_path.name == "pre_scan.jpg"
    assert "auto_rotate" in result.actions
    assert "deskew" in result.actions


def test_preprocess_rejects_low_dpi(tmp_path: Path) -> None:
    src = tmp_path / "scan.jpg"
    src.write_bytes(b"fake-image-data")

    pipeline = PreprocessPipeline(PreprocessConfig(min_dpi=200))
    with pytest.raises(ValueError):
        pipeline.preprocess_file(src, tmp_path / "processing", dpi=199)
