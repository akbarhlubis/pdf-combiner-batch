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

## Cara pakai

```bash
pip install -r requirements.txt

python combine.py                  # input/ -> result/ (hanya duplikat)
python combine.py --dry-run        # lihat rencana tanpa menulis file
python combine.py --include-unique # proses juga nama yang hanya 1 folder
python combine.py --output "D:\gabungan"
python combine.py --engine gs      # paksa Ghostscript
python combine.py --xlsx           # + laporan Excel (butuh openpyxl)
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
