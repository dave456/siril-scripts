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
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
    QLabel, QPushButton, QGroupBox, QSlider, QCheckBox, QMessageBox,
    QDoubleSpinBox, QSpinBox, QDialog, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QSettings, pyqtSignal

# Settings keys
SETTINGS_ORG = "CaribouAstro"
SETTINGS_APP = "CosmicClaritySharpen"
DEFAULT_EXE = "C:/Program Files/SetiAstroSuitePro/setiastrosuitepro.exe"

class SirilCosmicClarityInterface(QWidget):
    _enable_apply = pyqtSignal()

    def __init__(self):
        """Constructor for SirilCosmicClarityInterface class"""
        super().__init__()
        self.setWindowTitle("Cosmic Clarity Sharpening")
        self.setFixedWidth(450)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.settings = QSettings(SETTINGS_ORG, SETTINGS_APP)

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
        self.LoadSettings()

    def LoadSettings(self):
        """Load settings from QSettings and update the UI accordingly."""
        s = self.settings
        self.sharpen_path = s.value("sharpen_path", DEFAULT_EXE)
        self.sharpen_mode.setCurrentIndex(int(s.value("sharpen_mode", 2)))
        self.correction_mode.setCurrentIndex(int(s.value("correction_mode", 0)))
        self.non_stellar_psf_slider.setValue(int(s.value("non_stellar_psf", 30)))
        self.non_stellar_psf_label.setText(f"{self.non_stellar_psf_slider.value() / 10:.1f}")
        self.non_stellar_str_slider.setValue(int(s.value("non_stellar_str", 85)))
        self.non_stellar_str_label.setText(f"{self.non_stellar_str_slider.value() / 100:.2f}")
        self.stellar_str_slider.setValue(int(s.value("stellar_str", 50)))
        self.stellar_str_label.setText(f"{self.stellar_str_slider.value() / 100:.2f}")
    
    def SaveSettings(self):
        """Save a select set of settings via QSettings."""
        s = self.settings
        s.setValue("sharpen_path", self.sharpen_path)
        s.setValue("sharpen_mode", self.sharpen_mode.currentIndex())
        s.setValue("correction_mode", self.correction_mode.currentIndex())
        s.setValue("non_stellar_psf", self.non_stellar_psf_slider.value())
        s.setValue("non_stellar_str", self.non_stellar_str_slider.value())
        s.setValue("stellar_str", self.stellar_str_slider.value())
    
    def closeEvent(self, event):
        self.SaveSettings()
        super().closeEvent(event)

    def CreateWidgets(self):
        """Create the main dialog widgets."""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Sharpening mode group box
        mode_box = QGroupBox(" Sharpening Mode ")
        mode_layout = QVBoxLayout()
        mode_box.setLayout(mode_layout)
        mode_box.setContentsMargins(8, 23, 8, 13)

        sharpen_mode_row = QHBoxLayout()
        sharpen_mode_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        sharpen_mode_label = QLabel("Objects:")
        sharpen_mode_label.setFixedWidth(80)
        sharpen_mode_row.addWidget(sharpen_mode_label)
        self.sharpen_mode = QComboBox()
        self.sharpen_mode.addItems([
            "Stellar Only", 
            "Non-Stellar Only", 
            "Stellar & Non-Stellar",
        ])
        self.sharpen_mode.setCurrentIndex(2)  # default to "Both"
        self.sharpen_mode.setFixedWidth(150)
        sharpen_mode_row.addWidget(self.sharpen_mode, 1)
        mode_layout.addLayout(sharpen_mode_row)

        correction_mode_row = QHBoxLayout()
        correction_mode_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        correction_mode_label = QLabel("Aberrations:")
        correction_mode_label.setFixedWidth(80)
        correction_mode_row.addWidget(correction_mode_label)
        self.correction_mode = QComboBox()
        self.correction_mode.addItems([
            "Sharpen Only",
            "Correct Only",
            "Correct & Sharpen",
        ])
        self.correction_mode.setCurrentIndex(0)  # default to "Sharpen Only"
        self.correction_mode.setFixedWidth(150)
        correction_mode_row.addWidget(self.correction_mode, 1)
        mode_layout.addLayout(correction_mode_row)
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

        # Advanced options group box
        advanced_box = QGroupBox(" Advanced Options ")
        advanced_layout = QVBoxLayout()
        advanced_box.setLayout(advanced_layout)
        advanced_box.setContentsMargins(8, 23, 8, 13)

        # Chunk size row
        chunk_row = QHBoxLayout()
        chunk_label = QLabel("Chunk Size:")
        chunk_label.setFixedWidth(82)
        chunk_row.addWidget(chunk_label)
        self.chunk_size_spin = QSpinBox()
        self.chunk_size_spin.setMinimum(32)
        self.chunk_size_spin.setMaximum(8192)
        self.chunk_size_spin.setSingleStep(32)
        self.chunk_size_spin.setValue(512)
        self.chunk_size_spin.setFixedWidth(80)
        chunk_row.addWidget(self.chunk_size_spin)
        chunk_row.addStretch()
        advanced_layout.addLayout(chunk_row)

        # Overlap row
        overlap_row = QHBoxLayout()
        overlap_label = QLabel("Overlap:")
        overlap_label.setFixedWidth(82)
        overlap_row.addWidget(overlap_label)
        self.overlap_spin = QSpinBox()
        self.overlap_spin.setMinimum(0)
        self.overlap_spin.setMaximum(4096)
        self.overlap_spin.setSingleStep(32)
        self.overlap_spin.setValue(64)
        self.overlap_spin.setFixedWidth(80)
        overlap_row.addWidget(self.overlap_spin)
        overlap_row.addStretch()
        advanced_layout.addLayout(overlap_row)

        layout.addWidget(advanced_box)

        # Apply button
        button_row = QHBoxLayout()
        button_row.addSpacing(36)
        button_row.addStretch()
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setFixedWidth(80)
        self.apply_btn.clicked.connect(self.OnApply)
        button_row.addWidget(self.apply_btn)
        button_row.addStretch()

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.setFixedWidth(36)
        self.settings_btn.setFixedHeight(self.apply_btn.sizeHint().height())
        self.settings_btn.clicked.connect(self.OpenSettings)
        button_row.addWidget(self.settings_btn)

        layout.addLayout(button_row)

    def sharpeningMode(self):
        """Return the currently selected sharpening mode string."""
        if self.sharpen_mode.currentIndex() == 0:
            return "Stellar Only"
        elif self.sharpen_mode.currentIndex() == 1:
            return "Non-Stellar Only"
        elif self.sharpen_mode.currentIndex() == 2:
            return "Both"
        
    def correctionMode(self):
        """Return the currently selected aberration correction mode string."""
        if self.correction_mode.currentIndex() == 0:
            return "sharpen_only"
        elif self.correction_mode.currentIndex() == 1:
            return "correct_only"
        elif self.correction_mode.currentIndex() == 2:
            return "correct_sharpen"

    def OnApply(self):
        """Handle apply button click."""
        if not self.siril.is_image_loaded():
            QMessageBox.critical(self, "Error", "No image loaded!")
            return
        if not os.path.isfile(self.sharpen_path):
            QMessageBox.critical(self, "Error", f"Sharpen executable not found:\n{self.sharpen_path}")
            return
        self.apply_btn.setEnabled(False)
        threading.Thread(target=lambda: asyncio.run(self.ApplyChanges()), daemon=True).start()

    def OpenSettings(self):
        dlg = SettingsDialog(self)
        dlg.exec()

    async def RunCosmicClarity(self, inputFile, outputFile):
        """Run Cosmic Clarity"""
        try:
            # setiastro sharpen doesn't like it if you don't pass in all the arguments, 
            # even if you don't use them, e.g. PSF strength
            sharpenMode = self.sharpeningMode()
            correctionMode = self.correctionMode()
            stellar_str = f"{self.stellar_str_slider.value() / 100:.2f}"
            non_stellar_str = f"{self.non_stellar_str_slider.value() / 100:.2f}"
            non_stellar_psf = f"{self.non_stellar_psf_slider.value() / 10:.1f}"

            command = [
                self.sharpen_path,
                "cc",
                "sharpen",
                f"-i={inputFile}",
                f"-o={outputFile}",
                f"--sharpening-mode={sharpenMode}",
                f"--stellar-amount={stellar_str}",
                f"--nonstellar-amount={non_stellar_str}",
                f"--nonstellar-psf={non_stellar_psf}",
                f"--stellar-correct-mode={correctionMode}",
                f"--chunk-size={self.chunk_size_spin.value()}",
                f"--overlap={self.overlap_spin.value()}",
            ]

            if not self.use_gpu_check.isChecked():
                command.append("--disable_gpu")

            if self.sharpen_channels_check.isChecked():
                command.append("--sharpen_channels_separately")

            if self.use_auto_psf_check.isChecked():
                command.append("--auto-psf")

            self.siril.log(f"Sharpening mode: {sharpenMode}", s.LogColor.BLUE)
            self.siril.log(f"Correction mode: {correctionMode}", s.LogColor.BLUE)
            self.siril.log(f"Stellar sharpening: {stellar_str}", s.LogColor.BLUE)
            self.siril.log(f"Non-stellar sharpening: {non_stellar_str}", s.LogColor.BLUE)
            if self.use_auto_psf_check.isChecked():
                self.siril.log("PSF: auto", s.LogColor.BLUE)
            else:
                self.siril.log(f"PSF: {non_stellar_psf}", s.LogColor.BLUE)
            self.siril.log(f"Chunk size: {self.chunk_size_spin.value()}", s.LogColor.BLUE)
            self.siril.log(f"Overlap: {self.overlap_spin.value()}", s.LogColor.BLUE)

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
                    self.sharpen_path,
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
                        mode = self.sharpeningMode()
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

