#
# Multi-session stacking interface for Siril
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2026 lindner234 <AT> gmail
#

import sirilpy as s
s.ensure_installed("PyQt6")

import os
import sys
import threading

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QGroupBox, QRadioButton, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal

prefix = "session"
base_path = "."


class MultisessionInterface(QWidget):
    _enable_apply = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multi-Session Stacking")
        self.setFixedWidth(350)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.siril = s.SirilInterface()
        try:
            self.siril.connect()
        except s.SirilConnectionError:
            QMessageBox.critical(self, "Error", "Failed to connect to Siril!")
            self.close()
            return

        self._enable_apply.connect(lambda: self.apply_btn.setEnabled(True))
        self.CreateWidgets()

    def CreateWidgets(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        method_box = QGroupBox(" Stacking Method ")
        method_layout = QVBoxLayout()
        method_box.setLayout(method_layout)
        method_box.setContentsMargins(8, 23, 8, 13)

        self.interpolation_radio = QRadioButton("Interpolation (Lanczos4)")
        self.drizzle_radio = QRadioButton("Drizzle (2x)")
        self.drizzle_radio.setChecked(True)
        method_layout.addWidget(self.interpolation_radio)
        method_layout.addWidget(self.drizzle_radio)
        layout.addWidget(method_box)

        button_row = QHBoxLayout()
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setFixedWidth(80)
        self.apply_btn.clicked.connect(self.OnApply)
        button_row.addWidget(self.apply_btn)
        layout.addLayout(button_row)

    def OnApply(self):
        self.apply_btn.setEnabled(False)
        threading.Thread(target=self.ExecuteStacking, daemon=True).start()

    def ExecuteStacking(self):
        use_drizzle = self.drizzle_radio.isChecked()
        method = "Drizzle (2x)" if use_drizzle else "Interpolation (Lanczos4)"

        try:
            self.siril.log(f"Starting multi-session stacking — {method}", s.LogColor.BLUE)

            if not os.path.exists("process"):
                os.makedirs("process")

            merge_dirs = []

            for entry in sorted(os.listdir(base_path)):
                full_path = os.path.join(base_path, entry)
                if os.path.isdir(full_path) and entry.startswith(prefix):
                    self.siril.log(f"Processing session: {entry}", s.LogColor.BLUE)
                    merge_dirs.append("../" + entry + "/process/pp_light")

                    self.siril.cmd("cd", os.path.join(entry, "lights"))
                    self.siril.cmd("convert", "light", "-out=../process")
                    self.siril.cmd("cd", "../process")

                    calibrate_args = [
                        "light",
                        "-dark=../masters/dark_stacked",
                        "-flat=../masters/flat_stacked",
                        "-cc=dark", "-cfa", "-equalize_cfa",
                    ]
                    if not use_drizzle:
                        calibrate_args.append("-debayer")
                    self.siril.cmd("calibrate", *calibrate_args)

                    self.siril.cmd("cd", "../..")

            if not merge_dirs:
                self.siril.log(f"No session directories found with prefix '{prefix}'.", s.LogColor.SALMON)
                return

            merge_dirs.append("pp_merge")
            self.siril.cmd("cd", "process")
            self.siril.cmd("merge", *merge_dirs)

            if use_drizzle:
                self.siril.cmd("register", "pp_merge", "-drizzle", "-scale=2.0", "-pixfrac=0.75", "-kernel=square")
            else:
                self.siril.cmd("register", "pp_merge", "-interp=lanczos4")

            self.siril.cmd("stack", "r_pp_merge", "rej", "3", "3",
                           "-norm=addscale", "-filter-wfwhm=3.0k", "-output_norm", "-32b", "-out=../result")
            self.siril.cmd("cd", "..")
            self.siril.cmd("load", "result")
            self.siril.log("Stacking complete.", s.LogColor.GREEN)

        except Exception as e:
            self.siril.log(f"Unhandled exception in ExecuteStacking(): {str(e)}", s.LogColor.SALMON)

        finally:
            self._enable_apply.emit()


def main():
    try:
        app = QApplication(sys.argv)
        window = MultisessionInterface()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
