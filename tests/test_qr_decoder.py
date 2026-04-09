from pathlib import Path

from imarisha_scan.qr import QrPayloadDecoder


def test_decode_payload_raises_when_input_missing(tmp_path: Path) -> None:
    decoder = QrPayloadDecoder()
    missing = tmp_path / "missing.jpg"

    try:
        decoder.decode_payload(missing)
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        assert True


def test_decode_payload_returns_none_when_backends_unavailable(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "sheet.jpg"
    image_path.write_text("not-an-image", encoding="utf-8")
    decoder = QrPayloadDecoder()

    monkeypatch.setattr(QrPayloadDecoder, "_decode_with_opencv", staticmethod(lambda p: None))
    monkeypatch.setattr(QrPayloadDecoder, "_decode_with_pyzbar", staticmethod(lambda p: None))

    assert decoder.decode_payload(image_path) is None
