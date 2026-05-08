#
# Copy FITS header from one file to another
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2026 lindner234 <AT> gmail
#

import sirilpy as s
s.ensure_installed("astropy")
s.ensure_installed("PyQt6")

import sys
import os
from astropy.io import fits

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox
)


class CopyHeaderWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Copy FITS Header")
        self.setFixedWidth(500)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.siril = s.SirilInterface()
        try:
            self.siril.connect()
        except s.SirilConnectionError:
            QMessageBox.critical(self, "Error", "Failed to connect to Siril!")
            raise

        self.src_path = None
        self.dst_path = None
        self.CreateWidgets()

    def CreateWidgets(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Source file row
        src_layout = QHBoxLayout()
        src_label = QLabel("Source:")
        src_label.setFixedWidth(65)
        src_layout.addWidget(src_label)

        self.src_edit = QLineEdit()
        src_layout.addWidget(self.src_edit)
        src_browse = QPushButton("Select")
        src_browse.clicked.connect(lambda: self.OnSelectFile("src_path", self.src_edit))
        src_layout.addWidget(src_browse)
        layout.addLayout(src_layout)

        # Destination file row
        dst_layout = QHBoxLayout()
        dst_label = QLabel("Destination:")
        dst_label.setFixedWidth(65)
        dst_layout.addWidget(dst_label)

        self.dst_edit = QLineEdit()
        dst_layout.addWidget(self.dst_edit)
        dst_browse = QPushButton("Select")
        dst_browse.clicked.connect(lambda: self.OnSelectFile("dst_path", self.dst_edit))
        dst_layout.addWidget(dst_browse)
        layout.addLayout(dst_layout)
        layout.addSpacing(15)

        # Copy button
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.copy_btn = QPushButton("Copy Header")
        self.copy_btn.setFixedHeight(30)
        self.copy_btn.setFixedWidth(120)
        self.copy_btn.clicked.connect(self.CopyHeader)
        btn_row.addWidget(self.copy_btn)
        layout.addLayout(btn_row)
        self.setLayout(layout)

    def OnSelectFile(self, file_attr:str, lineedit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select file", "", "FITS files (*.fits *.fit *.fts *.fits.gz *.fit.gz *.fz *.fz2);;All files (*)"
            )
        if path:
            lineedit.setText(os.path.basename(path))
            setattr(self, file_attr, path)

    def CopyHeader(self):
        if not self.src_path or not self.dst_path:
            QMessageBox.warning(self, "Copy FITS Header", "Please select both source and destination files.")
            return

        if self.src_path == self.dst_path:
            QMessageBox.warning(self, "Copy FITS Header", "Source and destination must be different files.")
            return

        try:
            with fits.open(self.src_path) as src_hdul:
                src_header = src_hdul[0].header.copy()

            with fits.open(self.dst_path, mode="update") as dst_hdul:
                dst_hdul[0].header.update(src_header)
                dst_hdul.flush()

            self.siril.log(f"FITS header copied from '{self.src_path}' to '{self.dst_path}'", s.LogColor.GREEN)
            QMessageBox.information(self, "Copy FITS Header", "Header copied successfully.")
            self.close()

        except Exception as e:
            self.siril.log(f"Error copying FITS header: {e}", s.LogColor.SALMON)
            QMessageBox.critical(self, "Copy FITS Header", f"Failed to copy header:\n{e}")


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    try:
        window = CopyHeaderWindow()
    except Exception:
        sys.exit(1)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
