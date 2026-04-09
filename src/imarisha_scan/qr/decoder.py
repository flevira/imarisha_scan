from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class QrDecodeResult:
    payload: str
    backend: str


class QrPayloadDecoder:
    """Decode QR payloads from scan images using available local backends."""

    def decode_payload(self, image_path: str | Path) -> QrDecodeResult | None:
        source = Path(image_path)
        if not source.exists():
            raise FileNotFoundError(f"Input image not found: {source}")

        opencv_payload = self._decode_with_opencv(source)
        if opencv_payload:
            return QrDecodeResult(payload=opencv_payload, backend="opencv")

        pyzbar_payload = self._decode_with_pyzbar(source)
        if pyzbar_payload:
            return QrDecodeResult(payload=pyzbar_payload, backend="pyzbar")

        return None

    @staticmethod
    def _decode_with_opencv(image_path: Path) -> str | None:
        try:
            import cv2  # type: ignore[import-not-found]
        except ModuleNotFoundError:
            return None

        image = cv2.imread(str(image_path))
        if image is None:
            return None

        detector = cv2.QRCodeDetector()
        decoded, _, _ = detector.detectAndDecode(image)
        normalized = QrPayloadDecoder._normalize_payload(decoded)
        if normalized:
            return normalized

        if not hasattr(detector, "detectAndDecodeMulti"):
            return None

        multi_result = detector.detectAndDecodeMulti(image)
        if not multi_result:
            return None

        # OpenCV bindings may vary by version; first two values are retval + decoded_info.
        retval = bool(multi_result[0]) if len(multi_result) > 0 else False
        decoded_info = multi_result[1] if len(multi_result) > 1 else []
        if not retval:
            return None

        for payload in decoded_info:
            normalized = QrPayloadDecoder._normalize_payload(payload)
            if normalized:
                return normalized
        return None

    @staticmethod
    def _decode_with_pyzbar(image_path: Path) -> str | None:
        try:
            from PIL import Image  # type: ignore[import-not-found]
            from pyzbar.pyzbar import decode  # type: ignore[import-not-found]
        except ModuleNotFoundError:
            return None

        try:
            with Image.open(image_path) as img:
                symbols = decode(img)
        except OSError:
            return None

        for symbol in symbols:
            raw = symbol.data.decode("utf-8", errors="ignore")
            normalized = QrPayloadDecoder._normalize_payload(raw)
            if normalized:
                return normalized
        return None

    @staticmethod
    def _normalize_payload(payload: object) -> str:
        if payload is None:
            return ""
        text = str(payload).strip()
        return text
