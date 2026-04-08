# Offline Readiness Review

## Verdict
The current scaffold is **partially aligned** with an offline-first desktop app, but it still needs a few explicit choices to fully meet offline requirements.

## What already supports offline usage
- Desktop-first Flet runtime path is present (`run()` uses native mode unless `FLET_WEB=1`).
- Local domain model scaffolding exists (`DocumentJob`) for on-device processing.
- No cloud APIs are hardwired into the code path.

## Gaps to close for true offline operation
1. **OCR engine bundling**
   - Choose and bundle a local OCR engine (e.g., Tesseract + language packs).
   - Ensure installer includes binaries and verifies them at startup.
2. **Scanner drivers/integration**
   - Implement local adapters for TWAIN/WIA (Windows) and SANE (Linux).
   - Add fallback folder-watch import for environments without drivers.
3. **Local persistence & queueing**
   - Add SQLite-backed job queue and artifact storage paths.
   - Make processing resilient to app restarts (resume unfinished jobs).
4. **Export + validation profiles**
   - Store schemas and mapping rules locally.
   - Add validation before CSV generation to avoid bad exports.
5. **Packaging for offline installs**
   - Create platform installers with all required binaries/resources.
   - Support air-gapped installation instructions.

## Recommendation
Treat the Docker/Railway path as optional tooling only. For the product target, prioritize a native desktop packaging track (`PyInstaller`/`Briefcase`) and local service adapters first.

## Priority implementation sequence (offline)
1. Ingest: file import + scanner adapter interface.
2. Preprocess: deskew/denoise pipeline.
3. OCR: local engine integration + confidence scoring.
4. Extract: rule/template pipeline.
5. Review UI: editable fields + validation errors.
6. Export: CSV writer + schema profiles.
7. Persistence: SQLite job history + recoverability.
8. Packaging: signed offline installers.
