from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class QrDecodeResult:
    payload: str
    backend: str


class QrPayloadDecoder:
    """Decode QR payloads from scan images using optional runtime backends."""

    def decode_payload(self, image_path: str | Path) -> QrDecodeResult | None:
        source = Path(image_path)
        if not source.exists():
            raise FileNotFoundError(f"Input image not found: {source}")

        zxingcpp_payload = self._decode_with_zxingcpp(source)
        if zxingcpp_payload:
            return QrDecodeResult(payload=zxingcpp_payload, backend="zxingcpp")

        pyzxing_payload = self._decode_with_pyzxing(source)
        if pyzxing_payload:
            return QrDecodeResult(payload=pyzxing_payload, backend="pyzxing")

        zbarimg_payload = self._decode_with_zbarimg(source)
        if zbarimg_payload:
            return QrDecodeResult(payload=zbarimg_payload, backend="zbarimg")

        return None

    @staticmethod
    def _decode_with_zxingcpp(image_path: Path) -> str | None:
        try:
            import zxingcpp  # type: ignore[import-not-found]
        except ModuleNotFoundError:
            return None

        try:
            symbols = zxingcpp.read_barcodes(str(image_path))
        except Exception:
            return None

        for symbol in symbols or []:
            text = getattr(symbol, "text", "")
            normalized = QrPayloadDecoder._normalize_payload(text)
            if normalized:
                return normalized
        return None

    @staticmethod
    def _decode_with_pyzxing(image_path: Path) -> str | None:
        try:
            from pyzxing import BarCodeReader  # type: ignore[import-not-found]
        except ModuleNotFoundError:
            return None

        try:
            symbols = BarCodeReader().decode(str(image_path)) or []
        except Exception:
            return None

        for symbol in symbols:
            if not isinstance(symbol, dict):
                continue
            normalized = QrPayloadDecoder._normalize_payload(symbol.get("parsed"))
            if normalized:
                return normalized
            normalized = QrPayloadDecoder._normalize_payload(symbol.get("raw"))
            if normalized:
                return normalized
        return None

    @staticmethod
    def _decode_with_zbarimg(image_path: Path) -> str | None:
        try:
            result = subprocess.run(
                ["zbarimg", "--quiet", "--raw", str(image_path)],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return None

        if result.returncode != 0:
            return None

        for line in result.stdout.splitlines():
            normalized = QrPayloadDecoder._normalize_payload(line)
            if normalized:
                return normalized
        return None

    @staticmethod
    def _normalize_payload(payload: object) -> str:
        if payload is None:
            return ""
        return str(payload).strip()
