# Implementation Plan: Build Executable Win/Mac/Linux (PyInstaller)

> **Status:** Menunggu konfirmasi keputusan (lihat Open Questions di bawah).
> Berlaku untuk **dua proyek**: `pdf-combiner-batch` (gabung PDF) dan
> `eklaim-extractor-pdf` (pecah PDF per SEP).
> `eklaim-web-batch` (download) **tidak** termasuk scope build ini.
> Terakhir diperbarui: 2026-08-20.

## Overview

Membangun kedua proyek Python menjadi executable mandiri ala `go build`:

| Proyek | Hasil build | Target |
|---|---|---|
| `pdf-combiner-batch` | 1 file exe/binary (`gabung-pdf`) | Win + Mac + Linux |
| `eklaim-extractor-pdf` | 1 file exe/binary (`ekstrak-sep`) | Win + Mac + Linux |

User awam cukup menjalankan executable — tanpa perlu install Python.
**Dua rute deliver:** (a) script build per-OS (tanpa GitHub), (b) opsional
GitHub Actions matrix (butuh repo + push).

Kedua proyek ringan — tanpa browser, tanpa wizard, tanpa kredensial —
sehingga strategi build-nya identik: PyInstaller `--onefile` + pypdf
ter-bundle + Ghostscript eksternal opsional (auto-detect).

## Architecture Decisions

| # | Keputusan | Alasan |
|---|---|---|
| D1 | **PyInstaller** (bukan Nuitka/cx_Freeze) | Paling matang, dokumentasi luas; kedua proyek kecil sehingga Nuitka tidak memberi keuntungan berarti |
| D2 | **Keduanya `--onefile`** | combine & extractor mandiri tanpa data bundle → satu file exe cepat start, mudah didistribusikan (beda dengan proyek eklaim yang berat) |
| D3 | **Refactor path dulu: helper `app_dir()`** | PyInstaller frozen: `__file__` menunjuk ke folder temp ekstraksi. Semua data user (logs/, input/, result/, `combine_result.csv`, `audit.csv`) harus relatif ke **lokasi exe** (`sys.executable`), bukan `__file__`. Tanpa ini build rusak di runtime |
| D4 | **pypdf ter-bundle; Ghostscript eksternal (auto-detect)** | Extractor **wajib** pypdf (baca teks + slicing halaman, hard dependency). Combine butuh pypdf hanya saat GS tidak ada (fallback). GS tidak praktis di-bundle (native, per-OS) → deteksi: env `EKLAIM_GS_EXECUTABLE` → PATH → folder install umum |
| D5 | **Build per-OS (tidak ada cross-compile)** — script `build_windows.bat`, `build_linux.sh`, `build_macos.sh`; CI matrix opsional | PyInstaller hanya build untuk OS tempat ia jalan |
| D6 | **Versi & ikon opsional**: `--version`, metadata Windows (version info), icon | Profesional & memudahkan IT |

## Task List

### Phase 0 — Foundation: path refactor (WAJIB sebelum build)

**Task 1: combine — refactor path `app_dir()`** (XS, 1 file)
- **Desc:** `combine.py` `PROJECT_DIR` → `app_dir()` (`sys.frozen` → `Path(sys.executable).parent`, else `Path(__file__).parent`). `combine.log`, `combine_result.csv`, default `input/`/`result/` ikut relatif ke exe.
- **AC:** `--dry-run` di source-mode tetap sama; frozen mode menulis di samping exe.
- **Verifikasi:** `python combine.py --dry-run`.
- **Files:** `combine.py`.

**Task 2: extractor — refactor path `app_dir()`** (XS, 1 file)
- **Desc:** `extract_pdf.py` `PROJECT_DIR` → `app_dir()`; `extract.log`, default `result/` ikut relatif ke exe.
- **AC:** `--dry-run` di source-mode tetap sama; frozen mode menulis di samping exe.
- **Verifikasi:** `python extract_pdf.py --input <file> --dry-run`.
- **Files:** `extract_pdf.py`.

### Checkpoint: Path Foundation
- [ ] combine dry-run OK · extractor dry-run OK · tidak ada `Path(__file__)` untuk data user tersisa

### Phase 1 — Combine build (proyek kecil → fail fast)

**Task 3: spec + script build combine** (S, 2-3 file)
- **Desc:** `combine.spec` (onefile, name `gabung-pdf`, bundle pypdf, version info opsional) + `build_windows.bat` + `build_linux.sh`/`build_macos.sh`.
- **AC:** build jalan di Windows → `dist/gabung-pdf.exe`.
- **Verifikasi:** build sukses; exe ada.

