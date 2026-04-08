# Offline Installer Packaging

This folder provides starter scripts for creating offline installers.

## Linux/macOS
- `scripts/package_offline.sh`

## Windows
- `scripts/package_offline.ps1`

Both scripts assume:
- Python dependencies are already installed in a build environment.
- `pyinstaller` is available.
- Local OCR binaries (e.g., Tesseract + `tessdata`) are staged and bundled.
