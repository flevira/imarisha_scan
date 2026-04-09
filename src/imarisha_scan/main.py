"""Entry point for the Imarisha Scan app."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
import sys

import importlib
import importlib.util
from imarisha_scan.ingest import FolderLifecycleManager, IngestConfig


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
    from imarisha_scan.ui import ReviewRecord, ReviewSession
except ModuleNotFoundError:
    @dataclass(frozen=True)
    class ReviewRecord:
        user_id: str
        question_id: str
        test_id: str
        exam_id: str
        answer: str
        status: str = "pending"


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


def _sample_review_session() -> ReviewSession:
    return ReviewSession(
        [
            ReviewRecord(user_id="82", question_id="81535", test_id="", exam_id="1756", answer="C"),
            ReviewRecord(user_id="82", question_id="81570", test_id="", exam_id="1756", answer="A"),
            ReviewRecord(user_id="82", question_id="81679", test_id="", exam_id="1756", answer="E"),
        ]
    )


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

        session = _sample_review_session()
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
            _, message = advance_selected_scan_to_ingestion(ingest_root, selected_file)
            refresh_upload_status(message)
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
