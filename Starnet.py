#
# Starnet script for Siril
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2026 lindner234 <AT> gmail
#

import sirilpy as s
s.ensure_installed("PyQt6")
s.ensure_installed("numpy")
s.ensure_installed("tifffile")
s.ensure_installed("imagecodecs")

import os
import re
import sys
import asyncio
import subprocess
import threading
import importlib
import numpy as np

tifffile = importlib.import_module("tifffile")

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox, 
    QCheckBox, QMessageBox, QDoubleSpinBox, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from astropy.io import fits

starnetExecutable = "C:/StarNet25/starnet2.exe"


def chw_float_to_tiff_u16(data):
    """Convert Siril CHW float data to HWC/HW uint16 for TIFF i/o"""
    clipped = np.clip(data, 0, 1)
    if clipped.ndim == 3 and clipped.shape[0] in (1, 3):
        clipped = np.moveaxis(clipped, 0, -1)
    if clipped.ndim == 3 and clipped.shape[-1] == 1:
        clipped = clipped[:, :, 0]
    return np.round(clipped * 65535.0).astype(np.uint16)


def tiff_u16_to_chw_float(data):
    """Convert TIFF data back to Siril CHW float32 format."""
    converted = np.array(data, dtype=np.float32) / 65535.0
    if converted.ndim == 2:
        converted = converted[np.newaxis, :, :]
    elif converted.ndim == 3 and converted.shape[-1] in (1, 3):
        converted = np.moveaxis(converted, -1, 0)
    return converted

