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

    monkeypatch.setattr(QrPayloadDecoder, "_decode_with_zxingcpp", staticmethod(lambda p: None))
    monkeypatch.setattr(QrPayloadDecoder, "_decode_with_pyzxing", staticmethod(lambda p: None))
    monkeypatch.setattr(QrPayloadDecoder, "_decode_with_zbarimg", staticmethod(lambda p: None))

    assert decoder.decode_payload(image_path) is None


def test_decode_payload_uses_runtime_backends_in_order(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "sheet.jpg"
    image_path.write_text("not-an-image", encoding="utf-8")
    decoder = QrPayloadDecoder()
    calls: list[str] = []

    def _zxingcpp(_path: Path) -> str | None:
        calls.append("zxingcpp")
        return None

    def _pyzxing(_path: Path) -> str | None:
        calls.append("pyzxing")
        return "type=EXAM;studentId=82;examId=1756"

    monkeypatch.setattr(QrPayloadDecoder, "_decode_with_zxingcpp", staticmethod(_zxingcpp))
    monkeypatch.setattr(QrPayloadDecoder, "_decode_with_pyzxing", staticmethod(_pyzxing))
    monkeypatch.setattr(
        QrPayloadDecoder,
        "_decode_with_zbarimg",
        staticmethod(lambda p: (_ for _ in ()).throw(AssertionError("zbarimg should not run"))),
    )

    result = decoder.decode_payload(image_path)

    assert result is not None
    assert result.payload == "type=EXAM;studentId=82;examId=1756"
    assert result.backend == "pyzxing"
    assert calls == ["zxingcpp", "pyzxing"]
