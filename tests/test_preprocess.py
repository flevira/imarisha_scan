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


def test_preprocess_pdf_converts_first_page(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "scan.pdf"
    src.write_bytes(b"%PDF-1.4 fake")

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool):  # noqa: ANN001
        output_prefix = Path(cmd[-1])
        output_prefix.with_suffix(".png").write_bytes(b"fake-png")
        return None

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/pdftoppm" if name == "pdftoppm" else None)
    monkeypatch.setattr("subprocess.run", fake_run)

    pipeline = PreprocessPipeline()
    result = pipeline.preprocess_file(src, tmp_path / "processing", dpi=300)

    assert result.output_path.exists()
    assert result.output_path.suffix == ".png"
    assert result.output_path.name == "pre_scan.png"
    assert "pdf_to_png" in result.actions


def test_preprocess_pdf_requires_pdftoppm(tmp_path: Path) -> None:
    src = tmp_path / "scan.pdf"
    src.write_bytes(b"%PDF-1.4 fake")

    pipeline = PreprocessPipeline()
    with pytest.raises(RuntimeError, match="pdftoppm"):
        pipeline.preprocess_file(src, tmp_path / "processing", dpi=300)
