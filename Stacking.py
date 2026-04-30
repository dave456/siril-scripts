#
# Multi-session stacking interface for Siril
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2026 lindner234 <AT> gmail
#

import sirilpy as s
s.ensure_installed("PyQt6")

import os
import shutil
import sys
import threading

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QGroupBox, QRadioButton, QMessageBox,
    QDoubleSpinBox, QFormLayout, QComboBox, QLabel, 
    QCheckBox, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal

prefix = "session"
base_path = "."


class StackingInterface(QWidget):
    _enable_apply = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Session Stacking")
        self.setFixedWidth(500)
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

        # stacking method group box
        method_box = QGroupBox(" Stacking Method ")
        method_layout = QVBoxLayout()
        method_box.setLayout(method_layout)
        method_box.setContentsMargins(8, 23, 8, 13)

        self.interpolation_radio = QRadioButton("Interpolation (Lanczos4)")
        self.interpolation_radio.setChecked(True)
        self.drizzle_radio = QRadioButton("Drizzle")
        method_layout.addWidget(self.interpolation_radio)
        method_layout.addWidget(self.drizzle_radio)
        layout.addWidget(method_box)

        # drizzle settings group box (enabled only if Drizzle is selected)
        drizzle_box = QGroupBox(" Drizzle Settings ")
        drizzle_layout = QFormLayout()
        drizzle_box.setLayout(drizzle_layout)
        drizzle_box.setContentsMargins(8, 23, 8, 13)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setDecimals(1)
        self.scale_spin.setRange(1.0, 4.0)
        self.scale_spin.setValue(2.0)
        self.scale_spin.setSingleStep(0.5)
        self.scale_spin.setEnabled(False)
        drizzle_layout.addRow("Scale:", self.scale_spin)

        self.pixfrac_spin = QDoubleSpinBox()
        self.pixfrac_spin.setDecimals(2)
        self.pixfrac_spin.setRange(0.01, 1.0)
        self.pixfrac_spin.setValue(0.75)
        self.pixfrac_spin.setSingleStep(0.05)
        self.pixfrac_spin.setEnabled(False)
        drizzle_layout.addRow("Pixel Fraction:", self.pixfrac_spin)

        layout.addWidget(drizzle_box)
        self.drizzle_radio.toggled.connect(self.OnDrizzleToggled)

        # pixel rejection settings group box
        rejection_box = QGroupBox(" Pixel Rejection ")
        rejection_layout = QFormLayout()
        rejection_box.setLayout(rejection_layout)
        rejection_box.setContentsMargins(8, 23, 8, 13)

        # combo box for rejection method selection
        self.rejection_combo = QComboBox()
        self.rejection_combo.addItems([
            "None",
            "Percentile Clipping",
            "Sigma Clipping",
            "MAD Clipping",
            "Median Sigma Clipping",
            "Linear Fit Clipping",
            "Winsorized Sigma Clipping",
            "GESDT Clipping",
        ])
        self.rejection_combo.setCurrentText("Winsorized Sigma Clipping")
        self.rejection_combo.setFixedWidth(190)
        self.rejection_combo.currentTextChanged.connect(self.OnRejectionMethodChanged)

        # generic spin boxes for rejection method
        self.high_spin = QDoubleSpinBox()
        self.high_spin.setDecimals(3)
        self.high_spin.setRange(0.001, 10.0)
        self.high_spin.setValue(3.0)
        self.high_spin.setSingleStep(0.1)

        self.low_spin = QDoubleSpinBox()
        self.low_spin.setDecimals(3)
        self.low_spin.setRange(0.001, 10.0)
        self.low_spin.setValue(3.0)
        self.low_spin.setSingleStep(0.1)

        # default text for spin boxes, since Winsorized Sigma Clipping is the default method
        label_width = 70
        self.high_label = QLabel("Sigma high:")
        self.high_label.setFixedWidth(label_width)
        self.low_label = QLabel("Sigma low:")
        self.low_label.setFixedWidth(label_width)

        # layout for the rejection method combo box and the high/low spin boxes
        sigma_controls = QVBoxLayout()
        sigma_controls.setSpacing(6)

        sigma_high_row = QHBoxLayout()
        sigma_high_row.setSpacing(6)
        sigma_high_row.addWidget(self.high_label)
        sigma_high_row.addWidget(self.high_spin)
        sigma_high_row.addStretch()
        sigma_controls.addLayout(sigma_high_row)

        sigma_low_row = QHBoxLayout()
        sigma_low_row.setSpacing(6)
        sigma_low_row.addWidget(self.low_label)
        sigma_low_row.addWidget(self.low_spin)
        sigma_low_row.addStretch()
        sigma_controls.addLayout(sigma_low_row)

        sigma_row = QHBoxLayout()
        sigma_row.addWidget(self.rejection_combo, 1)
        sigma_row.addSpacing(20)
        sigma_row.addLayout(sigma_controls)
        rejection_layout.addRow(sigma_row)

        # checkbox for creating rejection maps
        self.create_rejection_maps_checkbox = QCheckBox("Create Rejection Maps")
        rejection_layout.addRow(self.create_rejection_maps_checkbox)
        layout.addWidget(rejection_box)

        # pixel rejection weighting group box
        weighting_box = QGroupBox(" Rejection Weighting ")
        weighting_layout = QFormLayout()
        weighting_box.setLayout(weighting_layout)
        weighting_box.setContentsMargins(8, 23, 8, 13)

        self.weighting_combo = QComboBox()
        self.weighting_combo.addItems([
            "None",
            "Number of stars",
            "Noise",
            "Weighted FWHM",
        ])
        self.weighting_combo.setCurrentText("Weighted FWHM")
        weighting_layout.addRow("Method:", self.weighting_combo)
        layout.addWidget(weighting_box)

        # output file options group box
        output_box = QGroupBox(" Output Options ")
        output_layout = QFormLayout()
        output_box.setLayout(output_layout)
        output_box.setContentsMargins(8, 23, 8, 13)

        # filename
        self.outfile_name = QLineEdit()
        self.outfile_name.setText("result")
        output_layout.addRow("Output file name:", self.outfile_name)
        self.addVSpacing(output_layout, spacing=3)

        # input normalization options
        input_norm_row = QHBoxLayout()
        input_norm_label = QLabel("Input image normalization:")
        input_norm_label.setFixedWidth(150)
        input_norm_row.addWidget(input_norm_label)
        self.input_norm_combo = QComboBox()
        self.input_norm_combo.addItems([
            "None",
            "Additive",
            "Multiplicative",
            "Additive Scaling",
            "Multiplicative Scaling",
        ])
        self.input_norm_combo.setCurrentText("Additive Scaling")
        input_norm_row.addWidget(self.input_norm_combo)
        input_norm_row.addStretch()
        output_layout.addRow(input_norm_row)
        self.addVSpacing(output_layout, spacing=4)
 
        # normalize output
        self.output_norm_checkbox = QCheckBox("Normalize output [0..1]")
        self.output_norm_checkbox.setChecked(True)
        output_layout.addRow(self.output_norm_checkbox)
        layout.addWidget(output_box)
        layout.addSpacing(5)

        # apply and clean buttons
        button_row = QHBoxLayout()
        self.apply_btn = QPushButton("Stack")
        self.apply_btn.setFixedWidth(80)
        self.apply_btn.clicked.connect(self.OnStack)
        button_row.addWidget(self.apply_btn)
        button_row.addSpacing(20)

        self.clean_btn = QPushButton("Clean")
        self.clean_btn.setFixedWidth(80)
        self.clean_btn.clicked.connect(self.OnClean)
        button_row.addWidget(self.clean_btn)
        layout.addLayout(button_row)

    def OnDrizzleToggled(self, checked):
        """toggle the spin boxes for drizzle on/off settings"""
        self.scale_spin.setEnabled(checked)
        self.pixfrac_spin.setEnabled(checked)

    def OnRejectionMethodChanged(self, method):
        """update labels for spin boxes based on rejection method"""
        if method in ["Sigma Clipping", "Median Sigma Clipping", "Winsorized Sigma Clipping", "MAD Clipping"]:
            self.high_label.setText("Sigma high:")
            self.low_label.setText("Sigma low:")
            self.high_spin.setValue(3.0)
            self.low_spin.setValue(3.0)
        elif method == "Percentile Clipping":
            self.high_label.setText("%-tile high:")
            self.low_label.setText("%-tile low:")
            self.high_spin.setValue(1.0)
            self.low_spin.setValue(1.0)
        elif method == "GESDT Clipping":
            self.high_label.setText("ESD outliers:")
            self.low_label.setText("Significance:")
            self.high_spin.setValue(0.30)
            self.low_spin.setValue(0.05)
        elif method == "Linear Fit Clipping":
            self.high_label.setText("Linear high:")
            self.low_label.setText("Linear low:")
            self.high_spin.setValue(3.0)
            self.low_spin.setValue(3.0)

    def addVSpacing(self, layout, spacing=10):
        spacer = QWidget()
        spacer.setFixedHeight(spacing)
        layout.addWidget(spacer)
 
    def OnStack(self):
        self.apply_btn.setEnabled(False)
        threading.Thread(target=self.ExecuteStacking, daemon=True).start()

    def OnClean(self):
        session_dirs = [
            entry for entry in sorted(os.listdir(base_path))
            if os.path.isdir(os.path.join(base_path, entry)) and entry.startswith(prefix)
        ]
        is_single_session = bool(
            os.path.isdir(os.path.join(base_path, "lights")) and
            os.path.isdir(os.path.join(base_path, "masters")) and
            not session_dirs
        )

        dirs_to_clean = []
        top_process = os.path.join(base_path, "process")
        if os.path.isdir(top_process):
            dirs_to_clean.append(top_process)
        if not is_single_session:
            for entry in session_dirs:
                session_process = os.path.join(base_path, entry, "process")
                if os.path.isdir(session_process):
                    dirs_to_clean.append(session_process)

        if not dirs_to_clean:
            QMessageBox.information(self, "Clean", "No process directories found to clean.")
            return

        dir_list = "\n".join(dirs_to_clean)
        reply = QMessageBox.question(
            self, "Confirm Clean",
            f"Delete the following process directories?\n\n{dir_list}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            for d in dirs_to_clean:
                shutil.rmtree(d)
                self.siril.log(f"Deleted directory: {d}", s.LogColor.BLUE)
            count = len(dirs_to_clean)
            self.siril.log(f"Cleaned {count} process director{'y' if count == 1 else 'ies'}.", s.LogColor.GREEN)
        except Exception as e:
            self.siril.log(f"Error cleaning process directories: {str(e)}", s.LogColor.SALMON)

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
                if not os.path.isfile("./process/light_.seq"):
                    self.siril.log("Detected single-night folder structure.", s.LogColor.BLUE)
                    self.siril.cmd("cd", "lights")
                    self.siril.cmd("convert", "light", "-out=../process")
                    self.siril.cmd("cd", "../process")
                else:
                    self.siril.log("Lights sequence found in process directory, skipping conversion.", s.LogColor.BLUE)
                    self.siril.cmd("cd", "./process")

                if not os.path.isfile("./process/pp_light_.seq"):
                    calibrate_args = [
                        "light",
                        "-dark=../masters/dark_stacked",
                        "-flat=../masters/flat_stacked",
                        "-cc=dark", "-cfa", "-equalize_cfa",
                    ]
                    if not use_drizzle:
                        calibrate_args.append("-debayer")
                    self.siril.cmd("calibrate", *calibrate_args)
                else:
                    self.siril.log("Calibrated sequence found in process directory, skipping calibration.", s.LogColor.BLUE)

                stack_prefix = "pp_light"
            else:
                if not session_dirs:
                    self.siril.log(
                        f"No session directories found with prefix '{prefix}', and no top-level lights/masters structure detected.",
                        s.LogColor.SALMON,
                    )
                    return

                self.siril.log("Detected multi-session folder structure.", s.LogColor.BLUE)
                merge_args = []

                for entry in session_dirs:
                    self.siril.log(f"Processing session: {entry}", s.LogColor.BLUE)
                    merge_args.append("../" + entry + "/process/pp_light")

                    # convert lights for each session
                    if not os.path.isfile(os.path.join(base_path, entry, "process", "light_.seq")):
                        self.siril.cmd("cd", os.path.join(entry, "lights"))
                        self.siril.cmd("convert", "light", "-out=../process")
                        self.siril.cmd("cd", "../process")
                    else:
                        self.siril.log(f"Lights sequence found for session '{entry}', skipping conversion.", s.LogColor.BLUE)
                        self.siril.cmd("cd", os.path.join(entry, "process"))

                    # calibrate lights for each session
                    if not os.path.isfile(os.path.join(base_path, entry, "process", "pp_light_.seq")):
                        calibrate_args = [
                            "light",
                            "-dark=../masters/dark_stacked",
                            "-flat=../masters/flat_stacked",
                            "-cc=dark", "-cfa", "-equalize_cfa",
                        ]
                        if not use_drizzle:
                            calibrate_args.append("-debayer")
                        self.siril.cmd("calibrate", *calibrate_args)
                    else:
                        self.siril.log(f"Calibrated sequence found for session '{entry}', skipping calibration.", s.LogColor.BLUE)

                    self.siril.cmd("cd", "../..")

                # merge all of the calibrated session subs into a single sequence for registration and stacking
                if not os.path.isfile("./process/pp_merge_.seq"):
                    merge_args.append("pp_merge")
                    self.siril.cmd("cd", "process")
                    self.siril.cmd("merge", *merge_args)
                else:
                    self.siril.log("Merged sequence found in process directory, skipping merge.", s.LogColor.BLUE)
                    self.siril.cmd("cd", "process")

                stack_prefix = "pp_merge"

            # register all the calibrated subs
            if not os.path.isfile(f"./process/r_{stack_prefix}_.seq"):
                if use_drizzle:
                    self.siril.cmd("register", stack_prefix, "-drizzle", f"-scale={scale:.1f}", f"-pixfrac={pixfrac:.2f}", "-kernel=square")
                else:
                    self.siril.cmd("register", stack_prefix, "-interp=lanczos4")
            else:
                self.siril.log("Registered sequence found, skipping registration.", s.LogColor.BLUE)
                
            # build the stacking command
            stacking_args = [
                f"r_{stack_prefix}",
                "rej"
            ]

            # pixel rejection method
            if self.weighting_combo.currentText() == "None":
                stacking_args.append("n")
            elif self.rejection_combo.currentText() == "Sigma Clipping":
                stacking_args.append("s")
                stacking_args.append(self.low_spin.value())
                stacking_args.append(self.high_spin.value())
            elif self.rejection_combo.currentText() == "Percentile Clipping":
                stacking_args.append("p")
                stacking_args.append(self.low_spin.value())
                stacking_args.append(self.high_spin.value())
            elif self.rejection_combo.currentText() == "MAD Clipping":
                stacking_args.append("mad")
                stacking_args.append(self.low_spin.value())
                stacking_args.append(self.high_spin.value())
            elif self.rejection_combo.currentText() == "Median Sigma Clipping":
                stacking_args.append("m")
                stacking_args.append(self.low_spin.value())
                stacking_args.append(self.high_spin.value())
            elif self.rejection_combo.currentText() == "Winsorized Sigma Clipping":
                stacking_args.append("w")
                stacking_args.append(self.low_spin.value())
                stacking_args.append(self.high_spin.value())
            elif self.rejection_combo.currentText() == "GESDT Clipping":
                stacking_args.append("g")
                stacking_args.append(self.low_spin.value())
                stacking_args.append(self.high_spin.value())
            elif self.rejection_combo.currentText() == "Linear Fit Clipping":
                stacking_args.append("l")
                stacking_args.append(self.low_spin.value())
                stacking_args.append(self.high_spin.value())
    
            # weighting
            if self.weighting_combo.currentText() == "Number of stars":
                stacking_args.append("-weight=nbstars")
            elif self.weighting_combo.currentText() == "Noise":
                stacking_args.append("-weight=noise")
            elif self.weighting_combo.currentText() == "Weighted FWHM":
                stacking_args.append("-weight=wfwhm")

            # create rejection maps?
            if self.create_rejection_maps_checkbox.isChecked():
                stacking_args.append("-rejmaps")

            # input image normalization
            if self.input_norm_combo.currentText() == "None":
                stacking_args.append("-nonorm")
            elif self.input_norm_combo.currentText() == "Additive":
                stacking_args.append("-norm=add")
            elif self.input_norm_combo.currentText() == "Multiplicative":
                stacking_args.append("-norm=mul")
            elif self.input_norm_combo.currentText() == "Additive Scaling":
                stacking_args.append("-norm=addscale")
            elif self.input_norm_combo.currentText() == "Multiplicative Scaling":
                stacking_args.append("-norm=mulscale")

            # output normalization
            if self.output_norm_checkbox.isChecked():
                stacking_args.append("-output_norm")

            # miscellaneous other flags that are fixed (for now)
            stacking_args.append("-32b")
            stacking_args.append(f"-out=../{self.outfile_name.text()}")

            # run the stacking command in siril and open the result
            self.siril.cmd("stack", *stacking_args)
            self.siril.cmd("cd", "..")
            self.siril.cmd("load", f"{self.outfile_name.text()}")
            self.siril.log("Stacking complete.", s.LogColor.GREEN)

        except Exception as e:
            self.siril.log(f"Unhandled exception in ExecuteStacking(): {str(e)}", s.LogColor.SALMON)

        finally:
            self._enable_apply.emit()


def main():
    try:
        app = QApplication(sys.argv)
        window = StackingInterface()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
