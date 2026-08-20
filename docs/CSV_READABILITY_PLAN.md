# Implementation Plan: Readability Audit CSV (combine + extractor)

> **Status:** Keputusan dijawab 2026-08-20 (lihat Open Questions) + tambahan
> fitur laporan missing di combine. Siap diimplementasikan.
> Berlaku untuk `pdf-combiner-batch/combine.py` dan
> `eklaim-extractor-pdf/extract_pdf.py`.
> Terakhir diperbarui: 2026-08-20.

## Overview

CSV hasil kedua proyek saat ini fungsional tapi kurang ramah pembaca
(terutama dibuka di Excel oleh user awam):

- `combine_result.csv` — `utf-8` **tanpa BOM** (huruf rusak di Excel
  Indonesia), header `name,status,pages,detail` (snake_case, tanpa NOSEP
  terpisah), status tanpa penjelasan bahasa Indonesia.
- `audit.csv` (extractor) — sudah `utf-8-sig`, tapi **34 kolom** snake_case
  berurutan sesuai urutan kemunculan label di PDF (campur identitas, rawat,
  klinis, tarif), nilai mentah kadang kotor (`'Rp 188,700.00'`), status hanya
  kode (`extracted/already_done/failed`).

Tujuan: CSV **mudah dibaca manusia & Excel**, tetap aman untuk konsumen
program (kunci `nomor_sep`/`name` tidak berubah), tanpa menambah kewajiban
dependensi — kecuali opsi xlsx yang disetujui.

## Architecture Decisions

| # | Keputusan | Alasan |
|---|---|---|
| AD1 | **CSV tetap format utama**, header manusiawi via mapping (`NOMOR_SEP` → "Nomor SEP") | Readability terbesar dari header + urutan; konsumen DictReader (akses by key) tidak patah |
| AD2 | **Urutan kolom dikelompokkan**: identifier → status/keterangan → file → identitas → rawat → klinis → tarif → meta | Yang sering dilihat (SEP, status, keterangan) di depan; yang teknis di belakang |
| AD3 | **Status tetap kode stabil** (`extracted`, `merged`, ...) + **kolom `keterangan`** berbahasa Indonesia | Kode stabil utk konsumen program; keterangan utk pembaca awam. Tidak mengubah nilai status yang sudah ada |
| AD4 | **`utf-8-sig` (BOM) di kedua proyek** (combine masih `utf-8`) | BOM = Excel Indonesia mengenali UTF-8 tanpa mojibake |
| AD5 | **Nilai tetap mentah, hanya di-trim** (jangan ubah `'Rp 188,700.00'`, `inacbg`, tanggal DD/MM/YYYY) | Hindari risiko salah format uang/tanggal; kolom ISO sudah tersedia utk konsumen |
| AD6 | **Helper kecil di-copy per proyek** (bukan modul bersama antar proyek) | Kedua proyek harus mandiri (rencana build PyInstaller `--onefile`); duplikasi ±30 baris lebih aman daripada import lintas proyek |
| AD7 | **xlsx OPSIONAL** (`--xlsx`, openpyxl) — DISETUJUI | CSV tetap jalan tanpa dep baru; xlsx = bonus keterbacaan (frozen header, filter, warna status, sheet ringkasan) |
| AD8 | **combine: laporan berkas missing** (`combine_missing.csv`) | Kasus nyata: folder A & B sama-sama 285 file tapi isinya beda → hanya 281 yang match. Laporan mencatat SEP yang ada di satu folder tapi tidak di folder lain (dan duplikat dalam folder) |

## Task List

### Phase 1 — CSV rapi (wajib, tanpa dep baru)

**Task 1: combine — header manusiawi + BOM + kolom `nosep` & `keterangan`** (XS-S, 1 file)
- **Desc:** Di `_write_result()`: encoding `utf-8` → `utf-8-sig`. Kolom jadi
  `name, nosep, status, keterangan, pages, detail` dengan header Indonesia
  ("Nama File", "NOSEP", "Status", "Keterangan", "Halaman", "Detail").
  `nosep` = stem filename (SEP tanpa ekstensi); `keterangan` = terjemahan
  status: `merged`→"Berhasil digabung", `copied`→"Disalin (1 folder)",
  `identical`→"File identik — disalin sekali", `skipped`→"Nama unik —
  dilewati", `exists_skipped`→"Output sudah ada — dilewati", `failed`→"Gagal".
- **AC:** `combine_result.csv` ber-BOM, header Indonesia, 2 kolom baru,
  nilai status (kunci internal) tidak berubah.
- **Verifikasi:** jalankan pada input sampel kecil → baca CSV via `csv.DictReader`
  (BOM ok, key `nosep`/`keterangan` ada, hitung status benar); buka di Excel
  manual tanpa mojibake.
- **Files:** `combine.py`.

