from __future__ import annotations

import csv
from pathlib import Path


class CsvExporter:
    def export_rows(self, rows: list[dict[str, str]], fieldnames: list[str], output_path: str | Path) -> Path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return out
