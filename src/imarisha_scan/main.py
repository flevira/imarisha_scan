"""Entry point for the Imarisha Scan app."""

from __future__ import annotations

import os
import shutil
import tempfile
import csv
import io
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
import sys
from urllib.parse import quote

import importlib
import importlib.util


def _bootstrap_import_path() -> None:
    """Ensure local package imports resolve in bundled/script execution modes."""
    current_file = Path(__file__).resolve()
    search_roots = [current_file.parent, *current_file.parents]
    candidates: list[Path] = []
    for root in search_roots:
        candidates.extend((root, root / "src"))

    for candidate in candidates:
        package_dir = candidate / "imarisha_scan"
        if package_dir.is_dir() and (package_dir / "__init__.py").is_file():
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)
            return


_bootstrap_import_path()

try:
    from imarisha_scan.extract import AnswerSheetExtractor
    from imarisha_scan.export import CsvExporter
    from imarisha_scan.ingest import FolderLifecycleManager, IngestConfig
    from imarisha_scan.ocr import LocalTesseractEngine, OcrResultStore, OcrWorkflow
    from imarisha_scan.preprocess import PreprocessPipeline
except ModuleNotFoundError:
    from extract import AnswerSheetExtractor  # type: ignore[no-redef]
    from export import CsvExporter  # type: ignore[no-redef]
    from ingest import FolderLifecycleManager, IngestConfig  # type: ignore[no-redef]
    from ocr import LocalTesseractEngine, OcrResultStore, OcrWorkflow  # type: ignore[no-redef]
    from preprocess import PreprocessPipeline  # type: ignore[no-redef]

try:
    from imarisha_scan.ui import ReviewRecord, ReviewSession
except ModuleNotFoundError:
    try:
        from ui import ReviewRecord, ReviewSession  # type: ignore[no-redef]
    except ModuleNotFoundError:
        @dataclass(frozen=True)
        class ReviewRecord:
            user_id: str
            question_id: str
            test_id: str
            exam_id: str
            answer: str
            status: str = "pending"
            source_file: str = ""


        class ReviewSession:
            def __init__(self, rows: list[ReviewRecord]) -> None:
                self.rows = rows
                self.error_queue: list[ReviewRecord] = []

            def update_field(self, index: int, field_name: str, value: str) -> None:
                row = self.rows[index]
                self.rows[index] = replace(row, **{field_name: value})

            def approve(self, index: int) -> None:
                row = self.rows[index]
                self.rows[index] = replace(row, status="approved")

            def reject(self, index: int) -> None:
                row = replace(self.rows[index], status="rejected")
                self.rows[index] = row
                self.error_queue.append(row)

            @property
            def approved_count(self) -> int:
                return sum(1 for r in self.rows if r.status == "approved")

            @property
            def rejected_count(self) -> int:
                return sum(1 for r in self.rows if r.status == "rejected")


@dataclass(frozen=True)
class RuntimeConfig:
    host: str
    port: int
    web_mode: bool


def build_home_title() -> str:
    """Return the title used on the home screen."""
    return "Imarisha Scan"


