from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


def _status_counts(path: Path) -> Counter[str]:
    if not path.is_file():
        return Counter()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return Counter(row.get("Status", "Tidak diketahui") for row in csv.DictReader(stream))


def _row_count(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return sum(1 for _ in csv.DictReader(stream))


def summarize_reports(output_dir: Path, check_only: bool) -> str:
    if check_only:
        counts = _status_counts(output_dir / "combine_check.csv")
        if not counts:
            return "Pemeriksaan selesai, tetapi laporan belum ditemukan."
        lines = ["Hasil Pemeriksaan"]
        lines.extend(f"{status}: {count}" for status, count in sorted(counts.items()))
        return "\n".join(lines)

    counts = _status_counts(output_dir / "combine_result.csv")
    if not counts:
        return "Penggabungan selesai, tetapi laporan hasil belum ditemukan."
    lines = ["Hasil Penggabungan"]
    lines.extend(f"{status}: {count}" for status, count in sorted(counts.items()))
    lines.append(f"Berkas missing/duplikat: {_row_count(output_dir / 'combine_missing.csv')}")
    lines.append(f"Berkas mismatch: {_status_counts(output_dir / 'combine_check.csv').get('mismatch', 0)}")
    return "\n".join(lines)
