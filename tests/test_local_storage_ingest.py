from pathlib import Path

from imarisha_scan.ingest import IngestConfig, LocalStorageIngestor


def test_import_files_from_local_storage(tmp_path: Path) -> None:
    cfg = IngestConfig(root_dir=tmp_path)
    cfg.incoming_dir.mkdir(parents=True, exist_ok=True)

    external = tmp_path / "usb"
    external.mkdir()
    pdf = external / "sheet1.pdf"
    jpg = external / "sheet2.jpg"
    txt = external / "notes.txt"

    pdf.write_text("a", encoding="utf-8")
    jpg.write_text("b", encoding="utf-8")
    txt.write_text("c", encoding="utf-8")

    ingestor = LocalStorageIngestor(cfg)
    results = ingestor.import_directory(external, target="incoming")

    statuses = {r.source.name: r.status for r in results}
    assert statuses["sheet1.pdf"] == "imported"
    assert statuses["sheet2.jpg"] == "imported"
    assert statuses["notes.txt"] == "skipped"

    assert (cfg.incoming_dir / "sheet1.pdf").exists()
    assert (cfg.incoming_dir / "sheet2.jpg").exists()


def test_import_duplicate_names_gets_unique_target(tmp_path: Path) -> None:
    cfg = IngestConfig(root_dir=tmp_path)
    cfg.incoming_dir.mkdir(parents=True, exist_ok=True)

    external = tmp_path / "pc"
    external.mkdir()
    source = external / "sheet1.pdf"
    source.write_text("a", encoding="utf-8")

    ingestor = LocalStorageIngestor(cfg)
    first = ingestor.import_files([source], target="incoming")
    second = ingestor.import_files([source], target="incoming")

    assert first[0].destination is not None
    assert second[0].destination is not None
    assert first[0].destination != second[0].destination
