#
# Simplfied Cosmic Clarity sharpening interface for Siril
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
from astropy.io import fits
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QSlider, QRadioButton, QCheckBox, QMessageBox,
    QDoubleSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal

sharpenExecutable = "C:/Program Files/SetiAstroSuitePro/setiastrosuitepro.exe"

class SirilCosmicClarityInterface(QWidget):
    _enable_apply = pyqtSignal()

    def __init__(self):
        """Constructor for SirilCosmicClarityInterface class"""
        super().__init__()
        self.setWindowTitle("Cosmic Clarity Sharpening")
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

        # Sharpening mode group box
        mode_box = QGroupBox(" Sharpening Mode ")
        mode_layout = QVBoxLayout()
        mode_box.setLayout(mode_layout)
        mode_box.setContentsMargins(8, 23, 8, 13)

        self.stellar_only_radio = QRadioButton("Stellar Only")
        self.non_stellar_only_radio = QRadioButton("Non-Stellar Only")
        self.both_radio = QRadioButton("Both")
        self.both_radio.setChecked(True)
        mode_layout.addWidget(self.stellar_only_radio)
        mode_layout.addWidget(self.non_stellar_only_radio)
        mode_layout.addWidget(self.both_radio)
        layout.addWidget(mode_box)

        # Sharpening strength group box
        strength_box = QGroupBox(" Sharpening Strength ")
        strength_layout = QVBoxLayout()
        strength_box.setLayout(strength_layout)
        strength_box.setContentsMargins(8, 23, 8, 13)

        # Non-stellar PSF slider (range 1.0–8.0, stored as int 10–80)
        psf_row = QHBoxLayout()
        psf_label = QLabel("Non-Stellar PSF:")
        psf_label.setFixedWidth(130)
        psf_row.addWidget(psf_label)
        self.non_stellar_psf_slider = QSlider(Qt.Orientation.Horizontal)
        self.non_stellar_psf_slider.setMinimum(10)
        self.non_stellar_psf_slider.setMaximum(80)
        self.non_stellar_psf_slider.setValue(30)
        psf_row.addWidget(self.non_stellar_psf_slider, 1)
        self.non_stellar_psf_label = QLabel("3.0")
        self.non_stellar_psf_label.setFixedWidth(35)
        psf_row.addWidget(self.non_stellar_psf_label)
        self.non_stellar_psf_slider.valueChanged.connect(
            lambda v: self.non_stellar_psf_label.setText(f"{v / 10:.1f}")
        )
        strength_layout.addLayout(psf_row)

        # Non-stellar strength slider (range 0.0–1.0, stored as int 0–100)
        non_stellar_row = QHBoxLayout()
        non_stellar_label = QLabel("Non-Stellar Strength:")
        non_stellar_label.setFixedWidth(130)
        non_stellar_row.addWidget(non_stellar_label)
        self.non_stellar_str_slider = QSlider(Qt.Orientation.Horizontal)
        self.non_stellar_str_slider.setMinimum(0)
        self.non_stellar_str_slider.setMaximum(100)
        self.non_stellar_str_slider.setValue(85)
        non_stellar_row.addWidget(self.non_stellar_str_slider, 1)
        self.non_stellar_str_label = QLabel("0.85")
        self.non_stellar_str_label.setFixedWidth(35)
        non_stellar_row.addWidget(self.non_stellar_str_label)
        self.non_stellar_str_slider.valueChanged.connect(
            lambda v: self.non_stellar_str_label.setText(f"{v / 100:.2f}")
        )
        strength_layout.addLayout(non_stellar_row)

        # Stellar strength slider (range 0.0–1.0, stored as int 0–100)
        stellar_row = QHBoxLayout()
        stellar_label = QLabel("Stellar Strength:")
        stellar_label.setFixedWidth(130)
        stellar_row.addWidget(stellar_label)
        self.stellar_str_slider = QSlider(Qt.Orientation.Horizontal)
        self.stellar_str_slider.setMinimum(0)
        self.stellar_str_slider.setMaximum(100)
        self.stellar_str_slider.setValue(60)
        stellar_row.addWidget(self.stellar_str_slider, 1)
        self.stellar_str_label = QLabel("0.60")
        self.stellar_str_label.setFixedWidth(35)
        stellar_row.addWidget(self.stellar_str_label)
        self.stellar_str_slider.valueChanged.connect(
            lambda v: self.stellar_str_label.setText(f"{v / 100:.2f}")
        )
        strength_layout.addLayout(stellar_row)
        layout.addWidget(strength_box)

        # Options group box
        options_box = QGroupBox(" Options ")
        options_layout = QVBoxLayout()
        options_box.setLayout(options_layout)
        options_box.setContentsMargins(8, 23, 8, 13)

        self.use_gpu_check = QCheckBox("Use GPU")
        self.use_gpu_check.setChecked(True)
        options_layout.addWidget(self.use_gpu_check)

        self.sharpen_channels_check = QCheckBox("Sharpen channels separately")
        self.sharpen_channels_check.setChecked(False)
        options_layout.addWidget(self.sharpen_channels_check)

        self.use_auto_psf_check = QCheckBox("Use automatic PSF")
        self.use_auto_psf_check.setChecked(True)
        options_layout.addWidget(self.use_auto_psf_check)

        # Pre-stretch row
        pre_stretch_row = QHBoxLayout()
        self.pre_stretch_check = QCheckBox("Pre-stretch")
        self.pre_stretch_check.setChecked(True)
        pre_stretch_row.addWidget(self.pre_stretch_check)
        self.pre_stretch_spin = QDoubleSpinBox()
        self.pre_stretch_spin.setDecimals(3)
        self.pre_stretch_spin.setMinimum(0.001)
        self.pre_stretch_spin.setMaximum(0.999)
        self.pre_stretch_spin.setValue(0.100)
        self.pre_stretch_spin.setSingleStep(0.001)
        self.pre_stretch_spin.setFixedWidth(80)
        self.pre_stretch_spin.setEnabled(True)
        pre_stretch_row.addWidget(self.pre_stretch_spin)
        pre_stretch_row.addStretch()
        self.pre_stretch_check.toggled.connect(self.pre_stretch_spin.setEnabled)
        options_layout.addLayout(pre_stretch_row)
        layout.addWidget(options_box)

        # Apply button
        button_row = QHBoxLayout()
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setFixedWidth(80)
        self.apply_btn.clicked.connect(self.OnApply)
        button_row.addWidget(self.apply_btn)
        layout.addLayout(button_row)

    def _sharpening_mode(self):
        """Return the currently selected sharpening mode string."""
        if self.stellar_only_radio.isChecked():
            return "Stellar Only"
        if self.non_stellar_only_radio.isChecked():
            return "Non-Stellar Only"
        return "Both"

    def OnApply(self):
        """Handle apply button click."""
        if not self.siril.is_image_loaded():
            QMessageBox.critical(self, "Error", "No image loaded!")
            return
        self.apply_btn.setEnabled(False)
        threading.Thread(target=lambda: asyncio.run(self.ApplyChanges()), daemon=True).start()

    async def RunCosmicClarity(self, inputFile, outputFile):
        """Run Cosmic Clarity"""
        try:
            # setiastro sharpen doesn't like it if you don't pass in all the arguments, 
            # even if you don't use them, e.g. PSF strength
            mode = self._sharpening_mode()
            stellar_str = f"{self.stellar_str_slider.value() / 100:.2f}"
            non_stellar_str = f"{self.non_stellar_str_slider.value() / 100:.2f}"
            non_stellar_psf = f"{self.non_stellar_psf_slider.value() / 10:.1f}"

            command = [
                sharpenExecutable,
                "cc",
                "sharpen",
                f"-i={inputFile}",
                f"-o={outputFile}",
                f"--sharpening-mode={mode}",
                f"--stellar-amount={stellar_str}",
                f"--nonstellar-amount={non_stellar_str}",
                f"--nonstellar-psf={non_stellar_psf}",
            ]

            if not self.use_gpu_check.isChecked():
                command.append("--disable_gpu")

            if self.sharpen_channels_check.isChecked():
                command.append("--sharpen_channels_separately")

            if self.use_auto_psf_check.isChecked():
                command.append("--auto-psf")

            self.siril.log(f"Sharpening mode: {mode}", s.LogColor.BLUE)
            self.siril.log(f"Stellar sharpening: {stellar_str}", s.LogColor.BLUE)
            self.siril.log(f"Non-stellar sharpening: {non_stellar_str}", s.LogColor.BLUE)
            if self.use_auto_psf_check.isChecked():
                self.siril.log("PSF: auto", s.LogColor.BLUE)
            else:
                self.siril.log(f"PSF: {non_stellar_psf}", s.LogColor.BLUE)

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
                        self.siril.update_progress("Sharpening...", percentage / 100)

                buffer = lines[-1]

            await process.wait()

            if process.returncode != 0:
                stderr = await process.stderr.read()
                error_message = stderr.decode('utf-8', errors='ignore')
                raise subprocess.CalledProcessError(
                    process.returncode,
                    sharpenExecutable,
                    error_message
                )

            return True

        except Exception as e:
            self.siril.log(f"Unhandled exception in RunCosmicClarity(): {str(e)}", s.LogColor.SALMON)
            return False

    async def ApplyChanges(self):
        pre_stretch = self.pre_stretch_check.isChecked()
        m = self.pre_stretch_spin.value() if pre_stretch else None

        try:
            # claim the processing thread
            with self.siril.image_lock():
                # get the current image filename and construct our new temp file names
                cwd = os.path.dirname(self.siril.get_image_filename())
                inputFile = os.path.join(cwd, "cc-sharpen-temp-input.fits")
                outputFile = os.path.join(cwd, "cc-sharpen-temp-output.fits")

                # get current image data and save to temp file
                data = self.siril.get_image_pixeldata()
                if pre_stretch:
                    self.siril.log(f"Pre-stretch: {m:.3f}", s.LogColor.BLUE)
                    data = mtf(m, data)
                hdu = fits.PrimaryHDU(data)
                hdu.writeto(inputFile, overwrite=True)

                # kick off the sharpening process
                self.siril.update_progress("Seti Astro Cosmic Clarity Sharpen starting...", 0)
                success = await self.RunCosmicClarity(inputFile, outputFile)

                if success:
                    # load the resulting image and set it in Siril
                    with fits.open(outputFile) as hdul:
                        data = hdul[0].data
                        if data.dtype != np.float32:
                            data = np.array(data, dtype=np.float32)
                        if pre_stretch:
                            inv_m = 1.0 - m
                            data = mtf(inv_m, data)
                        mode = self._sharpening_mode()
                        save_state = f"CC: '{mode}', "
                        if mode in ("Stellar Only", "Both"):
                            save_state += f"stellar={self.stellar_str_slider.value() / 100:.2f}, "
                        if mode in ("Non-Stellar Only", "Both"):
                            save_state += f"non-stellar={self.non_stellar_str_slider.value() / 100:.2f}, "
                        if self.use_auto_psf_check.isChecked():
                            save_state += "PSF: auto"
                        else:
                            save_state += f"PSF={self.non_stellar_psf_slider.value() / 10:.1f}"
                        if pre_stretch:
                            save_state += f", pre-stretch={m:.3f}"
                        self.siril.undo_save_state(save_state)
                        self.siril.set_image_pixeldata(data)
                    self.siril.log("Sharpening complete.", s.LogColor.GREEN)
                else:
                    self.siril.log("Sharpening failed.", s.LogColor.SALMON)

        except Exception as e:
            self.siril.log(f"Unhandled exception in ApplyChanges(): {str(e)}", s.LogColor.SALMON)

        finally:
            if os.path.exists(inputFile):
                os.remove(inputFile)
            if os.path.exists(outputFile):
                os.remove(outputFile)

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
        window = SirilCosmicClarityInterface()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
