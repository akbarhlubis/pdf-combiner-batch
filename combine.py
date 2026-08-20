#!/usr/bin/env python3
"""Gabungkan PDF bernama sama dari subfolder berbeda menjadi satu PDF.

Contoh struktur yang didukung:

    input/
      eklaim/0099R0010726V000032.pdf     <- 1
      rm/0099R0010726V000032.pdf         <- 2 (nama sama)
    result/0099R0010726V000032.pdf       <- gabungan 1+2

Cara pakai (dari folder proyek ini):

    python combine.py                      # input/ -> result/ (hanya duplikat)
    python combine.py --dry-run            # lihat rencana, tanpa menulis
    python combine.py --include-unique     # proses juga nama yang hanya 1 folder
    python combine.py --output "D:\\gabung"
    python combine.py --engine gs          # paksa Ghostscript

Engine gabung (--engine / env EKLAIM_COMBINE_ENGINE):
    auto  (default) : Ghostscript bila tersedia, fallback ke pypdf
    gs              : paksa Ghostscript (engine utama)
    pypdf           : paksa pypdf (opsional, fallback saja)

Ghostscript adalah engine utama (hasil lebih kecil, paling andal); pypdf
hanya dipakai sebagai fallback + validasi jumlah halaman. Install pypdf
bersifat opsional selama Ghostscript tersedia.

Sumber tidak pernah diubah — hanya dibaca.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent

try:
    from pypdf import PdfReader, PdfWriter
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

# ---------------------------------------------------------------- env
COMBINE_ENGINE = os.getenv("EKLAIM_COMBINE_ENGINE", "auto").strip().lower()
GS_EXECUTABLE = os.getenv("EKLAIM_GS_EXECUTABLE", "")

# ---------------------------------------------------------------- logging
def _setup_logging() -> logging.Logger:
    logger = logging.getLogger("combine")
    logger.setLevel(logging.DEBUG)
    for h in list(logger.handlers):
        logger.removeHandler(h)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")
    fh = logging.FileHandler(PROJECT_DIR / "combine.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


log = _setup_logging()

# ---------------------------------------------------------------- helpers
def _nat_key(s: str):
    """Natural sort: 'Tanggal 5' < 'Tanggal 25'."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def find_pdfs(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*")
                  if p.is_file() and p.suffix.lower() == ".pdf")


def group_by_name(files: list[Path]) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = {}
    for f in files:
        groups.setdefault(f.name.lower(), []).append(f)
    return groups


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def page_count(path: Path) -> int:
    """Jumlah halaman: pypdf (bila ada), fallback hitung via Ghostscript."""
    if HAS_PYPDF:
        with open(path, "rb") as fh:
            return len(PdfReader(fh).pages)
    gs = find_gs()
    if not gs:
        return 0
    try:
        # -dNOSAFER: izinkan baca file lokal untuk penghitungan halaman
        cmd = [gs, "-q", "-dNOSAFER", "-dNODISPLAY", "-c",
               f"({path}) (r) file runpdfbegin pdfpagecount = quit"]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return int(out.stdout.strip().splitlines()[-1])
    except Exception:
        return 0


# ---------------------------------------------------------------- engines
def find_gs() -> str | None:
    """Deteksi Ghostscript: env -> PATH -> folder install umum Windows.

    Utamakan executable asli (gswin64c/gs); tolak shim .cmd/.bat (gs.cmd)
    yang tidak bisa dipanggil langsung via subprocess.
    """
    if GS_EXECUTABLE and Path(GS_EXECUTABLE).exists():
        return GS_EXECUTABLE
    for name in ("gswin64c", "gswin32c", "gs"):
        found = shutil.which(name)
        if found and not found.lower().endswith((".cmd", ".bat")):
            return found
    for pattern in (
        r"C:\Program Files\gs\gs*\bin\gswin64c.exe",
        r"C:\Program Files (x86)\gs\gs*\bin\gswin64c.exe",
    ):
        hits = sorted(glob.glob(pattern), key=_nat_key, reverse=True)
        if hits:
            return hits[0]
    return None


def merge_pypdf(paths: list[Path], out_path: Path) -> int:
    writer = PdfWriter()
    for p in paths:
        with open(p, "rb") as fh:
            reader = PdfReader(fh)
            for page in reader.pages:
                writer.add_page(page)
    with open(out_path, "wb") as fh:
        writer.write(fh)
    return page_count(out_path)


