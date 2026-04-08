"""Entry point for the Imarisha Scan app."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import importlib
import importlib.util
from imarisha_scan.ui import ReviewRecord, ReviewSession


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


def get_runtime_config() -> RuntimeConfig:
    """Resolve runtime mode from environment variables."""
    port = int(os.getenv("PORT", "8550"))
    web_mode = os.getenv("FLET_WEB", "0") == "1"
    return RuntimeConfig(host="0.0.0.0", port=port, web_mode=web_mode)


def should_fallback_to_web(exc: Exception) -> bool:
    msg = str(exc)
    return "CERTIFICATE_VERIFY_FAILED" in msg or "flet" in msg.lower()


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
        grid_container = ft.Column(spacing=8, expand=True, scroll=ft.ScrollMode.AUTO)

        picker = ft.FilePicker()
        page.overlay.append(picker)

        def refresh_upload_status(message: str | None = None) -> None:
            file_count = sum(1 for p in scans_dir.iterdir() if p.is_file())
            parts = [
                f"Upload folder: {scans_dir}",
                f"Files queued: {file_count}",
            ]
            if storage_notice:
                parts.append(storage_notice)
            if message:
                parts.append(message)
            upload_status.value = " | ".join(parts)

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

        def on_files_picked(e: ft.FilePickerResultEvent) -> None:
            files = e.files or []
            if not files:
                refresh_upload_status("No files selected.")
                page.update()
                return
            copied = 0
            for item in files:
                if not item.path:
                    continue
                src = Path(item.path)
                if not src.exists() or not src.is_file():
                    continue
                target = scans_dir / src.name
                suffix_idx = 1
                while target.exists():
                    target = scans_dir / f"{src.stem}_{suffix_idx}{src.suffix}"
                    suffix_idx += 1
                shutil.copy2(src, target)
                copied += 1
            refresh_upload_status(f"Uploaded {copied} file(s).")
            page.update()

        picker.on_result = on_files_picked

        upload_view = ft.Column(
            [
                ft.Text("Upload files", size=20, weight=ft.FontWeight.BOLD),
                ft.Text("Select scanned PDFs/images to queue for processing.", size=13),
                ft.Row(
                    [
                        ft.Button(
                            "Choose Files",
                            on_click=lambda _: picker.pick_files(
                                allow_multiple=True,
                                dialog_title="Select scan files",
                            ),
                        ),
                        ft.Button("Refresh", on_click=lambda _: (refresh_upload_status(), page.update())),
                    ]
                ),
                upload_status,
            ],
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

        page.add(
            ft.Text(build_home_title(), size=28, weight=ft.FontWeight.BOLD),
            ft.Tabs(
                expand=1,
                tabs=[
                    ft.Tab(text="Upload", content=upload_view),
                    ft.Tab(text="Review", content=review_view),
                ],
            ),
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
