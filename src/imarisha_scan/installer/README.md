# Offline Installer Packaging

The app currently has **no login requirement** and can be packaged for both Windows and macOS.

## Platform support
- **Windows:** supported via `pyinstaller` on a Windows host.
- **macOS (MacBook):** supported via `flet build macos` on a macOS host.

> Note: cross-compiling native desktop binaries is not recommended. Build each platform on that platform.

## Build scripts
- Windows (PowerShell): `scripts/package_offline.ps1`
- Windows (bash shell): `scripts/package_offline.sh`
- macOS app bundle: `scripts/package_offline_macos.sh`
- macOS installer package (`.pkg`): `scripts/package_offline_macos_pkg.sh`

## Example commands
### Windows
```powershell
pip install .[packaging,ui]
./scripts/package_offline.ps1
```

### macOS
```bash
pip install .[ui]
./scripts/package_offline_macos.sh
./scripts/package_offline_macos_pkg.sh
```

### macOS with bundled Poppler (for PDF OCR offline)
```bash
# Example Homebrew location:
POPPLER_STAGING_DIR=/opt/homebrew/opt/poppler ./scripts/package_offline_macos.sh
./scripts/package_offline_macos_pkg.sh
```

If `POPPLER_STAGING_DIR` is set, `package_offline_macos.sh` copies Poppler's `bin/` (and optional `lib/`, `share/`)
into `imarisha-scan.app/Contents/Resources/poppler`, allowing PDF OCR without system-level Poppler install.

## Output
- Windows binary: `dist/windows/imarisha-scan.exe`
- macOS app bundle: `dist/macos/imarisha-scan.app`
- macOS installer package: `dist/macos/imarisha-scan.pkg`

## Common macOS install error
If you see `Couldn't open "imarisha-scan.pkg"` (Installer page controller error), verify:
1. The file is an actual `.pkg` produced by `package_offline_macos_pkg.sh`.
2. It is not corrupted/truncated during copy.
3. You removed quarantine if downloaded from the internet:
   - `xattr -dr com.apple.quarantine dist/macos/imarisha-scan.pkg`

## Common macOS build error (`codesign ... bundle format unrecognized`)
If `pyinstaller` fails during `codesign` (for example under `flet_desktop/.../device_info_plus.framework`):
1. Use the repo build script (`./scripts/package_offline_macos.sh`), which builds through `flet build macos` instead of direct `pyinstaller`.
2. If `flet` command is missing, install UI extras first: `python -m pip install .[ui]`.
3. If you still run `pyinstaller` manually, expect framework-signing failures on some Python/macOS versions.


## Common Flet SSL runtime error
If first launch shows `CERTIFICATE_VERIFY_FAILED` while preparing Flet desktop runtime:
1. Ensure cert bundle exists on machine (`python3 -m pip install certifi`).
2. Relaunch app (current runtime attempts web fallback when desktop runtime fetch fails).
3. In locked-down networks, pre-test on a machine with internet to warm caches before offline rollout.

## Optional polishing checklist
- Code-sign installers/app bundles.
- Add app icon and metadata.
- Bundle OCR binaries/language packs for offline use.
- Run smoke tests on clean machines before release.
