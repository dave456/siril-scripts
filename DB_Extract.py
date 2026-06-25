#
# Dual Band Extraction Stacking Interface for Siril
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
        "None": "",
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
        self.setWindowTitle("Dual Band Extraction")
        self.setFixedWidth(800)
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

        # Ha stacking method group box
        ha_method_box = QGroupBox(" Ha Stacking Method ")
        method_layout = QVBoxLayout()
        ha_method_box.setLayout(method_layout)
        ha_method_box.setContentsMargins(8, 23, 8, 13)

        radio_layout = QHBoxLayout()
        self.ha_interpolation = QRadioButton("Interpolate")
        self.ha_drizzle = QRadioButton("Drizzle")
        self.ha_drizzle.setChecked(True)
        radio_layout.addWidget(self.ha_interpolation)
        radio_layout.addWidget(self.ha_drizzle)
        method_layout.addLayout(radio_layout)
        method_layout.addSpacing(10)

        ha_drizzle_layout = QFormLayout()
        self.ha_scale_spin = QDoubleSpinBox()
        self.ha_scale_spin.setDecimals(1)
        self.ha_scale_spin.setRange(1.0, 4.0)
        self.ha_scale_spin.setValue(2.0)
        self.ha_scale_spin.setSingleStep(0.5)
        self.ha_scale_spin.setEnabled(False)
        ha_drizzle_layout.addRow("Scale (fixed):", self.ha_scale_spin)

        self.ha_pixfrac_spin = QDoubleSpinBox()
        self.ha_pixfrac_spin.setDecimals(2)
        self.ha_pixfrac_spin.setRange(0.01, 1.0)
        self.ha_pixfrac_spin.setValue(0.85)
        self.ha_pixfrac_spin.setSingleStep(0.05)
        self.ha_pixfrac_spin.setEnabled(True)       
        ha_drizzle_layout.addRow("Pixel Fraction:", self.ha_pixfrac_spin)
        method_layout.addLayout(ha_drizzle_layout)

        self.ha_drizzle_method = QComboBox()
        self.ha_drizzle_method.addItems([
            "Square", 
            "Gaussian", 
            "Point",
            "Turbo",
            "Lanczos2",
            "Lanczos3",
        ])
        self.ha_drizzle_method.setCurrentText("Square")
        self.ha_drizzle_method.setEnabled(True)
        ha_drizzle_layout.addRow("Kernel:", self.ha_drizzle_method)
        self.ha_drizzle.toggled.connect(self.OnHaDrizzleToggled)

        # OIII stacking method group box
        oiii_method_box = QGroupBox(" OIII Stacking Method ")
        oiii_method_layout = QVBoxLayout()
        oiii_method_box.setLayout(oiii_method_layout)
        oiii_method_box.setContentsMargins(8, 23, 8, 13)

        oiii_radio_layout = QHBoxLayout()
        self.oiii_interpolation = QRadioButton("Interpolate")
        self.oiii_interpolation.setChecked(True)
        self.oiii_drizzle = QRadioButton("Drizzle")
        oiii_radio_layout.addWidget(self.oiii_interpolation)
        oiii_radio_layout.addWidget(self.oiii_drizzle)
        oiii_method_layout.addLayout(oiii_radio_layout)
        oiii_method_layout.addSpacing(10)

        oiii_drizzle_layout = QFormLayout()
        self.oiii_scale_spin = QDoubleSpinBox()
        self.oiii_scale_spin.setDecimals(1)
        self.oiii_scale_spin.setRange(1.0, 4.0)
        self.oiii_scale_spin.setValue(2.0)
        self.oiii_scale_spin.setSingleStep(0.5)
        self.oiii_scale_spin.setEnabled(False)
        oiii_drizzle_layout.addRow("Scale:", self.oiii_scale_spin)

        self.oiii_pixfrac_spin = QDoubleSpinBox()
        self.oiii_pixfrac_spin.setDecimals(2)
        self.oiii_pixfrac_spin.setRange(0.01, 1.0)
        self.oiii_pixfrac_spin.setValue(0.75)
        self.oiii_pixfrac_spin.setSingleStep(0.05)
        self.oiii_pixfrac_spin.setEnabled(False)       
        oiii_drizzle_layout.addRow("Pixel Fraction:", self.oiii_pixfrac_spin)
        oiii_method_layout.addLayout(oiii_drizzle_layout)

        self.oiii_drizzle_method = QComboBox()
        self.oiii_drizzle_method.addItems([
            "Square", 
            "Gaussian", 
            "Point",
            "Turbo",
            "Lanczos2",
            "Lanczos3",
        ])
        self.oiii_drizzle_method.setCurrentText("Square")
        self.oiii_drizzle_method.setEnabled(False)
        oiii_drizzle_layout.addRow("Kernel:", self.oiii_drizzle_method)
        self.oiii_drizzle.toggled.connect(self.OnOIIIDrizzleToggled)

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

        # output file options group box
        output_box = QGroupBox(" Output Options ")
        output_layout = QFormLayout()
        output_box.setLayout(output_layout)
        output_box.setContentsMargins(8, 23, 8, 13)

        # filename
        self.outfile_name = QLineEdit()
        self.outfile_name.setText("result")
        output_layout.addRow("Output file suffix:", self.outfile_name)
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

        # Create two-column layout
        columns_layout = QHBoxLayout()

        # Left column: Ha and OIII method boxes
        left_column_layout = QVBoxLayout()
        left_column_layout.addWidget(ha_method_box, 1)
        left_column_layout.addWidget(oiii_method_box, 1)

        # Right column: rejection, weighting, and output boxes
        right_column_layout = QVBoxLayout()
        right_column_layout.addWidget(rejection_box, 1)
        right_column_layout.addWidget(weighting_box, 1)
        right_column_layout.addWidget(output_box, 1)

        # Add both columns to the horizontal layout
        columns_layout.addLayout(left_column_layout, 1)
        columns_layout.addLayout(right_column_layout, 1)

        # Add the columns layout to the main layout
        layout.addLayout(columns_layout)
        layout.addSpacing(5)

        # apply and clean buttons
        button_row = QHBoxLayout()
        self.apply_btn = QPushButton("Extract")
        self.apply_btn.setFixedWidth(80)
        self.apply_btn.clicked.connect(self.OnStack)
        button_row.addWidget(self.apply_btn)
        button_row.addSpacing(20)

        self.clean_btn = QPushButton("Clean")
        self.clean_btn.setFixedWidth(80)
        self.clean_btn.clicked.connect(self.OnClean)
        button_row.addWidget(self.clean_btn)

        self.help_btn = QPushButton("Help")
        self.help_btn.setFixedWidth(80)
        self.help_btn.clicked.connect(self.OnHelp)
        button_row.addWidget(self.help_btn)
        layout.addLayout(button_row)

    def addVSpacing(self, layout, spacing=10):
        spacer = QWidget()
        spacer.setFixedHeight(spacing)
        layout.addWidget(spacer)

    def OnThreadComplete(self):
        """re-enable buttons when the stacking thread completes"""
        self.apply_btn.setEnabled(True)
        self.clean_btn.setEnabled(True)

    def OnHaDrizzleToggled(self, checked):
        """toggle the spin boxes for Ha drizzle on/off settings"""
        self.ha_pixfrac_spin.setEnabled(checked)
        self.ha_drizzle_method.setEnabled(checked)

    def OnOIIIDrizzleToggled(self, checked):
        """toggle the spin boxes for OIII drizzle on/off settings"""
        self.oiii_scale_spin.setEnabled(checked)
        self.oiii_pixfrac_spin.setEnabled(checked)
        self.oiii_drizzle_method.setEnabled(checked)

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

    def OnStack(self):
        """start the stacking process in a separate thread"""
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

    def OnHelp(self):
        QMessageBox.information(self, "Dual Band Extraction Help", 
            "This tool extracts the Ha and OIII channels from an OSC image captured\n"
            "using a dual bandpass filter.\n\n"
            "Note: After extraction, the Ha data will be half the size of the OIII data.\n\n"
            
            "If interpolation is selected for Ha, the data will be resampled (2x) to match\n"
            "the OIII image size. If drizzle is selected, the scale is fixed at 2.0 so the\n"
            "final image sizes will match.\n\n"

            "If drizzle is selected for OIII, the scale can be adjusted as desired,\n" \
            "but the OIII channel may be resampled down to match the Ha\n"
            "image size depending upon the scale value selected.\n")
        
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

    def ProcessFlats(self, syntheticBias="=64*$OFFSET", subdir=".", force=False):
        """Process flats"""
        if not isFitsFile(f"{subdir}/masters", "flat_stacked") or force:
            if not os.path.isdir(f"{subdir}/flats"):
                raise ProcessingException("No master_flat or unprocessed flats found!")
            self.siril.log("Stacking flats...", s.LogColor.BLUE)
            self.siril.cmd("cd", "flats")
            self.siril.cmd("convert", "flat", "-out=../process")
            self.siril.cmd("cd", "../process")
            self.siril.cmd("calibrate", "flat", f"-bias=\"{syntheticBias}\"")
            self.siril.cmd("stack", "flat", "rej", "3", "3", "-norm=mul", "-out=../masters/flat_stacked")
            self.siril.cmd("cd", "..")
        return

    def ProcessDarks(self, subdir=".", force=False):
        """Process darks"""
        if not isFitsFile(f"{subdir}/masters", "dark_stacked") or force:
            if not os.path.isdir(f"{subdir}/darks"):
                raise ProcessingException("No master_dark or unprocessed darks found!")
            self.siril.log("Stacking darks...", s.LogColor.BLUE)
            self.siril.cmd("cd", "darks")
            self.siril.cmd("convert", "dark", "-out=../process")
            self.siril.cmd("cd", "../process")
            self.siril.cmd("stack", "dark", "rej", "3", "3", "-nonorm", "-out=../masters/dark_stacked")
            self.siril.cmd("cd", "..")
        return

    def CalibrateLights(self, useDebayer, subdir=".", force=False):
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
            if useDebayer:
                calibrate_args.append("-debayer")
            self.siril.log("Calibrating lights...", s.LogColor.BLUE)
            self.siril.cmd("cd", "process")
            self.siril.cmd("calibrate", *calibrate_args)
            self.siril.cmd("cd", "..")
        else:
            self.siril.log("Calibrated sequence found - skipping calibration.", s.LogColor.BLUE)

    def Register(self, sequenceName, useDrizzle, scale, pixfrac, kernel):
        """Register/Align the sequence"""
        if not os.path.isfile(f"./process/r_{sequenceName}_.seq"):
            self.siril.log(f"Registering {sequenceName}...", s.LogColor.BLUE)
            self.siril.cmd("cd", "process")
            self.siril.cmd("register", sequenceName, "-2pass")
            if useDrizzle:
                self.siril.cmd("seqapplyreg", sequenceName, "-framing=min", "-drizzle", 
                               f"-scale={scale:.1f}", 
                               f"-pixfrac={pixfrac:.2f}", 
                               f"-kernel={kernel.lower()}")
            else:
                self.siril.cmd("seqapplyreg", sequenceName, "-framing=min", "-interp=lanczos4")
            self.siril.cmd("cd", "..")
        else:
            self.siril.log(f"Registered sequence found for {sequenceName}, skipping registration.", s.LogColor.BLUE)

    def ExecuteStacking(self):
        """Perform the stacking process in a separate thread to avoid blocking the GUI."""
        try:
            self.siril.log(f"Starting stacking...", s.LogColor.BLUE)

            if not os.path.exists("process"):
                os.makedirs("process")

            session_dirs = []
            for entry in sorted(os.listdir(base_path)):
                full_path = os.path.join(base_path, entry)
                if os.path.isdir(full_path) and entry.startswith(prefix):
                    session_dirs.append(entry)

            # kind of hacky logic to determine if this is a single-session or not
            if os.path.isdir(os.path.join(base_path, "lights")) and not session_dirs:
                self.siril.log("Detected single-session folder structure.", s.LogColor.BLUE)
                self.ProcessDarks()
                self.ProcessFlats()
                self.ProcessLights()
                self.CalibrateLights(useDebayer=False)
            else:
                # sanity check to just bail if we have nothing
                if not session_dirs:
                    raise ProcessingException(f"No session directories found with prefix '{prefix}', and no top-level lights structure detected.")
                
                self.siril.log("Detected multi-session folder structure.", s.LogColor.BLUE)

                # process all our subdirs
                merge_args = []
                for subdir in session_dirs:
                    self.siril.log(f"Processing session: {subdir}", s.LogColor.BLUE)
                    merge_args.append(f"../{subdir}/process/pp_light")
                    self.siril.cmd("cd", f"{subdir}")
                    self.ProcessDarks(subdir)
                    self.ProcessFlats(subdir)
                    self.ProcessLights(subdir)
                    self.CalibrateLights(useDebayer=False, subdir=subdir)
                    self.siril.cmd("cd", "..")

                # merge all of the calibrated session subs into a single sequence for registration and stacking
                if not os.path.isfile("./process/pp_merge_.seq"):
                    merge_args.append("pp_light")
                    self.siril.cmd("cd", "process")
                    self.siril.cmd("merge", *merge_args)
                    self.siril.cmd("cd", "..")
                else:
                    self.siril.log("Merged sequence found in process directory, skipping merge.", s.LogColor.BLUE)

            # extract the Ha and OIII channels from the pre-processed sequence
            if not os.path.isfile(f"./process/Ha_pp_light_.seq") and not os.path.isfile(f"./process/OIII_pp_light_.seq"):
                self.siril.cmd("cd", "process")
                self.siril.cmd("seqextract_HaOIII", "pp_light")
                self.siril.cmd("cd", "..")
            else:
                self.siril.log("Ha and OIII sequences found, skipping extraction.", s.LogColor.BLUE)

            # Ha registration
            self.Register("Ha_pp_light", 
                          self.ha_drizzle.isChecked(), 
                          self.ha_scale_spin.value(), 
                          self.ha_pixfrac_spin.value(), 
                          self.ha_drizzle_method.currentText())

            # OIII registration
            self.Register("OIII_pp_light",
                          self.oiii_drizzle.isChecked(),
                          self.oiii_scale_spin.value(),
                          self.oiii_pixfrac_spin.value(),
                          self.oiii_drizzle_method.currentText())
            
            # final stacking
            self.siril.cmd("cd", "process")
            for channel in ["Ha", "OIII"]:
                # build the stacking command
                stacking_args = [
                    f"r_{channel}_pp_light",
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

                # create rejection maps?
                if self.create_rejection_maps_checkbox.isChecked():
                    stacking_args.append("-rejmaps")

                # input image normalization
                stacking_args.append(self.normalizationMethods[self.input_norm_combo.currentText()])

                # output normalization
                if self.output_norm_checkbox.isChecked():
                    stacking_args.append("-output_norm")

                # miscellaneous other flags that are fixed (for now)
                stacking_args.append("-32b")
                stacking_args.append(f"-out=../{channel}_{self.outfile_name.text()}")

                # run the stacking command in siril and open the result
                self.siril.cmd("stack", *stacking_args)

                # if we used interpolation on the Ha channel we need to resample it up so its the same
                # size as the OIII channel
                if channel == "Ha" and self.ha_interpolation.isChecked():
                    self.siril.cmd("cd", "..")
                    self.siril.cmd("load", f"{channel}_{self.outfile_name.text()}")
                    self.siril.cmd("resample", "2")
                    self.siril.cmd("save", f"{channel}_{self.outfile_name.text()}")
                    self.siril.cmd("close")
                    self.siril.cmd("cd", "process")

                # if we used drizzle with a scale greater than 1.0 on the OIII channel we need to resample 
                # it down to match the Ha channel
                if channel == "OIII" and self.oiii_drizzle.isChecked() and self.oiii_scale_spin.value() > 1.0:
                    self.siril.cmd("cd", "..")
                    self.siril.cmd("load", f"{channel}_{self.outfile_name.text()}")
                    resample_factor = 1.0 / self.oiii_scale_spin.value()
                    self.siril.cmd("resample", f"{resample_factor}")
                    self.siril.cmd("save", f"{channel}_{self.outfile_name.text()}")
                    self.siril.cmd("close")
                    self.siril.cmd("cd", "process")

            self.siril.cmd("cd", "..")
            # load the Ha channel \o/
            self.siril.cmd("load", f"Ha_{self.outfile_name.text()}")
            self.siril.log("Stacking complete.", s.LogColor.GREEN)

        except ProcessingException as pe:
            self.siril.cmd("pwd")
            self.siril.log(f"Error in processing: {str(pe)}", s.LogColor.SALMON)

        except Exception as e:
            self.siril.cmd("pwd")
            self.siril.log(f"Unhandled exception in ExecuteStacking(): {str(e)}", s.LogColor.SALMON)

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
