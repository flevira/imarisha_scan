"""Entry point for the Imarisha Scan app."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeConfig:
    host: str
    port: int
    web_mode: bool


def build_home_title() -> str:
    """Return the title used on the home screen."""
    return "Imarisha Scan"


def get_runtime_config() -> RuntimeConfig:
    """Resolve runtime mode from environment variables."""
    port = int(os.getenv("PORT", "8550"))
    web_mode = os.getenv("FLET_WEB", "0") == "1" or "RAILWAY_ENVIRONMENT" in os.environ
    return RuntimeConfig(host="0.0.0.0", port=port, web_mode=web_mode)


def run() -> None:
    """Start the Flet app in desktop or web mode."""
    import flet as ft

    config = get_runtime_config()

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

    if config.web_mode:
        ft.app(target=main, view=ft.AppView.WEB_BROWSER, host=config.host, port=config.port)
        return

    ft.app(target=main)


if __name__ == "__main__":
    run()
