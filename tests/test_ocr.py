from pathlib import Path

import pytest

from imarisha_scan.ocr import LocalTesseractEngine


def test_tesseract_engine_missing_input_file_raises(tmp_path: Path) -> None:
    engine = LocalTesseractEngine()
    with pytest.raises(FileNotFoundError):
        engine.extract_text(tmp_path / "missing.png")


def test_tesseract_engine_uses_env_binary_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_bin = tmp_path / "tesseract-custom"
    fake_bin.write_text("", encoding="utf-8")

    monkeypatch.setenv("IMARISHA_TESSERACT_BIN", str(fake_bin))
    engine = LocalTesseractEngine()

    assert engine.is_available()


def test_tesseract_engine_prefers_explicit_binary_over_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_bin = tmp_path / "tesseract-env"
    env_bin.write_text("", encoding="utf-8")
    explicit_bin = tmp_path / "tesseract-explicit"
    explicit_bin.write_text("", encoding="utf-8")

    monkeypatch.setenv("IMARISHA_TESSERACT_BIN", str(env_bin))
    engine = LocalTesseractEngine(binary=str(explicit_bin))

    assert engine.is_available()
