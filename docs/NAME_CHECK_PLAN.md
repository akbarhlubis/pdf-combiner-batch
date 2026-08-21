# Implementation Plan: Verifikasi Nama File vs NOSEP Isi PDF (combine)

> **Status:** Keputusan dijawab 2026-08-20 (lihat Open Questions). Siap diimplementasikan.
> Berlaku untuk `pdf-combiner-batch/combine.py`.
> Terakhir diperbarui: 2026-08-20.

## Overview

Audit data nyata menemukan **1 kesalahan penamaan manusia**:
`01_berkas digital\Tanggal 4\IGD TGL 4 JULI\0099R0010726V000302.pdf`
— nama file `000302`, tapi isi PDF berisi SEP **`0099R0010726V000314`**.
Dampaknya: V000302 muncul sebagai "RM tanpa eklaim" palsu DAN V000314
muncul sebagai "eklaim tanpa RM" palsu (2 masalah, 1 akar penyebab).
File gabungan V000314 tidak pernah dibuat.

Tujuan: combine memverifikasi **nama file = NOSEP di dalam isi PDF** sebelum
merge. File yang tidak cocok **tidak ikut merge** dan dilaporkan jelas —
mencegah isi pasien A tersimpan di berkas pasien B.

## Architecture Decisions

| # | Keputusan | Alasan |
|---|---|---|
| AD1 | **SEP di isi PDF = ground truth** (regex `\d{4}[A-Za-z]\d{7}[A-Za-z]\d{6}`, sama dengan extractor) | Nama file bisa salah ketik manusia; isi tidak |
| AD2 | **Verifikasi via flag `--check`** (bukan default-on — performa) + cache incremental | Run combine normal tetap cepat; `--check` untuk audit saat dibutuhkan; cache membuat re-check < 10 detik |
| AD3 | **File `mismatch` DILEWATKAN dari merge** + log peringatan keras + tercatat di laporan | Jangan pernah menggabung isi yang salah di bawah nama yang salah |
| AD4 | **Cache incremental** (path, size, mtime → hasil cek) disimpan `combine_check_cache.json` | 2.800+ PDF = 3–7 menit; cache membuat run ulang & watcher hanya cek file baru/berubah |
| AD5 | **Laporan `combine_check.csv`** (`utf-8-sig`, format konsisten proyek): file, nama_sep, isi_sep, status, keterangan | Bisa dibuka Excel; jadi dasar audit |
| AD6 | **Tidak ada auto-rename secara default** — report + saran; opsi `--auto-rename` dipertimbangkan (OQ1) | Rename otomatis bisa salah; butuh keputusan eksplisit |

Status per file:
- `ok` — nama cocok dengan SEP di isi
- `mismatch` — nama ≠ isi (kedua nilai dicatat)
- `no_sep` — ada teks tapi tidak ada pola SEP (format beda? halaman judul?)
- `no_text` — PDF scan tanpa lapisan teks (tidak bisa diverifikasi via teks)

## Task List

### Phase 1 — Verifikasi nama ↔ isi

**Task 1: fungsi `verify_names()` + flag `--check`/`--check-only` + laporan** (M, 1 file)
- **Desc:** Di `combine.py`: scan semua PDF `input/` (rglob), ekstrak teks
  (pypdf, reuse `page_count`-style try/except), cari SEP di isi, bandingkan
  dengan `Path.stem` (case-insensitive). Tulis `combine_check.csv` (kolom:
  `File, Nama File (SEP), SEP di Isi, Status, Keterangan, Ukuran, Mtime`).
  Ringkasan di log: total / ok / mismatch / no_sep / no_text.
  `--check-only` = cek saja, tanpa merge. `--no-verify` = lewati verifikasi
  (kecepatan, tidak disarankan).
- **AC:** audit data nyata → 1 `mismatch` (V000302→V000314) terdeteksi;
  `--check-only` tidak menulis apa pun ke `result/`.
- **Verifikasi:** `python combine.py --check-only` → CSV berisi 1 mismatch;
  `grep` log ringkasan; buka CSV di Excel.

