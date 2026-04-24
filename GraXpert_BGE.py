#
# Simplfied GraXpert BGE interface for Siril
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
import asyncio
import subprocess
import threading
from astropy.io import fits
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QSlider, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal

graxpertExecutable = "c:/GraXpert2/GraXpert.exe"


class SirilBGEInterface(QWidget):
    _enable_apply = pyqtSignal()

    def __init__(self):
        """Constructor for the GraXpert BGE UI."""
        super().__init__()
        self.setWindowTitle("GraXpert BGE")
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

        self._enable_apply.connect(lambda: self.apply_btn.setEnabled(True))
        self.CreateWidgets()

    def CreateWidgets(self):
        """Create the main dialog widgets."""
        layout = QVBoxLayout()
        self.setLayout(layout)

        options_box = QGroupBox(" Background Extraction ")
        options_layout = QVBoxLayout()
        options_box.setLayout(options_layout)
        options_box.setContentsMargins(8, 23, 8, 13)

        smoothing_row = QHBoxLayout()
        smoothing_label = QLabel("Smoothing:")
        smoothing_label.setFixedWidth(70)
        smoothing_row.addWidget(smoothing_label)

        self.smoothing_slider = QSlider(Qt.Orientation.Horizontal)
        self.smoothing_slider.setMinimum(0)
        self.smoothing_slider.setMaximum(100)
        self.smoothing_slider.setValue(80)
        smoothing_row.addWidget(self.smoothing_slider, 1)

        self.smoothing_value_label = QLabel("0.80")
        self.smoothing_value_label.setFixedWidth(35)
        smoothing_row.addWidget(self.smoothing_value_label)
        self.smoothing_slider.valueChanged.connect(
            lambda value: self.smoothing_value_label.setText(f"{value / 100:.2f}")
        )

        options_layout.addLayout(smoothing_row)
        layout.addWidget(options_box)

        button_row = QHBoxLayout()
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setFixedWidth(80)
        self.apply_btn.clicked.connect(self.OnApply)
        button_row.addWidget(self.apply_btn)
        layout.addLayout(button_row)

    def OnApply(self):
        """Handle apply button click."""
        if not self.siril.is_image_loaded():
            QMessageBox.critical(self, "Error", "No image loaded")
            return
        self.apply_btn.setEnabled(False)
        threading.Thread(target=lambda: asyncio.run(self.ApplyChanges()), daemon=True).start()

    async def ApplyChanges(self):
        """Run GraXpert BGE in a background thread and load the result into Siril."""
        input_file = ""
        output_file = ""
        try:
            # Claim the processing thread
            with self.siril.image_lock():

                # Read user input values
                smoothing = self.smoothing_slider.value() / 100

                # get the current image filename and construct our new output filename
                curfilename = self.siril.get_image_filename()
                basename = os.path.splitext(os.path.basename(curfilename))[0]
                directory = os.path.dirname(curfilename)
                outputFileNoSuffix = os.path.join(directory, f"{basename}-grax-bge-output")
                output_file = outputFileNoSuffix + ".fits"
                input_file = os.path.join(directory, f"{basename}-grax-bge-input.fits")

                # grab the current image data from siril and save to a temporary fits file
                data = self.siril.get_image_pixeldata()
                hdu = fits.PrimaryHDU(data)
                hdu.writeto(input_file, overwrite=True)

                # Call graxpert to run BGE, graxpert will add the .fits suffix
                args = [
                    input_file,
                    "-cli",
                    "-cmd",
                    "background-extraction",
                    "-ai_version",
                    "-smoothing",
                    str(smoothing),
                    "-output",
                    outputFileNoSuffix,
                ]

                # see if the output file already exists - remove it if it does
                if os.path.exists(output_file):
                    os.remove(output_file)

                # run graxpert
                self.siril.log("AI model: latest", s.LogColor.BLUE)
                self.siril.log(f"Smoothing: {smoothing:.2f}", s.LogColor.BLUE)
                self.siril.update_progress("GraXpert BGE running...", -1.0)
                subprocess.run([graxpertExecutable] + args, check=True, text=True, capture_output=True)

                # load image back into Siril
                with fits.open(output_file) as hdul:
                    data = hdul[0].data
                    if data.dtype != np.float32:
                        data = np.array(data, dtype=np.float32)
                    self.siril.undo_save_state(f"GraXpert BGE: ai=latest, smoothing={smoothing:.2f}")
                    self.siril.set_image_pixeldata(data)

                self.siril.update_progress("GraXpert BGE running...", 1)
                self.siril.log("GraXpert BGE completed.", s.LogColor.GREEN)

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


def main():
    try:
        app = QApplication(sys.argv)
        window = SirilBGEInterface()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