**Task 4: tes exe combine di Windows** (S)
- **Desc:** Jalankan exe: `--dry-run`, lalu merge nyata pada 10 PDF sampel. Cek deteksi Ghostscript tetap jalan di frozen mode.
- **AC:** dry-run benar; 5 file merged valid; tanpa GS (simulasi env kosong) → fallback pypdf tersalur dengan benar.
- **Verifikasi:** hasil `result/` + `combine_result.csv`; halaman sesuai.
- **Files:** tidak ada (validasi).

**Task 5: build Linux/macOS (script siap; eksekusi user/CI)** (S)
- **Desc:** Pastikan `build_*.sh` benar (venv, pip install, pyinstaller, output `dist/gabung-pdf`). Tidak bisa diverifikasi dari Windows → tandai "perlu build di OS target".
- **AC:** script deterministik; dokumentasi langkah.

### Checkpoint: Combine Buildable
- [ ] exe Windows teruji end-to-end · script OS lain siap

### Phase 2 — Extractor build

**Task 6: spec + script build extractor** (S, 2-3 file)
- **Desc:** `extractor.spec` (onefile, name `ekstrak-sep`, bundle pypdf, version info opsional) + `build_windows.bat` + `build_*.sh`.
- **AC:** build menghasilkan `dist/ekstrak-sep.exe`.
- **Verifikasi:** build sukses; exe ada.

**Task 7: tes exe extractor di Windows** (S-M)
- **Desc:** Copy exe ke folder bersih + 1 PDF sampel → `--dry-run` → `--limit 5` → full kecil. Cek GS terdeteksi (output ±100 KB) & fallback pypdf (±400 KB) benar; `audit.csv` ditulis di samping exe.
- **AC:** file per-SEP valid `%PDF`; resume (`already_done`) OK; folder mode month/date benar.
- **Verifikasi:** file + `audit.csv` di samping exe; halaman sesuai sumber.
- **Files:** tidak ada (validasi).

**Task 8: build Linux/macOS (script siap; note path GS)** (S)
- **Desc:** Script build + dokumentasi: GS di Linux/Mac via `apt`/`brew` (`gs`), path deteksi beda; pypdf fallback tetap jalan tanpa GS.
- **AC:** script deterministik; dokumentasi jelas.

### Checkpoint: Extractor Buildable
- [ ] exe Windows teruji end-to-end · script OS lain siap

### Phase 3 — Distribusi & kemasan

**Task 9: panduan user awam** (S)
- **Desc:** Seksi "Build & distribusi" di README kedua proyek + contoh pakai double-click (`.bat`/`.sh`) bila perlu.
- **AC:** user awam bisa: copy exe → letakkan input → jalankan.

**Task 10 (opsional): GitHub Actions matrix** (M, butuh keputusan OQ1)
- **Desc:** Umbrella repo `automation-tools` (2 proyek) + push GitHub; workflow matrix `[windows-latest, ubuntu-latest, macos-latest]` → artifact per OS.
- **AC:** 3 artifact ter-download; smoke test otomatis minimal.

### Checkpoint: Rilis
- [ ] Win teruji manual · Mac/Linux dibangun (CI/user) · panduan lengkap

## Risks and Mitigations

| Risk | Impact | Mitigasi |
|---|---|---|
| Path `__file__` salah di onefile | Tinggi | Task 1-2 wajib sebelum build; helper `app_dir()` teruji |
| Target tanpa Ghostscript → file hasil lebih besar (combine ±8×, extractor ±4×) | Sedang | pypdf ter-bundle sebagai fallback otomatis + pesan error jelas; OQ3 |
| Tidak ada cross-compile | Sedang | Script per-OS; CI matrix untuk 3 OS sekaligus |
| Windows Defender/AV memblokir exe PyInstaller | Sedang | Dokumentasi whitelist; opsional signing |
| macOS Gatekeeper (exe dari internet diblokir) | Sedang | Instruksi "buka dengan klik kanan" / notarisasi |
| Onefile + PDF besar → RAM tinggi saat GS re-encode | Rendah | PDF e-Klaim kecil (KB–MB); cukup untuk skala rumah sakit |

## Open Questions (butuh keputusan)

1. **CI otomatis**: mau **GitHub Actions** (perlu umbrella repo + push, build 3 OS otomatis) atau **cukup script build lokal** (build manual per OS)?
2. **Ikon/versi**: perlu ikon aplikasi + nomor versi (`--version`) untuk tiap build?
3. **Target tanpa GS**: fallback pypdf (file hasil lebih besar) diterima di mesin tanpa Ghostscript, atau IT rumah sakit akan install GS di tiap mesin?

## Catatan Struktur Jangka Panjang (rekomendasi)

Saat siap rilis: jadikan `D:\Projects\automation-tools\` sebagai umbrella git repo
(dua proyek + `docs/` bersama). Plan ini tinggal dipindah ke
`automation-tools\docs\BUILD_PLAN.md`; CI build dua proyek sekaligus dari satu repo.
