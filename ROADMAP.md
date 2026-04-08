# Python + Flet Scanner-to-CSV App Roadmap

## 1) Product Goals
- Build a cross-platform desktop app (Windows-first, then macOS/Linux) with a simple Flet UI.
- Ingest scans from TWAIN/WIA/SANE workflows and from local image/PDF files.
- Extract structured fields using OCR + document parsing.
- Let users validate extracted values before export.
- Export reliable CSV files with schema validation and audit logs.

## 2) Suggested Architecture

### Desktop shell (Flet)
- **Flet UI layer**: multi-page workflow (`Import -> Review -> Export -> History`).
- **State management**: keep a document session object (source file, pages, extracted fields, confidence, validation status).
- **Background tasks**: run OCR/parsing in worker threads/processes and stream progress to UI.

### Core processing services (Python modules)
- `ingest/`
  - File import for PDF/JPG/PNG/TIFF.
  - Scanner integration adapter (start with folder watch + manual import; add native scanner bridge in Phase 2).
- `preprocess/`
  - Deskew, denoise, contrast normalization, page splitting, DPI checks.
- `ocr/`
  - OCR provider abstraction (`Tesseract`, `PaddleOCR`, optional cloud OCR later).
  - Output normalized tokens + bounding boxes + confidence.
- `extract/`
  - Template rules (regex, anchor text, table region extraction).
  - Optional ML fallback for non-template documents.
- `export/`
  - CSV writer with strict schema mapping and type coercion.
  - Batch export + per-row error file.
- `storage/`
  - SQLite for job history, templates, mappings, and QA feedback.

### Reliability & Observability
- Structured logging (`structlog` / stdlib logging JSON formatter).
- Retry strategy for transient OCR failures.
- Deterministic run IDs and artifact folder per job.

## 3) Repo Bootstrap (Week 1)
1. **Initialize project layout**
   - `src/app` for Flet UI.
   - `src/core` for ingest/preprocess/ocr/extract/export.
   - `tests/` with unit + integration split.
2. **Tooling**
   - `uv` or `poetry`, `ruff`, `mypy`, `pytest`, `pre-commit`.
   - GitHub Actions for lint + tests.
3. **Config strategy**
   - `pydantic-settings` for environment-specific config.
   - `config/default.toml` + local override.

## 4) Delivery Phases

### Phase 1 (MVP, Weeks 2–4)
- Import local PDF/images (no direct scanner SDK yet).
- OCR + simple extraction rules.
- Review table in Flet with inline edits.
- Export to CSV with schema checks.
- Save processing history locally (SQLite).

### Phase 2 (Scanner + Better Parsing, Weeks 5–7)
- Add scanner ingestion path:
  - Windows: WIA/TWAIN bridge.
  - Linux: SANE command-based adapter.
- Add template designer UI:
  - Define fields, regex, anchors, and validation constraints.
- Improve table extraction and multi-page handling.

### Phase 3 (Quality + Scale, Weeks 8–10)
- Confidence scoring and human-in-the-loop queue.
- Batch processing pipeline and resumable jobs.
- Export profiles (different CSV formats for different downstream systems).
- Packaging/distribution:
  - Windows `.exe` installer.
  - macOS app bundle (if needed).

## 5) Data Model (Minimum)
- `DocumentJob`: id, source, created_at, status, total_pages.
- `PageResult`: job_id, page_no, ocr_confidence, image_path.
- `FieldResult`: page_id, field_name, value, confidence, validator_status.
- `ExportRun`: job_id, schema_version, csv_path, exported_at.

## 6) Extraction Strategy
- Start **rule-first** (faster to stabilize for known forms/invoices).
- Keep extraction pipeline pluggable:
  1. template matcher,
  2. region OCR,
  3. regex/post-processing,
  4. fallback heuristics.
- Add a feedback loop: corrected values become test fixtures.

## 7) Testing Strategy
- Unit tests for preprocess, parser, validators, CSV writer.
- Golden-file tests for OCR/extraction on representative scan sets.
- End-to-end test:
  - input sample PDF -> reviewed fields -> expected CSV.
- Performance smoke tests on 100+ page batches.

## 8) Security & Compliance
- Encrypt or hash sensitive fields at rest if required.
- Configurable retention policy for scanned images.
- Redact PII in logs by default.

## 9) Risks & Mitigations
- **Low-quality scans** -> stronger preprocessing + manual review queue.
- **Template drift** -> versioned templates + change tracking.
- **Scanner driver variability** -> adapter interface + staged OS support.
- **OCR language variance** -> language packs + per-template OCR settings.

## 10) Immediate Next 10 Tasks
1. Scaffold Python package + Flet app entrypoint.
2. Add lint/type/test toolchain.
3. Build import page (drag/drop + file picker).
4. Implement preprocess pipeline.
5. Integrate OCR provider abstraction with one local engine.
6. Implement first extraction template format (YAML/JSON).
7. Build review/edit table in UI.
8. Implement CSV export with schema validation.
9. Add SQLite persistence for job history.
10. Add baseline E2E test with sample documents.

## 11) Recommended Tech Stack
- UI: `flet`
- OCR: `pytesseract` (initial), optional `paddleocr`
- PDF/images: `pymupdf`, `pillow`, `opencv-python`
- Data processing: `pandas` (optional), `pydantic`
- Persistence: `sqlite3` / `sqlmodel`
- Packaging: `pyinstaller` or `briefcase`
- QA: `pytest`, `pytest-cov`, `hypothesis` (optional)
