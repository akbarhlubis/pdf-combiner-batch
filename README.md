# PDF Combiner Batch

Gabungkan PDF **bernama sama** dari subfolder berbeda menjadi satu PDF
(contoh: berkas klaim dari `input/eklaim/` + rekam medis dari `input/rm/`
per NOSEP → satu file di `result/`).

Struktur:

```
pdf-combiner-batch/
    combine.py          # skrip utama (mandiri, tanpa dependensi proyek lain)
    requirements.txt    # pypdf
    input/
        eklaim/         # contoh: 0099R0010726V000032.pdf
        rm/             # contoh: 0099R0010726V000032.pdf (nama sama)
    result/             # hasil gabungan (otomatis dibuat)
```

## Instalasi Windows

Kebutuhan:

```text
Windows 10/11
Python 3.10 atau lebih baru (Python 3.13 sudah diuji)
Ghostscript Windows (disarankan)
```

Package Python yang diinstal dari `requirements.txt`:

```text
pypdf       - membaca, validasi, dan fallback PDF
openpyxl    - membuat laporan Excel (.xlsx)
PySide6     - menjalankan GUI desktop
```

### 1. Buka PowerShell di folder aplikasi

1. Buka folder `pdf-combiner-batch` di File Explorer.
2. Klik area kosong di dalam folder sambil menekan `Shift`, lalu klik kanan.
3. Pilih **Open in Terminal** atau **Buka di Terminal**.
4. Pastikan baris perintah menunjukkan folder aplikasi. Jika belum, jalankan:

```powershell
cd "D:\Projects\automation-tools\pdf-combiner-batch"
```

### 2. Pastikan Python tersedia

```powershell
py --version
```

Jika perintah `py` tidak tersedia, gunakan path Python yang dipasang IT,
misalnya `D:\laragon\bin\python\python-3.13\python.exe`.

### 3. Buat virtual environment (`.venv`) dan instal package

`.venv` adalah folder Python khusus aplikasi ini. Instalasi ini cukup dilakukan
satu kali pada setiap komputer, atau diulang bila folder `.venv` dihapus.

Salin-tempel ketiga perintah berikut satu per satu ke PowerShell:

```powershell
cd D:\Projects\automation-tools\pdf-combiner-batch

py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Jika `py -3.13` menampilkan pesan bahwa Python 3.13 tidak ditemukan, tetapi
`py --version` berhasil, gunakan perintah ini sebagai gantinya:

```powershell
py -m venv .venv
```

Jika menggunakan Python Laragon:

```powershell
D:\laragon\bin\python\python-3.13\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. Pasang dan cek Ghostscript

```powershell
where gswin64c
```

Hasil normal menyerupai:

```text
C:\Program Files\gs\gs10.xx.x\bin\gswin64c.exe
```

Tanpa Ghostscript aplikasi masih dapat memakai `pypdf`, tetapi hasil dapat
lebih besar dan beberapa PDF tidak biasa lebih berisiko gagal.

### 5. Verifikasi package Python

```powershell
.\.venv\Scripts\python.exe -c "import pypdf, openpyxl, PySide6; print('Instalasi OK')"
```

## Menjalankan GUI

Setelah instalasi selesai, jalankan dengan double-click:

```text
Jalankan-Combiner-GUI.bat
```

Atau dari PowerShell:

```powershell
.\.venv\Scripts\python.exe combine_gui.py
```

## Cara pakai CLI

```powershell

python combine.py                  # input/ -> result/ (hanya duplikat)
python combine.py --dry-run        # lihat rencana tanpa menulis file
python combine.py --include-unique # proses juga nama yang hanya 1 folder
python combine.py --output "D:\gabungan"
python combine.py --engine gs      # paksa Ghostscript
python combine.py --xlsx           # + laporan Excel (butuh openpyxl)
python combine.py --check          # audit: nama file vs NOSEP di isi PDF
python combine.py --safe           # cek lalu merge; file mismatch dilewati
```

## Perilaku

- Sumber **tidak pernah diubah** — hanya dibaca
- Nama yang sama muncul di >1 folder → digabung (urutan natural sort per path)
- File identik (hash sama) → disalin sekali, tidak digabung dobel
- Nama unik → di-skip (default hanya duplikat; pakai `--include-unique` untuk ikut menyalin)
- Output sudah ada → di-skip (pakai `--force` untuk menimpa)
- Ringkasan: `combine_result.csv` + log `combine.log`
- **Laporan missing**: `combine_missing.csv` mencatat nama file yang ada di
  satu folder tapi tidak di folder lain (atau duplikat dalam folder) —
  misal folder A & B sama-sama 285 file tapi hanya 281 yang cocok
- **Cek nama vs isi**: `python combine.py --check` memverifikasi nama file
  cocok dengan NOSEP di dalam PDF → `combine_check.csv` (deteksi salah
  nama/manusia). File `mismatch` tidak di-rename otomatis; perbaiki manual.
- **Mode aman**: `python combine.py --safe` = cek lalu merge — file yang
  namanya tidak cocok isi **dilewati** (isi pasien A tidak akan masuk ke
  berkas B); salinan revisi dalam satu folder **memakai versi terbaru**
  (by waktu file), tidak menggabung semua versi.

## Engine gabung

- **Ghostscript (utama)** — hasil jauh lebih kecil (kompresi scan), paling
  andal untuk PDF aneh/rusak. Perlu binary `gs` terinstall per OS.
  Deteksi Ghostscript: env `EKLAIM_GS_EXECUTABLE` → PATH → folder install umum
  (`C:\Program Files\gs\gs*\bin\gswin64c.exe`).

  ## Build & distribusi

  Rencana pembuatan executable (Win/Mac/Linux) ada di
  `docs\BUILD_PLAN.md` — berlaku untuk proyek ini dan proyek
  `eklaim-extractor-pdf`.
- **pypdf (opsional)** — hanya fallback bila Ghostscript tidak ada, dan
  untuk validasi jumlah halaman.

Mode `--engine` / env `EKLAIM_COMBINE_ENGINE`:

- `auto` (default): Ghostscript bila tersedia → fallback pypdf
- `gs`: paksa Ghostscript
- `pypdf`: paksa pypdf