def get_ingest_root_dir() -> Path:
    """Return the local folder used for uploaded scan files."""
    configured = os.getenv("IMARISHA_INGEST_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".imarisha_scan" / "runtime_data").resolve()


def normalize_upload_path(path_text: str) -> str:
    """Normalize a manually entered path from the upload text field."""
    trimmed = path_text.strip()
    if len(trimmed) >= 2:
        quote_pairs = (("'", "'"), ('"', '"'), ("“", "”"))
        for start_quote, end_quote in quote_pairs:
            if trimmed.startswith(start_quote) and trimmed.endswith(end_quote):
                return trimmed[1:-1].strip()
    return trimmed


def pick_default_scan_file(file_names: list[str], current_selection: str | None) -> str | None:
    """Return the queue selection to keep in the file selector."""
    if not file_names:
        return None
    if current_selection and current_selection in file_names:
        return current_selection
    return file_names[0]


def advance_selected_scan_to_ingestion(
    ingest_root: Path,
    selected_scan_name: str,
) -> tuple[Path | None, str]:
    """Advance selected queued scan into ingestion processing."""
    selected_name = selected_scan_name.strip()
    if not selected_name:
        return None, "Select a queued file first, then click Scan."

    ingest_config = IngestConfig(root_dir=ingest_root, min_batch_size=1, max_wait_seconds=0, stable_cycles=1)
    lifecycle = FolderLifecycleManager(ingest_config)
    lifecycle.ensure_directories()

    source = ingest_root / "scans" / selected_name
    if not source.exists() or not source.is_file():
        return None, f"Selected file is no longer available: {selected_name}"

    target = ingest_config.incoming_dir / source.name
    suffix_idx = 1
    while target.exists():
        target = ingest_config.incoming_dir / f"{source.stem}_{suffix_idx}{source.suffix}"
        suffix_idx += 1
    source.replace(target)

    if lifecycle.ready_for_batch():
        staged = lifecycle.stage_batch(limit=1)
        if staged:
            return staged[0], f"Ingestion started: {staged[0].name}"
    return target, f"Moved to ingestion queue: {target.name}"


def get_runtime_config() -> RuntimeConfig:
    """Resolve runtime mode from environment variables."""
    port = int(os.getenv("PORT", "8550"))
    web_mode = os.getenv("FLET_WEB", "0") == "1"
    return RuntimeConfig(host="0.0.0.0", port=port, web_mode=web_mode)


def should_fallback_to_web(exc: Exception) -> bool:
    msg = str(exc)
    return "CERTIFICATE_VERIFY_FAILED" in msg or "flet" in msg.lower()


def initialize_file_picker(ft_module, page) -> object | None:
    """Create and register the file picker when the current runtime supports it."""
    if not hasattr(ft_module, "FilePicker"):
        return None

    try:
        picker = ft_module.FilePicker()
    except Exception:
        return None

    services = getattr(page, "services", None)
    if isinstance(services, list):
        try:
            services.append(picker)
            return picker
        except Exception:
            return None

    overlay = getattr(page, "overlay", None)
    if isinstance(overlay, list):
        try:
            overlay.append(picker)
            return picker
        except Exception:
            return None

    return None


def _record_from_processing_file(file_path: Path) -> ReviewRecord:
    """Create a fallback review record when extraction artifacts are unavailable."""
    return ReviewRecord(
        user_id="",
        question_id="",
        test_id="",
        exam_id="",
        answer="",
        source_file=file_path.name,
    )


def _normalize_row_dict(raw: dict[str, object], source_file: str) -> ReviewRecord:
    return ReviewRecord(
        user_id=str(raw.get("user_id", "")).strip(),
        question_id=str(raw.get("question_id", "")).strip(),
        test_id=str(raw.get("test_id", "")).strip(),
        exam_id=str(raw.get("exam_id", "")).strip(),
        answer=str(raw.get("answer", "")).strip().upper(),
        status=str(raw.get("status", "pending")).strip() or "pending",
        source_file=source_file,
    )


def _load_rows_from_json_sidecar(file_path: Path) -> list[ReviewRecord]:
    sidecars = [file_path.with_suffix(".json"), file_path.with_suffix(".extracted.json")]
    for sidecar in sidecars:
        if not sidecar.exists() or not sidecar.is_file():
            continue
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(payload, dict):
            payload = payload.get("rows", [])
        if not isinstance(payload, list):
            continue
        rows = [item for item in payload if isinstance(item, dict)]
        if rows:
            return [_normalize_row_dict(item, file_path.name) for item in rows]
    return []


def _pick_existing_sidecar(file_path: Path, *suffixes: str) -> Path | None:
    for suffix in suffixes:
        sidecar = file_path.with_suffix(suffix)
        if sidecar.exists() and sidecar.is_file():
            return sidecar
    return None


def _candidate_processing_names(file_path: Path) -> list[str]:
    names = [file_path.name]
    match = re.match(r"^\d{14}_(.+)$", file_path.name)
    if match:
        names.append(match.group(1))
    return names


def _find_sidecar_for_processing_file(ingest_root: Path, file_path: Path, *suffixes: str) -> Path | None:
    candidate_dirs = [file_path.parent, ingest_root / "scans", ingest_root / "incoming"]
    for directory in candidate_dirs:
        for name in _candidate_processing_names(file_path):
            source = directory / name
            sidecar = _pick_existing_sidecar(source, *suffixes)
            if sidecar is not None:
                return sidecar
    return None


def _load_rows_from_text_sidecars(file_path: Path) -> list[ReviewRecord]:
    ocr_sidecar = _pick_existing_sidecar(file_path, ".ocr.txt", ".ocr")
    qr_sidecar = _pick_existing_sidecar(file_path, ".qr.txt", ".qr")
    answers_sidecar = _pick_existing_sidecar(file_path, ".answers.json", ".answers")
    if ocr_sidecar is None or qr_sidecar is None or answers_sidecar is None:
        return []
    try:
        ocr_text = ocr_sidecar.read_text(encoding="utf-8")
        qr_payload = qr_sidecar.read_text(encoding="utf-8").strip()
        answers = json.loads(answers_sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(answers, dict):
        return []
    normalized_answers = {str(k): str(v) for k, v in answers.items()}
    try:
        extracted_rows = AnswerSheetExtractor().extract_rows(ocr_text, qr_payload, normalized_answers)
    except ValueError:
        return []
    return [_normalize_row_dict(item, file_path.name) for item in extracted_rows]


def run_ocr_and_extract_for_processing_file(ingest_root: Path, file_path: Path) -> str:
    """Generate OCR/extraction sidecars for one staged processing file when possible."""
    if not file_path.exists() or not file_path.is_file():
        return "Processing file not found for OCR."

    ocr_sidecar = (
        _find_sidecar_for_processing_file(ingest_root, file_path, ".ocr.txt", ".ocr") or file_path.with_suffix(".ocr.txt")
    )
    qr_sidecar = (
        _find_sidecar_for_processing_file(ingest_root, file_path, ".qr.txt", ".qr") or file_path.with_suffix(".qr.txt")
    )
    answers_sidecar = _find_sidecar_for_processing_file(
        ingest_root,
        file_path,
        ".answers.json",
        ".answers",
    ) or file_path.with_suffix(".answers.json")
    extracted_sidecar = file_path.with_suffix(".extracted.json")

    ocr_text = ""
    if ocr_sidecar.exists() and ocr_sidecar.is_file():
        try:
            ocr_text = ocr_sidecar.read_text(encoding="utf-8")
        except OSError:
            ocr_text = ""

    if not ocr_text.strip():
        engine = LocalTesseractEngine()
        if not engine.is_available():
            return "OCR not run (Tesseract unavailable). Add .ocr/.qr/.answers or .ocr.txt/.qr.txt/.answers.json sidecars for extraction."

        artifacts_dir = ingest_root / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        workflow = OcrWorkflow(
            preprocess=PreprocessPipeline(),
            engine=engine,
            store=OcrResultStore(artifacts_dir / "ocr_results.sqlite3"),
        )
        try:
            record = workflow.process_file(
                job_id=file_path.stem,
                input_path=file_path,
                output_dir=artifacts_dir / "preprocess",
            )
        except Exception as exc:
            return f"OCR failed for {file_path.name}: {exc}"
        ocr_text = record.text
        ocr_sidecar.write_text(ocr_text, encoding="utf-8")

    if not (qr_sidecar.exists() and answers_sidecar.exists()):
        return "OCR generated. Awaiting QR/answers sidecars to build extracted rows."

    try:
        qr_payload = qr_sidecar.read_text(encoding="utf-8").strip()
        answers_payload = json.loads(answers_sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"OCR generated. Could not parse sidecars: {exc}"
    if not isinstance(answers_payload, dict):
        return "OCR generated. answers sidecar must be a JSON object."

    normalized_answers = {str(k): str(v) for k, v in answers_payload.items()}
    try:
        extracted_rows = AnswerSheetExtractor().extract_rows(ocr_text, qr_payload, normalized_answers)
    except ValueError as exc:
        return f"OCR generated. Extraction pending valid QR/answers: {exc}"

    extracted_sidecar.write_text(json.dumps(extracted_rows, indent=2), encoding="utf-8")
    return f"OCR and extraction sidecars generated for {file_path.name}."


def rows_from_processing_file(file_path: Path) -> list[ReviewRecord]:
    """Load extraction rows for one processing file from sidecar artifacts when available."""
    extracted_rows = _load_rows_from_json_sidecar(file_path)
    if extracted_rows:
        return extracted_rows
    extracted_rows = _load_rows_from_text_sidecars(file_path)
    if extracted_rows:
        return extracted_rows
    return [_record_from_processing_file(file_path)]


def load_review_session(ingest_root: Path) -> ReviewSession:
    """Load rows that are currently in the processing queue for manual review."""
    ingest_config = IngestConfig(root_dir=ingest_root)
    lifecycle = FolderLifecycleManager(ingest_config)
    lifecycle.ensure_directories()
    rows: list[ReviewRecord] = []
    allowed_suffixes = {s.lower() for s in ingest_config.allowed_suffixes}
    for item in sorted(ingest_config.processing_dir.iterdir()):
        if item.is_file() and item.suffix.lower() in allowed_suffixes:
            rows.extend(rows_from_processing_file(item))
    return ReviewSession(rows)


def completed_rows_for_export(session: ReviewSession) -> list[dict[str, str]]:
    """Return completed review rows (approved/rejected) serialized for CSV export."""
    return [
        {
            "user_id": row.user_id,
            "question_id": row.question_id,
            "test_id": row.test_id,
            "exam_id": row.exam_id,
            "answer": row.answer,
            "status": row.status,
        }
        for row in session.rows
        if row.status in {"approved", "rejected"}
    ]


def serialize_completed_rows_to_csv(rows: list[dict[str, str]]) -> str:
    """Serialize completed rows into CSV text for browser download."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["user_id", "question_id", "test_id", "exam_id", "answer", "status"])
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def run() -> None:
    """Start the Flet app in desktop or web mode."""
    import flet as ft

    spec = importlib.util.find_spec("certifi")
    if spec is not None:
        certifi = importlib.import_module("certifi")
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    config = get_runtime_config()

    def main(page: "ft.Page") -> None:
        page.title = build_home_title()
        page.window_width = 1200
        page.window_height = 760
        page.padding = 16

        session = load_review_session(ingest_root=get_ingest_root_dir())
        ingest_root = get_ingest_root_dir()
        scans_dir = ingest_root / "scans"
        storage_notice = ""
        try:
            scans_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            fallback_root = Path(tempfile.gettempdir()) / "imarisha_scan" / "runtime_data"
            scans_dir = fallback_root / "scans"
            scans_dir.mkdir(parents=True, exist_ok=True)
            storage_notice = f"Primary path not writable; using temporary storage at {scans_dir}."

        summary = ft.Text(size=14)
        review_status = ft.Text(size=13)
        upload_status = ft.Text(size=13)
        queued_file_selector = ft.Dropdown(
            label="Queued file",
            hint_text="Select a queued scan to start",
            expand=True,
            dense=True,
        )
        manual_path_input = ft.TextField(
            label="File or folder path",
            hint_text="Paste a full path to a PDF/image file or a folder containing scans",
            expand=True,
            dense=True,
        )
        grid_container = ft.Column(spacing=8, expand=True, scroll=ft.ScrollMode.AUTO)
        allowed_suffixes = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
        enable_file_picker = os.getenv("IMARISHA_ENABLE_FILE_PICKER", "0") == "1"
        if enable_file_picker:
            initialize_file_picker(ft, page)

        def refresh_upload_status(message: str | None = None) -> None:
            queue_files = sorted(p.name for p in scans_dir.iterdir() if p.is_file())
            file_count = len(queue_files)
            queued_file_selector.options = [ft.dropdown.Option(name) for name in queue_files]
            queued_file_selector.value = pick_default_scan_file(queue_files, queued_file_selector.value)
            parts = [
                f"Upload folder: {scans_dir}",
                f"Files queued: {file_count}",
            ]
            if storage_notice:
                parts.append(storage_notice)
            if message:
                parts.append(message)
            upload_status.value = " | ".join(parts)

        def copy_to_queue(src: Path) -> bool:
            if src.suffix.lower() not in allowed_suffixes:
                return False
            target = scans_dir / src.name
            suffix_idx = 1
            while target.exists():
                target = scans_dir / f"{src.stem}_{suffix_idx}{src.suffix}"
                suffix_idx += 1
            shutil.copy2(src, target)
            return True

        def import_path(path_text: str) -> tuple[int, int]:
            candidate = Path(path_text).expanduser()
            if not candidate.exists():
                return (0, 0)
            if candidate.is_file():
                copied = 1 if copy_to_queue(candidate) else 0
                return (copied, 1)
            if candidate.is_dir():
                copied = 0
                checked = 0
                for item in sorted(candidate.iterdir()):
                    if not item.is_file():
                        continue
                    checked += 1
                    if copy_to_queue(item):
                        copied += 1
                return (copied, checked)
            return (0, 0)

        def render() -> None:
            summary.value = (
                f"Approved: {session.approved_count} | Rejected: {session.rejected_count} "
                f"| Error queue: {len(session.error_queue)}"
            )
            if not session.rows:
                review_status.value = "No scans are currently staged for review. Click Scan on the Upload tab first."
            grid_container.controls.clear()

            header = ft.Row(
                [
                    ft.Text("user_id", width=100, weight=ft.FontWeight.BOLD),
                    ft.Text("question_id", width=110, weight=ft.FontWeight.BOLD),
                    ft.Text("test_id", width=100, weight=ft.FontWeight.BOLD),
                    ft.Text("exam_id", width=100, weight=ft.FontWeight.BOLD),
                    ft.Text("answer", width=80, weight=ft.FontWeight.BOLD),
                    ft.Text("status", width=80, weight=ft.FontWeight.BOLD),
                    ft.Text("actions", width=180, weight=ft.FontWeight.BOLD),
                ]
            )
            grid_container.controls.append(header)

            for idx, row in enumerate(session.rows):
                def mk_on_change(field: str, row_index: int):
                    def _on_change(e: ft.ControlEvent) -> None:
                        session.update_field(row_index, field, e.control.value)
                    return _on_change

                def mk_approve(row_index: int):
                    def _approve(_: ft.ControlEvent) -> None:
                        session.approve(row_index)
                        render()
                        page.update()
                    return _approve

                def mk_reject(row_index: int):
                    def _reject(_: ft.ControlEvent) -> None:
                        session.reject(row_index)
                        render()
                        page.update()
                    return _reject

                grid_container.controls.append(
                    ft.Row(
                        [
                            ft.TextField(value=row.user_id, width=100, dense=True, on_change=mk_on_change("user_id", idx)),
                            ft.TextField(value=row.question_id, width=110, dense=True, on_change=mk_on_change("question_id", idx)),
                            ft.TextField(value=row.test_id, width=100, dense=True, on_change=mk_on_change("test_id", idx)),
                            ft.TextField(value=row.exam_id, width=100, dense=True, on_change=mk_on_change("exam_id", idx)),
                            ft.TextField(value=row.answer, width=80, dense=True, on_change=mk_on_change("answer", idx)),
                            ft.Text(row.status, width=80),
                            ft.Row(
                                [
                                    ft.Button("Approve", on_click=mk_approve(idx)),
                                    ft.Button("Reject", on_click=mk_reject(idx), style=ft.ButtonStyle(side=ft.BorderSide(1))),
                                ],
                                width=180,
                            ),
                        ]
                    )
                )

        render()
        refresh_upload_status()

        upload_controls: list[ft.Control] = [
            ft.Text("Upload files", size=20, weight=ft.FontWeight.BOLD),
            ft.Text("Add scanned PDFs/images to queue for processing.", size=13),
            ft.Text(
                "Paste a file/folder path below, then click Add Path. "
                "This replaces the file picker to avoid unsupported runtime controls.",
                size=13,
            ),
        ]

        def add_path(_: ft.ControlEvent) -> None:
            source_path = normalize_upload_path(manual_path_input.value or "")
            if not source_path:
                refresh_upload_status("Enter a file or folder path first.")
                page.update()
                return
            copied, checked = import_path(source_path)
            if checked == 0:
                refresh_upload_status("Path not found or contains no supported files.")
            elif copied == 0:
                refresh_upload_status("No supported scan files found. Use PDF/JPG/PNG/TIFF/BMP.")
            else:
                refresh_upload_status(f"Added {copied} file(s) from path.")
            page.update()

        def start_scan(_: ft.ControlEvent) -> None:
            selected_file = queued_file_selector.value or ""
            staged_path, message = advance_selected_scan_to_ingestion(ingest_root, selected_file)
            ocr_message = ""
            if staged_path is not None and staged_path.parent.name == "processing":
                ocr_message = run_ocr_and_extract_for_processing_file(ingest_root, staged_path)

            combined_message = message if not ocr_message else f"{message} {ocr_message}"
            refresh_upload_status(combined_message)
            review_status.value = "Scan initiated. Open Review to validate staged rows."
            page.update()

        def refresh_review(_: ft.ControlEvent | None = None) -> None:
            nonlocal session
            refreshed = load_review_session(ingest_root)
            persisted_rows_by_source = {row.source_file: row for row in session.rows}
            for idx, refreshed_row in enumerate(refreshed.rows):
                current_row = persisted_rows_by_source.get(refreshed_row.source_file)
                if current_row is None:
                    continue
                refreshed.rows[idx] = replace(
                    refreshed_row,
                    user_id=current_row.user_id,
                    question_id=current_row.question_id,
                    test_id=current_row.test_id,
                    exam_id=current_row.exam_id,
                    answer=current_row.answer,
                    status=current_row.status,
                )
            session = refreshed
            render()
            page.update()

        def export_review(_: ft.ControlEvent) -> None:
            completed_rows = completed_rows_for_export(session)
            if not completed_rows:
                review_status.value = "No completed rows to export yet. Approve or reject at least one row first."
                page.update()
                return

            output_file = ingest_root / "exports" / "review_export.csv"
            exporter = CsvExporter()
            exporter.export_rows(
                rows=completed_rows,
                fieldnames=["user_id", "question_id", "test_id", "exam_id", "answer", "status"],
                output_path=output_file,
            )

            if config.web_mode:
                csv_text = serialize_completed_rows_to_csv(completed_rows)
                data_uri = f"data:text/csv;charset=utf-8,{quote(csv_text)}"
                page.launch_url(data_uri, web_window_name="_self")
                review_status.value = (
                    f"Exported {len(completed_rows)} completed row(s). Browser download triggered; "
                    f"server copy saved at {output_file}."
                )
            else:
                review_status.value = f"Exported {len(completed_rows)} completed row(s) to {output_file}."
            page.update()

        upload_controls.append(
            ft.Row(
                [
                    manual_path_input,
                    ft.Button("Add Path", on_click=add_path),
                    ft.Button("Refresh", on_click=lambda _: (refresh_upload_status(), page.update())),
                    ft.Button("Scan", on_click=start_scan),
                ]
            )
        )
        upload_controls.append(queued_file_selector)

        upload_controls.append(upload_status)

        upload_view = ft.Column(
            upload_controls,
            spacing=12,
        )

        review_view = ft.Column(
            [
                ft.Text("Review UI: editable grid with approve/reject workflow", size=14),
                summary,
                ft.Row(
                    [
                        ft.Button("Refresh Review Queue", on_click=refresh_review),
                        ft.Button("Export Completed to CSV", on_click=export_review),
                    ]
                ),
                review_status,
                ft.Divider(),
                grid_container,
            ],
            spacing=12,
            expand=True,
        )

        current_view = {"name": "upload"}
        upload_nav_button = ft.Button("Upload", disabled=True)
        review_nav_button = ft.Button("Review")
        tab_content = ft.Container(content=upload_view, expand=True)

        def switch_view(view_name: str) -> None:
            if current_view["name"] == view_name:
                return
            current_view["name"] = view_name
            tab_content.content = upload_view if view_name == "upload" else review_view
            upload_nav_button.disabled = view_name == "upload"
            review_nav_button.disabled = view_name == "review"
            page.update()

        upload_nav_button.on_click = lambda _: switch_view("upload")
        review_nav_button.on_click = lambda _: switch_view("review")

        page.add(
            ft.Text(build_home_title(), size=28, weight=ft.FontWeight.BOLD),
            ft.Row([upload_nav_button, review_nav_button], spacing=8),
            tab_content,
        )

    if config.web_mode:
        ft.run(main, view=ft.AppView.WEB_BROWSER, host=config.host, port=config.port)
        return

    try:
        ft.run(main)
    except Exception as exc:
        if not should_fallback_to_web(exc):
            raise
        ft.run(main, view=ft.AppView.WEB_BROWSER, host=config.host, port=config.port)


if __name__ == "__main__":
    run()
