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
    QPushButton, QGroupBox, QRadioButton, QMessageBox,
    QDoubleSpinBox, QFormLayout
)
from PyQt6.QtCore import Qt, pyqtSignal

prefix = "session"
base_path = "."


class MultisessionInterface(QWidget):
    _enable_apply = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Session Stacking")
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
        self.drizzle_radio = QRadioButton("Drizzle")
        self.drizzle_radio.setChecked(True)
        method_layout.addWidget(self.interpolation_radio)
        method_layout.addWidget(self.drizzle_radio)
        layout.addWidget(method_box)

        drizzle_box = QGroupBox(" Drizzle Options ")
        drizzle_layout = QFormLayout()
        drizzle_box.setLayout(drizzle_layout)
        drizzle_box.setContentsMargins(8, 23, 8, 13)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setDecimals(1)
        self.scale_spin.setRange(1.0, 4.0)
        self.scale_spin.setValue(2.0)
        self.scale_spin.setSingleStep(0.5)
        drizzle_layout.addRow("Scale:", self.scale_spin)

        self.pixfrac_spin = QDoubleSpinBox()
        self.pixfrac_spin.setDecimals(2)
        self.pixfrac_spin.setRange(0.01, 1.0)
        self.pixfrac_spin.setValue(0.75)
        self.pixfrac_spin.setSingleStep(0.05)
        drizzle_layout.addRow("Pixel Fraction:", self.pixfrac_spin)

        layout.addWidget(drizzle_box)
        self.drizzle_radio.toggled.connect(self.OnDrizzleToggled)

        button_row = QHBoxLayout()
        self.apply_btn = QPushButton("Stack")
        self.apply_btn.setFixedWidth(80)
        self.apply_btn.clicked.connect(self.OnStack)
        button_row.addWidget(self.apply_btn)
        layout.addLayout(button_row)

    def OnDrizzleToggled(self, checked):
        self.scale_spin.setEnabled(checked)
        self.pixfrac_spin.setEnabled(checked)

    def OnStack(self):
        self.apply_btn.setEnabled(False)
        threading.Thread(target=self.ExecuteStacking, daemon=True).start()

    def ExecuteStacking(self):
        use_drizzle = self.drizzle_radio.isChecked()
        scale = self.scale_spin.value()
        pixfrac = self.pixfrac_spin.value()
        method = f"Drizzle ({scale:.1f}x)" if use_drizzle else "Interpolation (Lanczos4)"

        try:
            self.siril.log(f"Starting stacking - {method}", s.LogColor.BLUE)

            if not os.path.exists("process"):
                os.makedirs("process")

            session_dirs = []
            for entry in sorted(os.listdir(base_path)):
                full_path = os.path.join(base_path, entry)
                if os.path.isdir(full_path) and entry.startswith(prefix):
                    session_dirs.append(entry)

            is_single_session = bool(
                os.path.isdir(os.path.join(base_path, "lights")) and
                os.path.isdir(os.path.join(base_path, "masters")) and
                not session_dirs
            )

            if is_single_session:
                self.siril.log("Detected single-night folder structure.", s.LogColor.BLUE)

                self.siril.cmd("cd", "lights")
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

                stack_prefix = "pp_light"
            else:
                if not session_dirs:
                    self.siril.log(
                        f"No session directories found with prefix '{prefix}', and no top-level lights/masters structure detected.",
                        s.LogColor.SALMON,
                    )
                    return

                self.siril.log("Detected multi-night folder structure.", s.LogColor.BLUE)
                merge_dirs = []

                for entry in session_dirs:
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

                merge_dirs.append("pp_merge")
                self.siril.cmd("cd", "process")
                self.siril.cmd("merge", *merge_dirs)
                stack_prefix = "pp_merge"

            if use_drizzle:
                self.siril.cmd("register", stack_prefix, "-drizzle", f"-scale={scale:.1f}", f"-pixfrac={pixfrac:.2f}", "-kernel=square")
            else:
                self.siril.cmd("register", stack_prefix, "-interp=lanczos4")

            self.siril.cmd("stack", f"r_{stack_prefix}", "rej", "3", "3", "-weight=wfwhm",
                           "-norm=addscale", "-output_norm", "-32b", "-out=../result")
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
