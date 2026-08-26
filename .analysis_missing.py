#!/usr/bin/env python3
"""Analisis sementara: SEP RM tanpa klaim eklaim -> cari pasangan via No Rekam Medis."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from combine import missing_report  # noqa: E402
from pypdf import PdfReader  # noqa: E402

SEP_RE = re.compile(r"\d{4}[A-Za-z]\d{7}[A-Za-z]\d{6}")

def page_text(path: Path) -> str:
    try:
        return "".join((pg.extract_text() or "") for pg in PdfReader(str(path)).pages)
    except Exception:
        return ""

def grab(text: str, *pats: str) -> str:
    for pat in pats:
        m = re.search(pat, text)
        if m:
            return m.group(1).strip()
    return ""

# 1. daftar SEP RM tanpa eklaim (current state)
rows, ring = missing_report(Path("input"))
rm_no_eklaim = sorted({r["nosep"].upper() for r in rows
                       if r.get("00_eklaim") == "TIDAK"})
print(f"SEP RM tanpa eklaim (current): {len(rm_no_eklaim)}")

# 2. indeks eklaim: No RM -> [(SEP, jenis_perawatan, tgl_masuk)]
eklaim_index: dict[str, list[tuple]] = {}
for p in sorted(Path("input/00_eklaim").rglob("*.pdf")):
    t = page_text(p)
    sep = grab(t, r"Nomor SEP\s*:\s*(" + SEP_RE.pattern + ")")
    nrm = grab(t, r"Nomor Rekam Medis\s*:\s*(\S+)").replace(":", "").strip()
    if not sep or not nrm:
        continue
    jenis = grab(t, r"Jenis Perawatan\s*:\s*([^\n]+)")
    tgl = grab(t, r"Tanggal Masuk\s*:\s*([^\n]+)")
    eklaim_index.setdefault(nrm, []).append((sep, jenis, tgl))
print(f"file eklaim diindeks: {len(eklaim_index)} No RM unik")

# 3. untuk tiap SEP missing, baca RM file -> No RM + nama + unit + tanggal
matched = []   # ditemukan pasangan eklaim via No RM
unmatched = []  # tidak ada klaim eklaim sama sekali
for sep in rm_no_eklaim:
    hits = sorted(Path("input/01_berkas digital").rglob(sep + ".pdf"))
    if not hits:
        unmatched.append((sep, "FILE RM TIDAK DITEMUKAN", "", "", "", ""))
        continue
    t = page_text(hits[0])
    nrm = grab(t, r"No\.?RM\s*[:=]\s*([0-9]+)").strip() or grab(t, r"No\s+Rekam Medis\s*:\s*(\S+)").strip()
    nama = grab(t, r"Nama Pasien\s*:\s*([^\n]+)")
    unit = grab(t, r"Unit/Instansi\s*:\s*([^\n]+)")
    tgl = grab(t, r"Tanggal & Jam\s*:\s*([^\n]+)")
    pairs = eklaim_index.get(nrm, [])
    if pairs:
        matched.append((sep, nrm, nama, unit, tgl, pairs))
    else:
        unmatched.append((sep, nrm, nama, unit, tgl, ""))

print()
print("=" * 80)
print(f"A. DITEMUKAN pasangan eklaim (No RM sama, SEP beda): {len(matched)}")
print("=" * 80)
for sep, nrm, nama, unit, tgl, pairs in matched:
    print(f"{sep} | RM:{nrm} | {nama} | {unit} | {tgl}")
    for esep, ejenis, etgl in pairs:
        print(f"    -> eklaim {esep} | jenis={ejenis} | masuk={etgl}")
print()
print("=" * 80)
print(f"B. TIDAK ada klaim eklaim (No RM tidak ditemukan di 00_eklaim): {len(unmatched)}")
print("=" * 80)
for sep, nrm, nama, unit, tgl, _ in unmatched:
    print(f"{sep} | RM:{nrm} | {nama} | {unit} | {tgl}")
