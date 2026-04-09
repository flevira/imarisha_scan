from __future__ import annotations

import os
import shutil
import subprocess
import sys
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

    @staticmethod
    def _pdftoppm_candidates() -> list[str]:
        configured = (os.getenv("IMARISHA_PDFTOPPM_BIN", "")).strip()
        candidates: list[str] = []
        if configured:
            candidates.append(configured)

        candidates.append("pdftoppm")

        if sys.platform == "darwin":
            executable = Path(sys.executable).resolve()
            resources_bin = executable.parent.parent / "Resources" / "poppler" / "bin" / "pdftoppm"
            candidates.extend(
                [
                    str(resources_bin),
                    "/opt/homebrew/bin/pdftoppm",
                    "/usr/local/bin/pdftoppm",
                ]
            )
        return candidates

    def _resolve_pdftoppm(self) -> str | None:
        for candidate in self._pdftoppm_candidates():
            if not candidate:
                continue
            candidate_path = Path(candidate)
            if candidate_path.is_file():
                return str(candidate_path)
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return None

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

        actions = []
        if src.suffix.lower() == ".pdf":
            dest = self._pdf_first_page_to_png(src, output_root)
            actions.append("pdf_to_png")
        else:
            processed_name = f"pre_{src.name}"
            dest = output_root / processed_name
            shutil.copy2(src, dest)
            actions.append("copy")

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

    def _pdf_first_page_to_png(self, src: Path, output_root: Path) -> Path:
        pdftoppm = self._resolve_pdftoppm()
        output_prefix = output_root / f"pre_{src.stem}"
        rendered = output_prefix.with_suffix(".png")

        if pdftoppm is not None:
            run_env = None
            pdftoppm_path = Path(pdftoppm)
            bundled_lib_dir = pdftoppm_path.parent.parent / "lib"
            if bundled_lib_dir.is_dir() and sys.platform == "darwin":
                run_env = os.environ.copy()
                existing = run_env.get("DYLD_LIBRARY_PATH", "").strip()
                run_env["DYLD_LIBRARY_PATH"] = (
                    f"{bundled_lib_dir}:{existing}" if existing else str(bundled_lib_dir)
                )

            subprocess.run(
                [
                    pdftoppm,
                    "-f",
                    "1",
                    "-singlefile",
                    "-png",
                    str(src),
                    str(output_prefix),
                ],
                capture_output=True,
                text=True,
                check=True,
                env=run_env,
            )
        else:
            # macOS fallback for local setups that don't have Poppler installed.
            sips = shutil.which("sips")
            if sips is not None:
                subprocess.run(
                    [sips, "-s", "format", "png", str(src), "--out", str(rendered)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            else:
                raise RuntimeError(
                    "PDF OCR could not find a rasterizer. Install Poppler so 'pdftoppm' is on PATH, "
                    "or use macOS 'sips' for fallback conversion."
                )

        if not rendered.exists():
            raise RuntimeError(f"Failed to render PDF page to image: {rendered}")
        return rendered
