from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PreprocessConfig:
    min_dpi: int = 200
    preferred_dpi: int = 300
    auto_rotate: bool = True
    deskew: bool = True
    denoise: bool = True
    binarize: bool = True
    preserve_original: bool = True


@dataclass(frozen=True)
class QualityAssessment:
    dpi: int | None
    status: str  # reject | warn | pass
    reason: str


@dataclass(frozen=True)
class PreprocessResult:
    input_path: Path
    output_path: Path
    actions: tuple[str, ...]
    quality: QualityAssessment


class PreprocessPipeline:
    def __init__(self, config: PreprocessConfig | None = None) -> None:
        self.config = config or PreprocessConfig()

    def assess_quality(self, dpi: int | None) -> QualityAssessment:
        if dpi is None:
            return QualityAssessment(dpi=dpi, status="warn", reason="DPI metadata missing")
        if dpi < self.config.min_dpi:
            return QualityAssessment(dpi=dpi, status="reject", reason=f"DPI below minimum ({self.config.min_dpi})")
        if dpi < self.config.preferred_dpi:
            return QualityAssessment(dpi=dpi, status="warn", reason=f"DPI below preferred ({self.config.preferred_dpi})")
        return QualityAssessment(dpi=dpi, status="pass", reason="DPI meets preferred threshold")

    def preprocess_file(self, input_path: str | Path, output_dir: str | Path, dpi: int | None = None) -> PreprocessResult:
        src = Path(input_path)
        if not src.exists():
            raise FileNotFoundError(f"Input file not found: {src}")

        quality = self.assess_quality(dpi)
        if quality.status == "reject":
            raise ValueError(quality.reason)

        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)

        processed_name = f"pre_{src.name}"
        dest = output_root / processed_name

        actions = ["copy"]
        shutil.copy2(src, dest)

        # Placeholder transformation labels for visibility in pipeline orchestration.
        if self.config.auto_rotate:
            actions.append("auto_rotate")
        if self.config.deskew:
            actions.append("deskew")
        if self.config.denoise:
            actions.append("denoise")
        if self.config.binarize:
            actions.append("binarize")

        return PreprocessResult(
            input_path=src,
            output_path=dest,
            actions=tuple(actions),
            quality=quality,
        )
