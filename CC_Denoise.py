#
# Simplfied Cosmic Clarity Denoise interface for Siril
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2026 lindner234 <AT> gmail
#

import sirilpy as s
s.ensure_installed("PyQt6")
s.ensure_installed("astropy")
s.ensure_installed("numpy")

import os
import re
import sys
import asyncio
import subprocess
import threading

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QSlider, QRadioButton, QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from astropy.io import fits
import numpy as np

denoiseExecutable = "C:/Program Files/SetiAstroSuitePro/setiastrosuitepro.exe"

class SirilDenoiseInterface(QWidget):
    _enable_apply = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cosmic Clarity Denoise")
        self.setFixedWidth(400)
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
        """Create the GUI widgets for the Cosmic Clarity Denoise interface."""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Denoise Mode Group Box
        mode_box = QGroupBox(" Denoise Mode ")
        mode_layout = QVBoxLayout()
        mode_box.setLayout(mode_layout)
        mode_box.setContentsMargins(8, 23, 8, 13)

        self.luminance_radio = QRadioButton("Luminance")
        self.full_radio = QRadioButton("Full")
        self.full_radio.setChecked(True)
        mode_layout.addWidget(self.luminance_radio)
        mode_layout.addWidget(self.full_radio)
        layout.addWidget(mode_box)

        # Denoise Strength Group Box
        strength_box = QGroupBox(" Denoise Strength ")
        strength_layout = QVBoxLayout()
        strength_box.setLayout(strength_layout)
        strength_box.setContentsMargins(8, 23, 8, 13)

        # Luminance strength slider
        lum_row = QHBoxLayout()
        lum_label = QLabel("Luminance:")
        lum_label.setFixedWidth(75)
        lum_row.addWidget(lum_label)
        self.lum_slider = QSlider(Qt.Orientation.Horizontal)
        self.lum_slider.setMinimum(0)
        self.lum_slider.setMaximum(100)
        self.lum_slider.setValue(75)
        lum_row.addWidget(self.lum_slider, 1)
        self.lum_value_label = QLabel("0.75")
        self.lum_value_label.setFixedWidth(35)
        lum_row.addWidget(self.lum_value_label)
        self.lum_slider.valueChanged.connect(
            lambda v: self.lum_value_label.setText(f"{v / 100:.2f}")
        )
        strength_layout.addLayout(lum_row)

        # Color strength slider
        color_row = QHBoxLayout()
        color_label = QLabel("Color:")
        color_label.setFixedWidth(75)
        color_row.addWidget(color_label)
        self.color_slider = QSlider(Qt.Orientation.Horizontal)
        self.color_slider.setMinimum(0)
        self.color_slider.setMaximum(100)
        self.color_slider.setValue(55)
        color_row.addWidget(self.color_slider, 1)
        self.color_value_label = QLabel("0.55")
        self.color_value_label.setFixedWidth(35)
        color_row.addWidget(self.color_value_label)
        self.color_slider.valueChanged.connect(
            lambda v: self.color_value_label.setText(f"{v / 100:.2f}")
        )
        strength_layout.addLayout(color_row)
        layout.addWidget(strength_box)

        # Options Group Box
        options_box = QGroupBox(" Options ")
        options_layout = QVBoxLayout()
        options_box.setLayout(options_layout)
        options_box.setContentsMargins(8, 23, 8, 13)

        self.use_gpu_check = QCheckBox("Use GPU")
        self.use_gpu_check.setChecked(True)
        options_layout.addWidget(self.use_gpu_check)

        self.separate_channels_check = QCheckBox("Separate RGB channels")
        self.separate_channels_check.setChecked(False)
        options_layout.addWidget(self.separate_channels_check)
        layout.addWidget(options_box)

        # Apply Button
        button_row = QHBoxLayout()
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setFixedWidth(80)
        self.apply_btn.clicked.connect(self.OnApply)
        button_row.addWidget(self.apply_btn)
        layout.addLayout(button_row)

    def OnApply(self):
        """Callback for the Apply button."""
        if not self.siril.is_image_loaded():
            QMessageBox.critical(self, "Error", "No image loaded!")
            return
        self.apply_btn.setEnabled(False)
        threading.Thread(target=lambda: asyncio.run(self.ApplyChanges()), daemon=True).start()

    async def RunCosmicClarity(self, inputFile, outputFile):
        """Run Cosmic Clarity denoise."""
        try:
            denoise_mode = "luminance" if self.luminance_radio.isChecked() else "full"
            lum_strength = f"{self.lum_slider.value() / 100:.2f}"
            color_strength = f"{self.color_slider.value() / 100:.2f}"

            command = [
                denoiseExecutable,
                "cc",
                "denoise",
                f"-i={inputFile}",
                f"-o={outputFile}",
                f"--denoise-mode={denoise_mode}",
                f"--denoise-luma={lum_strength}",
                f"--denoise-color={color_strength}"
            ]

            if not self.use_gpu_check.isChecked():
                command.append("--disable_gpu")

            self.siril.log(f"Denoise mode: {denoise_mode}", s.LogColor.BLUE)
            self.siril.log(f"Luma strength: {lum_strength}", s.LogColor.BLUE)
            self.siril.log(f"Color strength: {color_strength}", s.LogColor.BLUE)

            if self.separate_channels_check.isChecked():
                command.append("--separate-channels")
                self.siril.log("Denoise separate channels", s.LogColor.BLUE)

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
                    match = re.search(r'(\d+)%', line)
                    if match:
                        percentage = float(match.group(1))
                        self.siril.update_progress("Denoising...", percentage / 100)

                buffer = lines[-1]

            await process.wait()

            if process.returncode != 0:
                stderr = await process.stderr.read()
                error_message = stderr.decode('utf-8', errors='ignore')
                raise subprocess.CalledProcessError(
                    process.returncode,
                    denoiseExecutable,
                    error_message
                )

            return True

        except Exception as e:
            self.siril.log(f"Unhandled exception in RunCosmicClarity(): {str(e)}", s.LogColor.SALMON)
            return False

    async def ApplyChanges(self):
        try:
            # Claim the processing thread
            with self.siril.image_lock():
                # get the current image filename and construct our new temp file names
                cwd = os.path.dirname(self.siril.get_image_filename())
                inputFile = os.path.join(cwd, "cc-denoise-temp-input.fits")
                outputFile = os.path.join(cwd, "cc-denoise-temp-output.fits")

                # get current image data and save to our temp input file
                data = self.siril.get_image_pixeldata()
                hdu = fits.PrimaryHDU(data)
                hdu.writeto(inputFile, overwrite=True)

                # kick off the denoise process
                self.siril.update_progress("Cosmic Clarity Denoise starting...", 0)
                success = await self.RunCosmicClarity(inputFile, outputFile)

                # load up the file on success and get out of dodge
                if success:
                    # load the resulting image and set it in Siril
                    with fits.open(outputFile) as hdul:
                        data = hdul[0].data
                        if data.dtype != np.float32:
                            data = np.array(data, dtype=np.float32)
                        denoise_mode = "luminance" if self.luminance_radio.isChecked() else "full"
                        self.siril.undo_save_state(f"CC denoise: mode='{denoise_mode}' "
                                                   f"luma={self.lum_slider.value() / 100:.2f} "
                                                   f"color={self.color_slider.value() / 100:.2f}")
                        self.siril.set_image_pixeldata(data)
                    self.siril.log("Denoise complete.", s.LogColor.GREEN)
                else:
                    self.siril.log("Denoise failed.", s.LogColor.SALMON)

        except Exception as e:
            self.siril.log(f"Unhandled exception in ApplyChanges(): {str(e)}", s.LogColor.SALMON)
            self.siril.log("Denoise failed.", s.LogColor.SALMON)

        finally:
            if os.path.exists(inputFile):
                os.remove(inputFile)
            if os.path.exists(outputFile):
                os.remove(outputFile)

            # re-enable the Apply button from the main thread via signal
            self._enable_apply.emit()
            self.siril.reset_progress()

def main():
    try:
        app = QApplication(sys.argv)
        window = SirilDenoiseInterface()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
