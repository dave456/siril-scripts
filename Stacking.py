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

class ProcessingException(Exception):
    """Custom exception for processing errors."""
    pass

class StackingInterface(QWidget):
    # thread complete signal
    threadComplete = pyqtSignal()

    # dict for rejection methods
    rejectionMethods = {
        "None": "n",
        "Percentile Clipping": "p",
        "Sigma Clipping": "s",
        "MAD Clipping": "mad",
        "Median Sigma Clipping": "m",
        "Linear Fit Clipping": "l",
        "Winsorized Sigma Clipping": "w",
        "GESDT Clipping": "g",
    }

    # dict for weighting methods
    weightingMethods = {
        "None": "None",
        "Number of stars": "-weight=nbstars",
        "Noise": "-weight=noise",
        "Weighted FWHM": "-weight=wfwhm",
    }

    # dict for normalization methods
    normalizationMethods = {
        "None": "-nonorm",
        "Additive": "-norm=add",
        "Multiplicative": "-norm=mul",
        "Additive Scaling": "-norm=addscale",
        "Multiplicative Scaling": "-norm=mulscale",
    }

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

        self.threadComplete.connect(self.OnThreadComplete)
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

        self.drizzle_method = QComboBox()
        self.drizzle_method.addItems([
            "Square", 
            "Gaussian", 
            "Point",
            "Turbo",
            "Lanczos2",
            "Lanczos3",
        ])
        self.drizzle_method.setCurrentText("Square")
        self.drizzle_method.setEnabled(False)
        drizzle_layout.addRow("Kernel:", self.drizzle_method)

        layout.addWidget(drizzle_box)
        self.drizzle_radio.toggled.connect(self.OnDrizzleToggled)

        # pixel rejection settings group box
        rejection_box = QGroupBox(" Pixel Rejection ")
        rejection_layout = QFormLayout()
        rejection_box.setLayout(rejection_layout)
        rejection_box.setContentsMargins(8, 23, 8, 13)

        # combo box for rejection method selection
        self.rejection_combo = QComboBox()
        for method in self.rejectionMethods.keys():
            self.rejection_combo.addItem(method)
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
        for method in self.weightingMethods.keys():
            self.weighting_combo.addItem(method)
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
        for method in self.normalizationMethods.keys():
            self.input_norm_combo.addItem(method)
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

    def OnThreadComplete(self):
        self.apply_btn.setEnabled(True)
        self.clean_btn.setEnabled(True)

    def OnDrizzleToggled(self, checked):
        """toggle the spin boxes for drizzle on/off settings"""
        self.scale_spin.setEnabled(checked)
        self.pixfrac_spin.setEnabled(checked)
        self.drizzle_method.setEnabled(checked)

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
        self.clean_btn.setEnabled(False)
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

    def ProcessLights(self, subdir=".", force=False):
        """Process lights"""
        if not os.path.isfile(f"{subdir}/process/light_.seq") or force:
            if not os.path.isdir(f"{subdir}/lights"):
                raise ProcessingException("No lights found!")
            self.siril.log("Converting lights...", s.LogColor.BLUE)
            self.siril.cmd("cd", "lights")
            self.siril.cmd("convert", "light", "-out=../process")
            self.siril.cmd("cd", "..")
        else:
            self.siril.log("Lights sequence found - skipping conversion.", s.LogColor.BLUE)

    def ProcessFlats(self, subdir=".", force=False):
        if not isFitsFile(f"{subdir}/masters", "flat_stacked") or force:
            if not os.path.isdir(f"{subdir}/flats"):
                raise ProcessingException("No flats found!")
            # TODO: Implement flat stacking logic!
            self.siril.log("Stacking flats... NOT IMPLEMENTED YET", s.LogColor.BLUE)
        return

    def ProcessDarks(self, subdir=".", force=False):
        """Process darks"""
        if not isFitsFile(f"{subdir}/masters", "dark_stacked") or force:
            if not os.path.isdir(f"{subdir}/darks"):
                raise ProcessingException("No darks found!")
            self.siril.log("Stacking darks...", s.LogColor.BLUE)
            self.siril.cmd("cd", "darks")
            self.siril.cmd("convert", "dark", "../process")
        return

    def CalibrateLights(self, use_drizzle, subdir=".", force=False):
        """Calibrate lights"""
        if not os.path.isfile(f"{subdir}/process/pp_light_.seq") or force:
            if not isFitsFile(f"{subdir}/masters", "dark_stacked") or not isFitsFile(f"{subdir}/masters", "flat_stacked"):
                raise ProcessingException("Calibration master fit files not found!")
            calibrate_args = [
                "light",
                "-dark=../masters/dark_stacked",
                "-flat=../masters/flat_stacked",
                "-cc=dark", "-cfa", "-equalize_cfa",
            ]
            if not use_drizzle:
                calibrate_args.append("-debayer")
            self.siril.log("Calibrating lights...", s.LogColor.BLUE)
            self.siril.cmd("cd", "process")
            self.siril.cmd("calibrate", *calibrate_args)
            self.siril.cmd("cd", "..")
        else:
            self.siril.log("Calibrated sequence found - skipping calibration.", s.LogColor.BLUE)

    def ExecuteStacking(self):
        """Main stacking logic, executed in a separate thread to keep the GUI responsive."""
        try:
            self.siril.log("Starting stacking...", s.LogColor.BLUE)
            use_drizzle = self.drizzle_radio.isChecked()

            # is this necessary?
            if not os.path.exists("process"):
                os.makedirs("process")

            # collect a list of session directory that match our prefix
            session_dirs = []
            for subdir in sorted(os.listdir(base_path)):
                full_path = os.path.join(base_path, subdir)
                if os.path.isdir(full_path) and subdir.startswith(prefix):
                    session_dirs.append(subdir)

            # kind of hacky logic to determine if this is a single-session or not
            if os.path.isdir(os.path.join(base_path, "lights")) and not session_dirs:
                self.ProcessDarks()
                self.ProcessFlats()
                self.ProcessLights()
                self.CalibrateLights(use_drizzle)
            else:
                # sanity check to just bail if we have nothing
                if not session_dirs:
                    raise ProcessingException(f"No session directories found with prefix '{prefix}', and no top-level lights/masters structure detected.")
                
                self.siril.log("Detected multi-session folder structure.", s.LogColor.BLUE)

                merge_args = []
                for subdir in session_dirs:
                    self.siril.log(f"Processing session: {subdir}", s.LogColor.BLUE)
                    merge_args.append("../" + subdir + "/process/pp_light")

                    self.siril.cmd("cd", f"{subdir}")
                    self.ProcessDarks(subdir)
                    self.ProcessFlats(subdir)
                    self.ProcessLights(subdir)
                    self.CalibrateLights(use_drizzle, subdir)
                    self.siril.cmd("cd", "..")

                # merge all of the calibrated session subs into a single sequence for registration and stacking
                if not os.path.isfile("./process/pp_light_.seq"):
                    merge_args.append("pp_light")
                    self.siril.cmd("cd", "process")
                    self.siril.cmd("merge", *merge_args)
                    self.siril.cmd("cd", "..")
                else:
                    self.siril.log("Merged sequence found in process directory, skipping merge.", s.LogColor.BLUE)

            # use a 2-pass algorithm for registration
            if not os.path.isfile(f"./process/r_pp_light_.seq"):
                self.siril.cmd("cd", "process")
                self.siril.cmd("register", "pp_light", "-2pass")
                if use_drizzle:
                    self.siril.cmd("seqapplyreg", "pp_light", "-framing=min", "-drizzle", 
                                   f"-scale={self.scale_spin.value():.1f}", 
                                   f"-pixfrac={self.pixfrac_spin.value():.2f}", 
                                   f"-kernel={self.drizzle_method.currentText().lower()}")
                else:
                    self.siril.cmd("seqapplyreg", "pp_light", "-framing=min", "-interp=lanczos4")
            else:
                self.siril.log("Registered sequence found, skipping registration.", s.LogColor.BLUE)
                
            # build the stacking command
            stacking_args = [
                f"r_pp_light",
                "rej"
            ]

            # pixel rejection method
            selectedMethod = self.rejection_combo.currentText()
            stacking_args.append(self.rejectionMethods[selectedMethod])
            if selectedMethod != "None":
                stacking_args.append(self.low_spin.value())
                stacking_args.append(self.high_spin.value())
    
            # weighting
            selectedWeighting = self.weighting_combo.currentText()
            if selectedWeighting != "None":
                stacking_args.append(self.weightingMethods[selectedWeighting])

            # create rejection maps
            if self.create_rejection_maps_checkbox.isChecked():
                stacking_args.append("-rejmaps")

            # input image normalization
            stacking_args.append(self.normalizationMethods[self.input_norm_combo.currentText()])

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

        except ProcessingException as pe:
            self.siril.log(f"Error in processing: {str(pe)}", s.LogColor.SALMON)
            self.siril.cmd("cd", "..")  # Ensure we return to the base directory on error

        except Exception as e:
            self.siril.log(f"Unhandled exception in ExecuteStacking(): {str(e)}", s.LogColor.SALMON)
            self.siril.cmd("cd", "..")  # Ensure we return to the base directory on error

        finally:
            self.siril.reset_progress()
            self.threadComplete.emit()

def isFitsFile(dirname, basename):
    return any(
        os.path.isfile(f"{dirname}/{basename}{ext}")
        for ext in (".fit", ".fits")
    )

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
