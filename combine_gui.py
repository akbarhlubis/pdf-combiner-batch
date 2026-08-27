from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

import combine
from combine_gui_report import summarize_reports


class CombineWorker(QObject):
    progress = Signal(str, int, int)
    completed = Signal(int)
    failed = Signal(str)

    def __init__(self, arguments: list[str]) -> None:
        super().__init__()
        self.arguments = arguments

    def run(self) -> None:
        try:
            code = combine.main(self.arguments, progress_callback=self.progress.emit)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.completed.emit(code)


class CombineWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.thread: QThread | None = None
        self.worker: CombineWorker | None = None
        self.setWindowTitle("Gabung PDF E-Klaim dan Berkas Digital")
        self.setMinimumSize(820, 660)
        self.last_check_only = True
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        title = QLabel("Gabung PDF E-Klaim dan Berkas Digital")
        title.setObjectName("title")
        layout.addWidget(title)
        layout.addWidget(QLabel("Pilih folder E-Klaim dan Berkas Digital yang akan dipasangkan berdasarkan nomor SEP."))

        form_group = QGroupBox("1. Pilih Folder Sumber")
        form = QFormLayout(form_group)
        self.eklaim_field = QLineEdit()
        self.berkas_digital_field = QLineEdit()
        self.output_field = QLineEdit(str(Path(__file__).resolve().parent / "result"))
        form.addRow("Folder E-Klaim", self._folder_row(self.eklaim_field, "Pilih folder E-Klaim"))
        form.addRow("Folder Berkas Digital", self._folder_row(self.berkas_digital_field, "Pilih folder Berkas Digital"))
        form.addRow("Folder hasil/laporan", self._folder_row(self.output_field, "Pilih folder hasil"))
        layout.addWidget(form_group)

        options_group = QGroupBox("2. Atur Proses")
        options = QFormLayout(options_group)
        self.engine = QComboBox()
        self.engine.addItem("Otomatis - Ghostscript utama", "auto")
        self.engine.addItem("Ghostscript saja", "gs")
        self.engine.addItem("pypdf saja", "pypdf")
        self.xlsx = QCheckBox("Buat laporan Excel (.xlsx)")
        self.include_unique = QCheckBox("Sertakan file tanpa pasangan")
        self.force = QCheckBox("Timpa hasil lama")
        self.force_verify = QCheckBox("Cek ulang semua file tanpa cache")
        options.addRow("Engine PDF", self.engine)
        options.addRow("Keamanan", QLabel("Mode aman aktif: file mismatch ditahan."))
        options.addRow("", self.xlsx)
        options.addRow("", self.include_unique)
        options.addRow("", self.force)
        options.addRow("", self.force_verify)
        layout.addWidget(options_group)

        buttons = QHBoxLayout()
        self.check_button = QPushButton("Periksa Berkas")
        self.check_button.clicked.connect(lambda: self._start(check_only=True))
        self.combine_button = QPushButton("Mulai Penggabungan")
        self.combine_button.clicked.connect(lambda: self._start(check_only=False))
        buttons.addWidget(self.check_button)
        buttons.addWidget(self.combine_button)
        layout.addLayout(buttons)
        section = QLabel("3. Periksa dan Gabungkan")
        section.setObjectName("section")
        layout.addWidget(section)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)
        self.status = QLabel("Siap.")
        layout.addWidget(self.status)
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMaximumHeight(110)
        self.summary.setPlaceholderText("Ringkasan pemeriksaan dan penggabungan tampil di sini.")
        layout.addWidget(self.summary)
        self.activity = QPlainTextEdit()
        self.activity.setReadOnly(True)
        self.activity.document().setMaximumBlockCount(200)
        layout.addWidget(self.activity, 1)
        open_button = QPushButton("Buka Folder Hasil dan Laporan")
        open_button.clicked.connect(self._open_output)
        layout.addWidget(open_button)
        self.setCentralWidget(root)

    def _folder_row(self, field: QLineEdit, title: str) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(field, 1)
        button = QPushButton("Pilih")
        button.clicked.connect(lambda: self._choose_folder(field, title))
        layout.addWidget(button)
        return row

    def _choose_folder(self, field: QLineEdit, title: str) -> None:
        folder = QFileDialog.getExistingDirectory(self, title)
        if folder:
            field.setText(folder)

    def _arguments(self, check_only: bool) -> list[str]:
        args = ["--eklaim-dir", self.eklaim_field.text().strip(),
                "--berkas-digital-dir", self.berkas_digital_field.text().strip(),
                "--output", self.output_field.text().strip(),
                "--engine", self.engine.currentData()]
        if check_only:
            args.append("--check")
        else:
            args.append("--safe")
        if self.xlsx.isChecked() and not check_only:
            args.append("--xlsx")
        if self.include_unique.isChecked() and not check_only:
            args.append("--include-unique")
        if self.force.isChecked() and not check_only:
            args.append("--force")
        if self.force_verify.isChecked():
            args.append("--force-verify")
        return args

    def _start(self, check_only: bool) -> None:
        eklaim_dir = Path(self.eklaim_field.text().strip())
        berkas_dir = Path(self.berkas_digital_field.text().strip())
        if not eklaim_dir.is_dir() or not berkas_dir.is_dir() or not self.output_field.text().strip():
            QMessageBox.warning(self, "Input belum valid", "Pilih folder E-Klaim, Berkas Digital, dan hasil yang valid.")
            return
        if eklaim_dir.resolve() == berkas_dir.resolve():
            QMessageBox.warning(self, "Folder sumber sama", "Folder E-Klaim dan Berkas Digital harus berbeda.")
            return
        self.last_check_only = check_only
        self.check_button.setEnabled(False)
        self.combine_button.setEnabled(False)
        self.progress.setValue(0)
        self.activity.clear()
        self.summary.clear()
        self.thread = QThread(self)
        self.worker = CombineWorker(self._arguments(check_only))
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._progress)
        self.worker.completed.connect(self._completed)
        self.worker.failed.connect(self._failed)
        self.worker.completed.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self._finished)
        self.thread.start()

    def _progress(self, message: str, current: int, total: int) -> None:
        self.progress.setValue(int(current * 100 / max(total, 1)))
        self.status.setText(message)
        self.activity.appendPlainText(message)

    def _completed(self, code: int) -> None:
        self.progress.setValue(100 if code == 0 else self.progress.value())
        self.status.setText("Selesai." if code == 0 else f"Selesai dengan kode {code}.")
        if code == 0:
            self.summary.setPlainText(summarize_reports(Path(self.output_field.text().strip()), self.last_check_only))

    def _failed(self, message: str) -> None:
        self.status.setText("Proses gagal.")
        self.activity.appendPlainText(f"Gagal: {message}")

    def _finished(self) -> None:
        self.check_button.setEnabled(True)
        self.combine_button.setEnabled(True)
        if self.worker:
            self.worker.deleteLater()
        if self.thread:
            self.thread.deleteLater()
        self.worker = None
        self.thread = None

    def _open_output(self) -> None:
        folder = Path(self.output_field.text().strip())
        if folder.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


def main() -> int:
    app = QApplication(sys.argv)
    window = CombineWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