class SettingsDialog(QDialog):
    """Settings dialog for the Cosmic Clarity Sharpening interface."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedWidth(450)
        self.settings = QSettings(SETTINGS_ORG, SETTINGS_APP)

        layout = QVBoxLayout()
        self.setLayout(layout)

        location_box = QGroupBox(" Executable Location ")
        location_layout = QVBoxLayout()
        location_box.setLayout(location_layout)

        location_row = QHBoxLayout()
        location_label = QLabel("Path:")
        location_row.addWidget(location_label)
        self.location_lineedit = QPlainTextEdit()
        self.location_lineedit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.location_lineedit.setFixedHeight(56)
        self.sharpen_path = self.settings.value("sharpen_path", DEFAULT_EXE)
        self.location_lineedit.setPlainText(self.sharpen_path)
        location_row.addWidget(self.location_lineedit, 1)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(lambda: self.OnSelectFile("sharpen_path", self.location_lineedit))
        location_row.addWidget(browse_btn)
        location_layout.addLayout(location_row)
        layout.addWidget(location_box)
        layout.addSpacing(10)

        # ok and cancel buttons
        button_row = QHBoxLayout()
        button_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ok_btn = QPushButton("OK")
        ok_btn.setFixedWidth(80)
        ok_btn.clicked.connect(self.OnOK)
        button_row.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        layout.addLayout(button_row)
        
    def OnOK(self):
        """Handle OK button click."""
        self.sharpen_path = self.location_lineedit.toPlainText().strip()
        self.settings.setValue("sharpen_path", self.sharpen_path)
        self.close()

    def OnSelectFile(self, file_attr: str, lineedit: QPlainTextEdit):
        """Open a file dialog to select a file and update the line edit."""
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File", "", "Executable Files (*.exe);;All Files (*)")
        if file_path:
            setattr(self, file_attr, file_path)
            lineedit.setPlainText(file_path)

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