**Task 2: integrasi ke alur merge — mismatch dilewatkan** (S, 1 file)
- **Desc:** Sebelum `process_group`, grup nama yang punya file `mismatch`
  → file tersebut di-remove dari daftar merge (tidak ikut digabung) + log
  `[SKIP] nama tidak cocok dengan isi: ... (isi=SEP_X)`. Ringkasan akhir
  menampilkan jumlah file dilewati.
- **AC:** run combine dengan 1 mismatch nyata → tidak ada output untuk
  V000302; V000314 tidak merge sampai file diperbaiki; laporan tetap ditulis.
- **Verifikasi:** `python combine.py --xlsx` → log skip; `result/` tidak
  memuat V000302.

### Checkpoint: Deteksi & proteksi
- [ ] 1 mismatch terdeteksi · file mismatch tidak ikut merge · CSV benar

### Phase 2 — Performa & perbaikan data nyata

**Task 3: cache incremental** (S, 1 file)
- **Desc:** Simpan hasil verifikasi per (path, size, mtime) ke
  `combine_check_cache.json`; hanya baca ulang file yang berubah/baru.
  `--force-verify` untuk full re-check (anggap cache basi).
- **AC:** run pertama 3–7 menit, run kedua (tanpa perubahan input) < 10 detik;
  tambah 1 file baru → hanya file itu yang diverifikasi.
- **Verifikasi:** ukur waktu 2 run; ubah 1 file → cache hanya re-check 1 file.

**Task 4: perbaiki 1 file nyata + re-run** (XS, butuh konfirmasi user)
- **Desc:** Rename `...\0099R0010726V000302.pdf` → `0099R0010726V000314.pdf`
  (isi sudah terbukti V000314), lalu `combine.py --xlsx --force` untuk V000314.
- **AC:** missing report turun: 91→90 (RM tanpa eklaim) dan 2→1 (eklaim tanpa RM);
  `result/0099R0010726V000314.pdf` terbuat.
- **Verifikasi:** audit ulang 0 mismatch; cek file hasil.
- **Catatan:** lakukan hanya setelah user setuju rename.

### Checkpoint: Lengkap
- [ ] 0 mismatch · cache cepat · missing report akurat · V000314 ter-combine

## Risks and Mitigations

| Risk | Impact | Mitigasi |
|---|---|---|
| Verifikasi 2.800+ PDF lambat | Sedang | AD4 cache incremental + `--no-verify` untuk kasus darurat |
| PDF scan tanpa teks (`no_text`) tidak bisa diverifikasi | Sedang | Dicatat + dilewatkan dari verifikasi (bukan di-block); OCR di luar scope |
| Cache basi (file berubah tapi size+mtime sama — jarang) | Rendah | `--force-verify`; watcher nanti bisa bandingkan hash bila perlu |
| Auto-rename keliru | Tinggi (bila diaktifkan) | AD6: default report-only; `--auto-rename` hanya bila OQ1 disetujui + dry-run |
| File mismatch diabaikan tapi user tidak tahu | Sedang | Peringatan log keras + `combine_check.csv` + ringkasan "N file dilewati" |

## Open Questions — SUDAH DIJAWAB (2026-08-20)

1. **Auto-rename**: TIDAK — cukup report + skip (file mismatch tidak di-rename otomatis). ✅
2. **`no_text` (scan)**: tetap boleh di-merge + ditandai di laporan (tidak di-block). ✅
3. **Default-on**: TIDAK — verifikasi hanya saat flag `--check` (performa run biasa tetap cepat),
   dengan cache incremental (`combine_check_cache.json`) agar re-check ringan. ✅

**Keputusan tambahan (2026-08-20):**
- Mode **`--safe`** ditambahkan: verifikasi → merge, file `mismatch` DILEWATI
  dari merge (batch tetap jalan), hasil cek tetap ditulis ke `combine_check.csv`.
- Perbaikan duplikat/revisi di `process_group`: bila dalam satu folder sumber
  ada salinan nama sama beda isi → **dipakai versi terbaru (mtime)**, bukan
  menggabung semua versi (bug: hasil 25 halaman padahal harusnya 13).