class SirilStarnetInterface(QWidget):
    _enable_apply = pyqtSignal()

    def __init__(self):
        """Constructor for SirilStarnetInterface class"""
        super().__init__()
        self.setWindowTitle("Starnet++ v2.5.1")
        self.setFixedWidth(450)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        # Initialize Siril connection
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
        """Create the main dialog widgets."""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Starnet options group box
        options_box = QGroupBox(" Starnet Options ")
        options_layout = QVBoxLayout()
        options_box.setLayout(options_layout)
        options_box.setContentsMargins(8, 23, 8, 13)

        # Pre-stretch row
        pre_stretch_row = QHBoxLayout()
        self.pre_stretch_check = QCheckBox("Pre-stretch")
        self.pre_stretch_check.setChecked(True)
        self.pre_stretch_check.setFixedWidth(110)
        pre_stretch_row.addWidget(self.pre_stretch_check)

        self.pre_stretch_spin = QDoubleSpinBox()
        self.pre_stretch_spin.setDecimals(3)
        self.pre_stretch_spin.setMinimum(0.001)
        self.pre_stretch_spin.setMaximum(0.999)
        self.pre_stretch_spin.setValue(0.100)
        self.pre_stretch_spin.setSingleStep(0.005)
        self.pre_stretch_spin.setFixedWidth(80)
        self.pre_stretch_spin.setEnabled(True)
        pre_stretch_row.addWidget(self.pre_stretch_spin)
        pre_stretch_row.addStretch()
        self.pre_stretch_check.toggled.connect(self.pre_stretch_spin.setEnabled)
        options_layout.addLayout(pre_stretch_row)

        # starmask row
        starmask_row = QHBoxLayout()
        self.create_starmask = QCheckBox("Create starmask")
        self.create_starmask.setChecked(True)
        self.create_starmask.setFixedWidth(110)
        starmask_row.addWidget(self.create_starmask)

        self.starmask_type = QComboBox()
        self.starmask_type.addItem("Subtraction")
        self.starmask_type.addItem("Screen")
        self.starmask_type.setCurrentIndex(0)
        starmask_row.addWidget(self.starmask_type)
        starmask_row.addStretch()
        self.create_starmask.toggled.connect(self.starmask_type.setEnabled)
        options_layout.addLayout(starmask_row)

        # stride row
        stride_row = QHBoxLayout()
        self.custom_stride = QCheckBox("Custom stride")
        self.custom_stride.setChecked(False)
        self.custom_stride.setFixedWidth(110)
        stride_row.addWidget(self.custom_stride)

        self.stride_spin = QDoubleSpinBox()
        self.stride_spin.setDecimals(0)
        self.stride_spin.setMinimum(2)
        self.stride_spin.setMaximum(512)
        self.stride_spin.setValue(256)
        self.stride_spin.setSingleStep(2)
        self.stride_spin.setEnabled(False)
        stride_row.addWidget(self.stride_spin)
        stride_row.addStretch()
        self.custom_stride.toggled.connect(self.stride_spin.setEnabled)
        options_layout.addLayout(stride_row)

        # upsample checkbox
        self.upsample = QCheckBox("Upsample 2x")
        self.upsample.setChecked(False)
        options_layout.addWidget(self.upsample)

        layout.addWidget(options_box)

        # Apply button
        button_row = QHBoxLayout()
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setFixedWidth(80)
        self.apply_btn.clicked.connect(self.OnApply)
        button_row.addWidget(self.apply_btn)
        layout.addLayout(button_row)

 
    def OnApply(self):
        """Handle apply button click."""
        if not self.siril.is_image_loaded():
            QMessageBox.critical(self, "Error", "No image loaded!")
            return
        self.apply_btn.setEnabled(False)
        threading.Thread(target=lambda: asyncio.run(self.ApplyChanges()), daemon=True).start()

    async def RunStarnet(self, inputFile, outputFile, starmaskFile):
        """Run Starnet"""
        try:
            command = [
                starnetExecutable,
                f"-i {inputFile}",
                f"-o {outputFile}",
            ]

            if self.create_starmask.isChecked():
                if self.starmask_type.currentText() == "Subtraction":
                    command.append(f"-m {starmaskFile}")
                elif self.starmask_type.currentText() == "Screen":
                    command.append(f"-n {starmaskFile}")

            if self.custom_stride.isChecked():
                command.append(f"-s {int(self.stride_spin.value())}")

            if self.upsample.isChecked():
                command.append("-u")

            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=subprocess.PIPE,
                stderr=sys.stderr,
            )

            buffer = ""
            while True:
                chunk = await process.stdout.read(80)
                if not chunk:
                    break

                buffer += chunk.decode('utf-8', errors='ignore')
                lines = buffer.split('\r')

                for line in lines[:-1]:
                    match = re.search(r'(\d+(?:\.\d+)?)%', line)
                    if match:
                        percentage = float(match.group(1))
                        self.siril.update_progress("Working...", percentage / 100)

                buffer = lines[-1]

            await process.wait()

            if process.returncode != 0:
                stderr = await process.stderr.read()
                error_message = stderr.decode('utf-8', errors='ignore')
                raise subprocess.CalledProcessError(
                    process.returncode,
                    starnetExecutable,
                    error_message
                )

            return True

        except Exception as e:
            self.siril.log(f"Unhandled exception in RunCosmicClarity(): {str(e)}", s.LogColor.SALMON)
            return False

    async def ApplyChanges(self):
        pre_stretch = self.pre_stretch_check.isChecked()
        target_median = self.pre_stretch_spin.value()

        try:
            # claim the processing thread
            with self.siril.image_lock():
                # get the current image filename and construct our new temp file names
                cwd = os.path.dirname(self.siril.get_image_filename())
                inputFile = os.path.join(cwd, "starnet-temp-input.tif")
                outputFile = os.path.join(cwd, "starnet-temp-output.tif")
                starmaskFile = os.path.join(cwd, "starnet-temp-starmask.tif")
                starmaskOutputFile = f"starmask-{os.path.basename(self.siril.get_image_filename())}"

                # get current image data and save to temp file
                data = self.siril.get_image_pixeldata()
                if pre_stretch:
                    self.siril.log(f"Pre-stretch: {target_median:.3f}", s.LogColor.BLUE)
                    data = mtf(target_median, data)
                tiff_data = chw_float_to_tiff_u16(data)
                tifffile.imwrite(inputFile, tiff_data)

                # kick off the starnet process
                self.siril.update_progress("Starnet starting...", 0)
                self.siril.log("Running Starnet...", s.LogColor.BLUE)
                success = await self.RunStarnet(inputFile, outputFile, starmaskFile)

                if success:
                    # load the starmask (if it was created) and save it as a fits file
                    if self.create_starmask.isChecked() and os.path.exists(starmaskFile):
                        starmask_data = tifffile.imread(starmaskFile)
                        starmask_data = tiff_u16_to_chw_float(starmask_data)
                        hdu = fits.PrimaryHDU(starmask_data)
                        hdu.writeto(starmaskOutputFile, overwrite=True)

                    # load the resulting starless image and set it in Siril
                    data = tifffile.imread(outputFile)
                    data = tiff_u16_to_chw_float(data)
                    if pre_stretch:
                        data = mtf((1.0 - target_median), data)
                    
                    save_state = f"Starnet"
                    if pre_stretch:
                        save_state += f", pre-stretch={target_median:.3f}"
                    if self.custom_stride.isChecked():
                        save_state += f", stride={int(self.stride_spin.value())}"
                    if self.upsample.isChecked():
                        save_state += ", upsample"
                    self.siril.undo_save_state(save_state)
                    self.siril.set_image_pixeldata(data)
                    self.siril.log("Starnet complete.", s.LogColor.GREEN)
                else:
                    self.siril.log("Starnet failed.", s.LogColor.SALMON)

        except Exception as e:
            self.siril.log(f"Unhandled exception in ApplyChanges(): {str(e)}", s.LogColor.SALMON)

        finally:
            if os.path.exists(inputFile):
                os.remove(inputFile)
            if os.path.exists(outputFile):
                os.remove(outputFile)
            if os.path.exists(starmaskFile):
                os.remove(starmaskFile)

            # re-enable the Apply button from the main thread via signal
            self._enable_apply.emit()
            self.siril.reset_progress()

def mtf(m, img):
    """Midtones transfer function. Returns ((m-1)*x) / ((2m-1)*x - m)"""
    if m == 0.5:
        return img
    clipped = np.clip(img, 0, 1)
    return ((m - 1) * clipped) / (((2 * m - 1) * clipped) - m)


def main():
    try:
        app = QApplication(sys.argv)
        window = SirilStarnetInterface()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
