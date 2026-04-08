# Offline Installer Packaging

The app currently has **no login requirement** and can be packaged for both Windows and macOS.

## Platform support
- **Windows:** supported via `pyinstaller` on a Windows host.
- **macOS (MacBook):** supported via `pyinstaller` on a macOS host.

> Note: cross-compiling native desktop binaries is not recommended. Build each platform on that platform.

## Build scripts
- Windows (PowerShell): `scripts/package_offline.ps1`
- Windows (bash shell): `scripts/package_offline.sh`
- macOS (bash shell): `scripts/package_offline_macos.sh`

## Example commands
### Windows
```powershell
pip install .[packaging,ui]
./scripts/package_offline.ps1
```

### macOS
```bash
pip install .[packaging,ui]
./scripts/package_offline_macos.sh
```

## Output
- Windows binary: `dist/windows/imarisha-scan.exe`
- macOS app bundle: `dist/macos/imarisha-scan.app`

## Optional polishing checklist
- Code-sign installers/app bundles.
- Add app icon and metadata.
- Bundle OCR binaries/language packs for offline use.
- Run smoke tests on clean machines before release.
