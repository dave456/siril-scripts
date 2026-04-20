#
# Tool to align files using Siril's alignment algorithms
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2026 lindner234 <AT> gmail
#

import sirilpy as s
s.ensure_installed("PyQt6")

import sys
import os
import shutil
import threading

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal

ALIGN_WORKING_DIR = "align_working"

class SirilAlignInterface(QWidget):
    _set_controls_enabled = pyqtSignal(bool)
    _show_info = pyqtSignal(str)
    _show_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Alignment Tool")
        self.setFixedWidth(650)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.files_to_align = []

        # Initialize Siril connection
        self.siril = s.SirilInterface()
        try:
            self.siril.connect()
        except s.SirilConnectionError:
            QMessageBox.critical(self, "Error", "Failed to connect to Siril")
            self.close()
            return

        self._set_controls_enabled.connect(self._on_set_controls_enabled)
        self._show_info.connect(lambda msg: QMessageBox.information(self, "Done", msg))
        self._show_error.connect(lambda msg: QMessageBox.critical(self, "Error", msg))

        self.CreateWidgets()

    def CreateWidgets(self):
        """Create the GUI widgets for our alignment tool."""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Add/remove buttons
        add_remove_row = QHBoxLayout()
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.AddFiles)
        add_remove_row.addWidget(self.add_button)

        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self.RemoveFiles)
        add_remove_row.addWidget(self.remove_button)
        add_remove_row.addStretch()
        layout.addLayout(add_remove_row)

        # File list group box
        files_box = QGroupBox(" Files to Align ")
        files_layout = QVBoxLayout()
        files_box.setLayout(files_layout)
        files_box.setContentsMargins(8, 23, 8, 13)

        self.file_listbox = QListWidget()
        self.file_listbox.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        files_layout.addWidget(self.file_listbox)
        layout.addWidget(files_box)

        # Align button
        self.align_button = QPushButton("Align Images")
        self.align_button.setFixedWidth(100)
        self.align_button.clicked.connect(self.AlignFiles)
        layout.addWidget(self.align_button)

    def AddFiles(self):
        """Callback for add button - open file dialog to select files to align."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select files to align",
            "",
            "FITS files (*.fit *.fits *.fts *.fits.gz *.fit.gz *.fz *.fz2);;All files (*)",
        )

        for file in files:
            if file in self.files_to_align:
                continue  # avoid duplicates
            self.files_to_align.append(file)
            item = QListWidgetItem(os.path.basename(file))
            item.setToolTip(file)
            item.setData(Qt.ItemDataRole.UserRole, file)
            self.file_listbox.addItem(item)

    def RemoveFiles(self):
        """Callback for remove button - remove selected files from list."""
        selected_items = self.file_listbox.selectedItems()
        for item in selected_items:
            filepath = item.data(Qt.ItemDataRole.UserRole)
            if filepath in self.files_to_align:
                self.files_to_align.remove(filepath)
            row = self.file_listbox.row(item)
            self.file_listbox.takeItem(row)

    def AlignFiles(self):
        """Callback for align button - perform alignment on selected files."""
        if not self.files_to_align:
            QMessageBox.warning(self, "Warning", "Please add one or more files to align")
            return

        input_files = [f for f in self.files_to_align if os.path.isfile(f)]

        if not input_files:
            QMessageBox.warning(self, "Warning", "No valid files found")
            return

        self._set_controls_enabled.emit(False)
        threading.Thread(target=lambda: self._AlignFilesWorker(input_files), daemon=True).start()

    def _on_set_controls_enabled(self, enabled):
        self.align_button.setEnabled(enabled)
        self.add_button.setEnabled(enabled)
        self.remove_button.setEnabled(enabled)

    def _AlignFilesWorker(self, input_files):
        old_cwd = os.getcwd()

        try:
            # create our working directory
            if not os.path.exists(ALIGN_WORKING_DIR):
                os.mkdir(ALIGN_WORKING_DIR)

            # create siril sequence of files to align
            seqnum = 1
            for file in input_files:
                shutil.copyfile(file, f"{ALIGN_WORKING_DIR}/align_{seqnum:04d}.fits")
                seqnum += 1

            # do some siril magic
            self.siril.cmd("cd", ALIGN_WORKING_DIR)
            self.siril.cmd("register", "align", "-2pass")
            self.siril.cmd("seqapplyreg", "align", "-framing=min")
            self.siril.cmd("cd", "..")

            # rename our newly aligned files using original names and -aligned suffix
            seqnum = 1
            for file in input_files:
                aligned_filename = os.path.splitext(file)[0] + "-aligned.fits"
                if os.path.isfile(aligned_filename):
                    self.siril.log(f"Overwriting existing aligned file: {aligned_filename}")
                    os.remove(aligned_filename)
                os.rename(f"{ALIGN_WORKING_DIR}/r_align_{seqnum:04d}.fits", aligned_filename)
                seqnum += 1

            self.siril.log(f"Aligned {len(input_files)} file(s)", s.LogColor.GREEN)
            self._show_info.emit(f"Alignment complete for {len(input_files)} file(s)")

        except Exception as e:
            self.siril.log(f"Error during alignment: {str(e)}", s.LogColor.SALMON)
            self._show_error.emit(f"Error during alignment: {str(e)}")

        finally:
            try:
                if os.getcwd() != old_cwd:
                    self.siril.cmd("cd", "..")
            except Exception:
                pass
            if os.path.exists(ALIGN_WORKING_DIR):
                shutil.rmtree(ALIGN_WORKING_DIR)

            self._set_controls_enabled.emit(True)

def main():
    try:
        app = QApplication(sys.argv)
        window = SirilAlignInterface()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
