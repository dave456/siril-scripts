#
# Simplfied GraXpert interface for Siril
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2026 lindner234 <AT> gmail
#

import sirilpy as s
s.ensure_installed("PyQt6")
s.ensure_installed("astropy")
s.ensure_installed("numpy")

import os
import sys
import subprocess
import threading
from astropy.io import fits
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QSlider, QMessageBox, QRadioButton
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

graxpertExecutable = "c:/GraXpert2/GraXpert.exe"


class SirilGraxpertInterface(QWidget):
    _enable_apply = pyqtSignal()
    _close_requested = pyqtSignal()

    def __init__(self):
        """Constructor for the GraXpert denoise UI."""
        super().__init__()
        self.setWindowTitle("GraXpert")
        self.setFixedWidth(380)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        # Initialize Siril connection
        self.siril = s.SirilInterface()

        try:
            self.siril.connect()
        except s.SirilConnectionError:
            QMessageBox.critical(self, "Error", "Failed to connect to Siril")
            self.close()
            return

        self.progress = 0.0
        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(1000)
        self.progress_timer.timeout.connect(self.UpdateProgress)

        self._enable_apply.connect(self.OnThreadComplete)
        self._close_requested.connect(self.close)
        self.CreateWidgets()

    def CreateWidgets(self):
        """Create the main dialog widgets."""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # mode box to determine what operation we are running
        mode_box = QGroupBox(" Mode ")
        mode_layout = QVBoxLayout()
        mode_box.setLayout(mode_layout)
        mode_box.setContentsMargins(8, 23, 8, 13)
        
        self.mode_bge_radio = QRadioButton("Background Extraction")
        self.mode_bge_radio.toggled.connect(self.OnToggleMode)
        self.mode_denoise_radio = QRadioButton("Denoise")
        self.mode_denoise_radio.toggled.connect(self.OnToggleMode)
        mode_layout.addWidget(self.mode_bge_radio)
        mode_layout.addWidget(self.mode_denoise_radio)
        layout.addWidget(mode_box)

        # background extraction options
        bge_options_box = QGroupBox(" Background Extraction ")
        bge_options_layout = QVBoxLayout()
        bge_options_box.setLayout(bge_options_layout)
        bge_options_box.setContentsMargins(8, 23, 8, 13)

        smoothing_row = QHBoxLayout()
        smoothing_label = QLabel("Smoothing:")
        smoothing_label.setFixedWidth(70)
        smoothing_row.addWidget(smoothing_label)

        self.smoothing_slider = QSlider(Qt.Orientation.Horizontal)
        self.smoothing_slider.setMinimum(0)
        self.smoothing_slider.setMaximum(100)
        self.smoothing_slider.setValue(25)
        smoothing_row.addWidget(self.smoothing_slider, 1)

        self.smoothing_value_label = QLabel("0.25")
        self.smoothing_value_label.setFixedWidth(35)
        smoothing_row.addWidget(self.smoothing_value_label)
        self.smoothing_slider.valueChanged.connect(
            lambda value: self.smoothing_value_label.setText(f"{value / 100:.2f}")
        )
        bge_options_layout.addLayout(smoothing_row)
        layout.addWidget(bge_options_box)

        # denoise options
        denoise_options_box = QGroupBox(" Denoise ")
        denoise_options_layout = QVBoxLayout()
        denoise_options_box.setLayout(denoise_options_layout)
        denoise_options_box.setContentsMargins(8, 23, 8, 13)

        strength_row = QHBoxLayout()
        strength_label = QLabel("Strength:")
        strength_label.setFixedWidth(70)
        strength_row.addWidget(strength_label)

        self.strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.strength_slider.setMinimum(0)
        self.strength_slider.setMaximum(100)
        self.strength_slider.setValue(80)
        strength_row.addWidget(self.strength_slider, 1)

        self.strength_value_label = QLabel("0.80")
        self.strength_value_label.setFixedWidth(35)
        strength_row.addWidget(self.strength_value_label)
        self.strength_slider.valueChanged.connect(
            lambda value: self.strength_value_label.setText(f"{value / 100:.2f}")
        )
        self.strength_slider.setEnabled(False)
        denoise_options_layout.addLayout(strength_row)
        layout.addWidget(denoise_options_box)

        # Set initial mode only after dependent widgets are created.
        self.mode_bge_radio.setChecked(True)

        button_row = QHBoxLayout()
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setFixedWidth(80)
        self.apply_btn.clicked.connect(self.OnApply)
        button_row.addWidget(self.apply_btn)
        layout.addLayout(button_row)

    def OnToggleMode(self):
        """Handle mode toggle between background extraction and denoise."""
        if self.mode_bge_radio.isChecked():
            self.smoothing_slider.setEnabled(True)
            self.strength_slider.setEnabled(False)
        else:
            self.smoothing_slider.setEnabled(False)
            self.strength_slider.setEnabled(True)
    
    def OnApply(self):
        """Handle apply button click."""
        if not self.siril.is_image_loaded():
            QMessageBox.critical(self, "Error", "No image loaded")
            return
        self.apply_btn.setEnabled(False)
        self.progress = 0.0
        self.progress_timer.start()
        threading.Thread(target=self.ApplyChanges, daemon=True).start()

    def ApplyChanges(self):
        """Run GraXpert denoise in a background thread and load the result into Siril."""
        input_file = ""
        output_file = ""
        success = False

        try:
            # Claim the processing thread
            with self.siril.image_lock():
                # Read user input values
                bge_smoothing = self.smoothing_slider.value() / 100
                denoise_strength = self.strength_slider.value() / 100

                # get the current image filename and construct our new output filename
                curfilename = self.siril.get_image_filename()
                directory = os.path.dirname(curfilename)
                outputFileNoSuffix = os.path.join(directory, f"graxpert-temp-output")
                output_file = outputFileNoSuffix + ".fits"
                input_file = os.path.join(directory, f"graxpert-temp-input.fits")

                # grab the current image data from siril and save to a temporary fits file
                data = self.siril.get_image_pixeldata()
                hdu = fits.PrimaryHDU(data)
                hdu.writeto(input_file, overwrite=True)

                # see if the output file already exists - remove it if it does
                if os.path.exists(output_file):
                    os.remove(output_file)

                if self.mode_bge_radio.isChecked():
                    # graxpert BGE options
                    args = [input_file, "-cli", "-cmd", "background-extraction", "-smoothing", str(bge_smoothing), "-output", outputFileNoSuffix]
                    self.siril.log("GraXpert background extraction", s.LogColor.BLUE)
                    self.siril.log("AI model: latest", s.LogColor.BLUE)
                    self.siril.log(f"Smoothing: {bge_smoothing:.2f}", s.LogColor.BLUE)
                else:
                    # graxpert denoise options
                    args = [input_file, "-cli", "-cmd", "denoising", "-strength", str(denoise_strength), "-output", outputFileNoSuffix]
                    self.siril.log("GraXpert denoise", s.LogColor.BLUE)
                    self.siril.log("AI model: latest", s.LogColor.BLUE)
                    self.siril.log(f"Strength: {denoise_strength:.2f}", s.LogColor.BLUE)

                # run graxpert
                subprocess.run([graxpertExecutable] + args, check=True, text=True, capture_output=True)

                # load image back into Siril
                with fits.open(output_file) as hdul:
                    data = hdul[0].data
                    if data.dtype != np.float32:
                        data = np.array(data, dtype=np.float32)
                    if self.mode_bge_radio.isChecked():
                        self.siril.undo_save_state(f"GraXpert BGE: ai=latest, smoothing={bge_smoothing:.2f}")
                    else:
                        self.siril.undo_save_state(f"GraXpert denoise: ai=latest, strength={denoise_strength:.2f}")
                    self.siril.set_image_pixeldata(data)

                self.siril.update_progress("GraXpert running...", 1)
                self.siril.log("GraXpert complete.", s.LogColor.GREEN)
                success = True
                
        except subprocess.CalledProcessError as e:
            self.siril.log(f"Error occurred while running GraXpert: {e}", s.LogColor.SALMON)
        
        except Exception as e:
            self.siril.log(f"Error in script: {str(e)}", s.LogColor.SALMON)

        finally:
            if input_file and os.path.exists(input_file):
                os.remove(input_file)
            if output_file and os.path.exists(output_file):
                os.remove(output_file)
            self._enable_apply.emit()
            self.siril.reset_progress()
            if success:
                self._close_requested.emit()

    def UpdateProgress(self):
        """Simulate progress updates while the background processing is running."""
        if self.apply_btn.isEnabled():
            return
        self.siril.update_progress("GraXpert running...", self.progress)
        if self.progress <= 0.98:
            self.progress = self.progress + 0.01

    def OnThreadComplete(self):
        """Re-enable the apply button after processing is complete."""
        self.progress_timer.stop()
        self.apply_btn.setEnabled(True)

def main():
    try:
        app = QApplication(sys.argv)
        window = SirilGraxpertInterface()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
