"""Entry point for the Imarisha Scan desktop app scaffold."""

from __future__ import annotations


def build_home_title() -> str:
    """Return the title used on the home screen."""
    return "Imarisha Scan"


def run() -> None:
    """Start the Flet app if available."""
    try:
        import flet as ft
    except Exception as exc:  # pragma: no cover - runtime convenience path
        raise RuntimeError(
            "Flet is not installed. Install project dependencies to run the desktop app."
        ) from exc

    def main(page: "ft.Page") -> None:
        page.title = build_home_title()
        page.window_width = 980
        page.window_height = 680
        page.padding = 24
        page.add(
            ft.Text(build_home_title(), size=30, weight=ft.FontWeight.BOLD),
            ft.Text("Scanner/Image/PDF ingestion → extraction → CSV export", size=16),
            ft.Divider(),
            ft.Text("Scaffold ready. Implement Import, Review, and Export views next."),
        )

    ft.app(target=main)


if __name__ == "__main__":
    run()