def merge_gs(paths: list[Path], out_path: Path) -> int:
    gs = find_gs()
    if not gs:
        raise RuntimeError(
            "Ghostscript tidak ditemukan — set EKLAIM_GS_EXECUTABLE atau "
            "pasang di PATH (contoh: D:\\Program Files\\gs\\gs10.06.0\\bin\\gswin64c.exe)"
        )
    cmd = [
        gs, "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=pdfwrite",
        "-dPDFSETTINGS=/prepress", f"-sOutputFile={out_path}",
    ] + [str(p) for p in paths]
    subprocess.run(cmd, check=True, capture_output=True)
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError("Ghostscript tidak menghasilkan file output")
    return page_count(out_path)


def merge_any(paths: list[Path], out_path: Path, engine: str) -> int:
    """Gabung sesuai engine. auto = Ghostscript dulu, fallback pypdf."""
    if engine == "pypdf":
        if not HAS_PYPDF:
            raise RuntimeError(
                "pypdf tidak terpasang — install via: pip install pypdf"
            )
        return merge_pypdf(paths, out_path)

    if engine == "gs":
        return merge_gs(paths, out_path)  # error jelas bila gs tidak ada

    # auto: GS utama, pypdf fallback
    if find_gs():
        try:
            return merge_gs(paths, out_path)
        except Exception as exc:
            if HAS_PYPDF:
                log.warning("Ghostscript gagal (%s) — fallback ke pypdf.", exc)
                return merge_pypdf(paths, out_path)
            raise
    if HAS_PYPDF:
        log.warning("Ghostscript tidak terdeteksi — memakai pypdf.")
        return merge_pypdf(paths, out_path)
    raise RuntimeError(
        "Tidak ada engine tersedia: Ghostscript tidak ditemukan dan pypdf "
        "belum terpasang. Install salah satunya."
    )


# ---------------------------------------------------------------- hasil
_STATUS_LABEL = {
    "merged": "Berhasil digabung",
    "copied": "Disalin (1 folder)",
    "identical": "File identik — disalin sekali",
    "skipped": "Nama unik — dilewati",
    "exists_skipped": "Output sudah ada — dilewati",
    "failed": "Gagal",
}
_RESULT_HEADERS = ["name", "nosep", "status", "keterangan", "pages", "detail"]
_RESULT_HEADER_LABEL = {
    "name": "Nama File", "nosep": "NOSEP", "status": "Status",
    "keterangan": "Keterangan", "pages": "Halaman", "detail": "Detail",
}


def _write_result(rows: list[dict]) -> None:
    import csv
    out = PROJECT_DIR / "combine_result.csv"
    with open(out, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_RESULT_HEADERS)
        writer.writerow({k: _RESULT_HEADER_LABEL[k] for k in _RESULT_HEADERS})
        for r in rows:
            name = r.get("name", "")
            writer.writerow({
                "name": name,
                "nosep": Path(name).stem,
                "status": r.get("status", ""),
                "keterangan": _STATUS_LABEL.get(r.get("status", ""), ""),
                "pages": r.get("pages", ""),
                "detail": r.get("detail", ""),
            })


def missing_report(root: Path) -> tuple[list[dict], dict]:
    """Laporan nama file yang tidak lengkap antar folder sumber.

    Sumber = anak langsung folder input (mis. input/E-Klaim, input/Berkas
    Digital). Baris = nama yang tidak ada di SEMUA sumber, atau duplikat
    dalam satu sumber. Return (rows matriks, ringkasan).
    """
    files = find_pdfs(root)
    if not files:
        return [], {}
    sources = sorted({p.relative_to(root).parts[0] for p in files})
    # nama(lower) -> {sumber: jumlah}
    groups: dict[str, dict[str, int]] = {}
    orig_name: dict[str, str] = {}
    for p in files:
        parts = p.relative_to(root).parts
        src = parts[0] if len(parts) > 1 else "(root)"
        key = p.name.lower()
        orig_name.setdefault(key, p.name)
        per = groups.setdefault(key, {})
        per[src] = per.get(src, 0) + 1

    rows = []
    for name in sorted(groups):
        per = groups[name]
        ada = {s for s, c in per.items() if c > 0}
        missing = sorted(set(sources) - ada)
        dups = sorted((s, c) for s, c in per.items() if c > 1)
        if not missing and not dups:
            continue
        row = {"nosep": Path(orig_name[name]).stem, "nama_file": orig_name[name]}
        for s in sources:
            row[s] = "ada" if s in ada else "TIDAK"
        ket = []
        if missing:
            ket.append("tidak ada di: " + ", ".join(missing))
        if dups:
            ket.append("duplikat di: " + ", ".join(f"{s}({c}x)" for s, c in dups))
        row["keterangan"] = " | ".join(ket)
        rows.append(row)

    ringkasan = {
        "sumber": sources,
        "per_sumber": {s: sum(1 for p in files
                              if (p.relative_to(root).parts[0] if len(p.relative_to(root).parts) > 1 else "(root)") == s)
                       for s in sources},
        "nama_union": len(groups),
        "lengkap": sum(1 for per in groups.values()
                       if all(per.get(s, 0) == 1 for s in sources)),
        "bermasalah": len(rows),
    }
    return rows, ringkasan