**Task 2: extractor — header manusiawi + urutan kolom terkelompok + `keterangan`** (S, 1 file)
- **Desc:** Di main(): `CSV_COLUMNS` diurut ulang berkelompok (SEP → status →
  keterangan → file/halaman → identitas → rawat → klinis → tarif → meta).
  Header via mapping (`nomor_sep`→"Nomor SEP", `total_tarif`→"Total Tarif",
  dst.). Tambah kolom `keterangan`: `extracted`→"Berhasil diekstrak",
  `already_done`→"Sudah ada — dilewati", `failed`→"Gagal". Encoding tetap
  `utf-8-sig`. Nilai field tetap mentah (hanya `" ".join(value.split())` seperti
  sekarang). **Keputusan: tetap semua 34 field.**
- **AC:** `audit.csv` header Indonesia, urutan baru, kolom `keterangan` terisi,
  `nomor_sep` tetap kunci, jumlah kolom 35.
- **Verifikasi:** `--limit 5 --force` → baca CSV via DictReader (header, urutan,
  nilai keterangan); buka di Excel.
- **Files:** `extract_pdf.py`.

**Task 2b: combine — laporan berkas missing antar folder** (S-M, 1 file)
- **Desc:** Fungsi `missing_report()`: sumber = anak langsung folder input
  (mis. `input/E-Klaim`, `input/Berkas Digital`). Untuk tiap nama file yang
  tidak lengkap (ada di sebagian sumber / duplikat dalam satu sumber) → baris
  matriks `nosep, nama_file, <kolom per sumber: ada/TIDAK>, keterangan`
  (keterangan: "tidak ada di: X" dan/atau "duplikat di: Y(2x)"). Ringkasan:
  jumlah file per sumber, nama union, nama lengkap (ada di semua sumber), nama
  bermasalah. Tulis `combine_missing.csv` (`utf-8-sig`).
- **AC:** kasus A=285, B=285, match 281 → 8 baris masalah (4 hanya di A, 4
  hanya di B); ringkasan benar; duplikat dalam folder terdeteksi.
- **Verifikasi:** fixture 2 folder (A: sep1-3, B: sep1,2,4) → CSV berisi sep3
  & sep4 sebagai masalah; buka di Excel.
- **Files:** `combine.py`.

### Checkpoint: CSV rapi
- [ ] Kedua CSV ber-BOM, header Indonesia, keterangan terisi, kunci tidak berubah

### Phase 2 — Opsional: laporan Excel `--xlsx` (butuh keputusan OQ2)

**Task 3: `--xlsx` di combine + extractor (openpyxl)** (M, 2 file + requirements)
- **Desc:** Flag `--xlsx` → tulis `combine_result.xlsx` / `audit.xlsx`:
  - combine: sheet "Hasil" (header bold + frozen baris 1, autofilter, lebar
    kolom auto (cap ±40), fill warna per status: hijau sukses / kuning skip /
    merah gagal); sheet "Ringkasan" (jumlah per status + ringkasan missing);
    sheet "Missing" (matriks missing bila ada).
  - extractor: sheet "Hasil" + "Ringkasan" (jumlah per status).
  Import openpyxl dibungkus try/except — tanpa openpyxl → warning & tetap
  tulis CSV saja. Tambah `openpyxl>=3.1` (komentar "opsional") di
  `requirements.txt` kedua.
- **AC:** `--xlsx` menghasilkan file valid (2-3 sheet); tanpa openpyxl CSV
  tetap jalan.
- **Verifikasi:** buka via openpyxl (sheet benar, hitung baris = ringkasan);
  jalankan tanpa openpyxl terpasang (simulasi) → warning + CSV normal.
- **Files:** `combine.py`, `extract_pdf.py`, `requirements.txt` (×2).

### Checkpoint: Laporan Excel
- [ ] xlsx terbuka rapi (frozen/filter/warna/ringkasan) · fallback CSV normal

## Risks and Mitigations

| Risk | Impact | Mitigasi |
|---|---|---|
| Header/urutan kolom berubah mematahkan konsumen CSV lama | Sedang | Kunci (`nomor_sep`, `name`) tidak berubah; konsumen DictReader aman; dokumentasikan perubahan header di README |
| Openpyxl jadi dep baru | Rendah | Opsional & try/except; CSV tetap jalan tanpa openpyxl; auto-bundle di PyInstaller bila dipakai |
| Status dikira "bahasa Indonesia" oleh konsumen | Rendah | AD3: nilai status TIDAK diubah, hanya ada kolom tambahan `keterangan` |

## Open Questions — SUDAH DIJAWAB (2026-08-20)

1. **Status**: kode stabil + kolom `keterangan` (rekomendasi) — ✅ dipilih.
2. **xlsx**: perlu output Excel `.xlsx` — ✅ dipilih (openpyxl, opsional).
3. **Header**: bahasa Indonesia untuk semua header kolom — ✅ dipilih.
4. **Kolom extractor**: tetap semua 34 field — ✅ dipilih.

**Tambahan user (2026-08-20):** laporan berkas missing di combine
(`combine_missing.csv` + sheet "Missing" di xlsx + ringkasan) — lihat Task 2b.