def _write_missing(rows: list[dict], sources: list[str]) -> None:
    import csv
    out = PROJECT_DIR / "combine_missing.csv"
    fieldnames = ["nosep", "nama_file"] + sources + ["keterangan"]
    labels = {"nosep": "NOSEP", "nama_file": "Nama File", "keterangan": "Keterangan"}
    with open(out, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writerow({k: labels.get(k, k) for k in fieldnames})
        writer.writerows(rows)


def _autosize(ws, cap: int = 40) -> None:
    from openpyxl.utils import get_column_letter
    for col in ws.columns:
        width = max((len(str(c.value or "")) for c in col), default=4) + 2
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(width, cap)


def _write_xlsx(rows: list[dict], missing_rows: list[dict],
                sources: list[str], ringkasan: dict) -> None:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
    except ImportError:
        log.warning("openpyxl belum terpasang — lewati laporan Excel "
                    "(pip install openpyxl).")
        return
    fill_color = {"merged": "C6EFCE", "copied": "C6EFCE", "identical": "C6EFCE",
                  "skipped": "FFEB9C", "exists_skipped": "FFEB9C", "failed": "FFC7CE"}
    wb = Workbook()

    ws = wb.active
    ws.title = "Hasil"
    ws.append([_RESULT_HEADER_LABEL[k] for k in _RESULT_HEADERS])
    for r in rows:
        name = r.get("name", "")
        ws.append([name, Path(name).stem, r.get("status", ""),
                   _STATUS_LABEL.get(r.get("status", ""), ""),
                   r.get("pages", ""), r.get("detail", "")])
        color = fill_color.get(r.get("status"))
        if color:
            ws.cell(row=ws.max_row, column=3).fill = PatternFill("solid", fgColor=color)
    for c in ws[1]:
        c.font = Font(bold=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    _autosize(ws)

    ws2 = wb.create_sheet("Ringkasan")
    ws2.append(["Status", "Jumlah"])
    for status in _STATUS_LABEL:
        ws2.append([_STATUS_LABEL[status],
                    sum(1 for r in rows if r.get("status") == status)])
    ws2.append(["Total", len(rows)])
    if ringkasan:
        ws2.append([])
        ws2.append(["Ringkasan Missing", ""])
        for s in ringkasan.get("sumber", []):
            ws2.append([f"File di {s}", ringkasan["per_sumber"].get(s, 0)])
        ws2.append(["Nama unik (union)", ringkasan.get("nama_union", 0)])
        ws2.append(["Lengkap (ada di semua sumber)", ringkasan.get("lengkap", 0)])
        ws2.append(["Bermasalah (missing/duplikat)", ringkasan.get("bermasalah", 0)])
    for c in ws2[1]:
        c.font = Font(bold=True)
    _autosize(ws2)

    if missing_rows:
        ws3 = wb.create_sheet("Missing")
        fieldnames = ["nosep", "nama_file"] + sources + ["keterangan"]
        labels = {"nosep": "NOSEP", "nama_file": "Nama File", "keterangan": "Keterangan"}
        ws3.append([labels.get(k, k) for k in fieldnames])
        for r in missing_rows:
            ws3.append([r.get(k, "") for k in fieldnames])
        for c in ws3[1]:
            c.font = Font(bold=True)
        ws3.freeze_panes = "A2"
        ws3.auto_filter.ref = ws3.dimensions
        _autosize(ws3)

    out = PROJECT_DIR / "combine_result.xlsx"
    wb.save(out)
    log.info("Laporan Excel: %s", out)


def process_group(name: str, paths: list[Path], out_dir: Path,
                  only_duplicates: bool, force: bool, engine: str) -> dict:
    orig_name = paths[0].name  # pertahankan case asli
    stem = Path(orig_name).stem
    ext = Path(orig_name).suffix or ".pdf"
    out_file = out_dir / f"{stem}{ext}"

    if out_file.exists() and not force:
        return {"name": orig_name, "status": "exists_skipped", "pages": 0,
                "detail": "output sudah ada (pakai --force untuk menimpa)"}

    if len(paths) == 1:
        if only_duplicates:
            return {"name": orig_name, "status": "skipped", "pages": 0,
                    "detail": "nama unik (default: hanya duplikat)"}
        shutil.copy2(paths[0], out_file)
        return {"name": orig_name, "status": "copied", "pages": page_count(out_file),
                "detail": ""}

    ordered = sorted(paths, key=lambda p: _nat_key(str(p)))
    if len({sha256(p) for p in paths}) == 1:
        shutil.copy2(ordered[0], out_file)
        return {"name": orig_name, "status": "identical", "pages": page_count(out_file),
                "detail": f"file identik dari {len(paths)} folder"}

    try:
        pages = merge_any(ordered, out_file, engine)
        return {"name": orig_name, "status": "merged", "pages": pages,
                "detail": " + ".join(p.parent.name for p in ordered)}
    except Exception as exc:
        return {"name": orig_name, "status": "failed", "pages": 0, "detail": f"{exc}"}


# ---------------------------------------------------------------- main
def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Gabungkan PDF bernama sama dari subfolder berbeda (read-only pada sumber).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--input", default=str(PROJECT_DIR / "input"),
                   help="Folder sumber (dipindai rekursif)")
    p.add_argument("--output", default=str(PROJECT_DIR / "result"),
                   help="Folder hasil")
    p.add_argument("--include-unique", action="store_true",
                   help="Proses juga nama yang hanya muncul di 1 folder "
                        "(default: hanya nama duplikat)")
    p.add_argument("--engine", choices=["auto", "pypdf", "gs"], default=COMBINE_ENGINE,
                   help="Engine gabung: auto = pypdf lalu fallback Ghostscript")
    p.add_argument("--force", action="store_true", help="Timpa output yang sudah ada")
    p.add_argument("--dry-run", action="store_true", help="Rencana saja, tanpa menulis")
    p.add_argument("--xlsx", action="store_true",
                   help="Tulis juga laporan Excel (butuh openpyxl)")
    args = p.parse_args(argv)

    log.info("=" * 60)
    log.info("Gabungkan PDF — dimulai (engine=%s)", args.engine)
    if args.engine == "pypdf" and not HAS_PYPDF:
        log.error("pypdf tidak terpasang (pip install pypdf) — tidak bisa pakai engine pypdf.")
        return 2
    if args.engine == "gs" and not find_gs():
        log.error("Ghostscript tidak ditemukan (set EKLAIM_GS_EXECUTABLE atau install gs).")
        return 2
    if args.engine == "auto" and not find_gs() and not HAS_PYPDF:
        log.error("Ghostscript dan pypdf tidak tersedia — install salah satunya.")
        return 2
    if args.engine == "auto" and find_gs():
        log.info("Ghostscript terdeteksi — dipakai sebagai engine utama.")

    root = Path(args.input)
    if not root.is_dir():
        log.error("Folder input tidak ditemukan: %s", root)
        return 2
    out_dir = Path(args.output)

    files = find_pdfs(root)
    if not files:
        log.error("Tidak ada PDF di %s", root)
        return 2
    groups = group_by_name(files)
    duplicates = {n: ps for n, ps in groups.items() if len(ps) > 1}
    log.info("Total PDF: %s | nama unik: %s | nama duplikat: %s",
             len(files), len(groups), len(duplicates))

    if args.dry_run:
        log.info("DRY RUN — tidak ada file yang ditulis. Output akan ke: %s", out_dir)
        for name in sorted(duplicates):
            paths = sorted(duplicates[name], key=lambda p: _nat_key(str(p)))
            log.info("  %s -> %s: %s", Path(name).name, len(paths),
                     " ; ".join(p.parent.name for p in paths))
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    log.info("Output: %s", out_dir)

    rows = []
    merged = copied = failed = 0
    only_dup = not args.include_unique
    for name in sorted(groups):
        r = process_group(name, groups[name], out_dir,
                          only_dup, args.force, args.engine)
        rows.append(r)
        if r["status"] == "merged":
            merged += 1
        elif r["status"] in ("copied", "identical"):
            copied += 1
        elif r["status"] == "failed":
            failed += 1
        log.info("%-16s %-14s %4s hal  %s", r["status"], r["name"][:32],
                 r["pages"] or "-", r["detail"])

    _write_result(rows)
    missing_rows, ringkasan = missing_report(root)
    if ringkasan:
        _write_missing(missing_rows, ringkasan["sumber"])
        log.info("Missing report: %s nama unik (%s lengkap, %s bermasalah) — "
                 "combine_missing.csv", ringkasan["nama_union"],
                 ringkasan["lengkap"], ringkasan["bermasalah"])
    if args.xlsx:
        _write_xlsx(rows, missing_rows, ringkasan.get("sumber", []), ringkasan)
    log.info("Selesai. merged=%s copied/identical=%s failed=%s "
             "(ringkasan: combine_result.csv)", merged, copied, failed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
