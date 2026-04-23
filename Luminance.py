#
# Luminance Channel Extractor and Recombiner
#
# This script allows the user to extract the luminance channel from the currently loaded image in Siril
# and save it as a separate FITS file. The user can then modify the luminance file (denoise, sharpen, etc.) 
# and then recombine it with the original image.
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2026 lindner234 <AT> gmail
#

import sirilpy as s
s.ensure_installed("PyQt6")
s.ensure_installed("astropy")
s.ensure_installed("numpy")
s.ensure_installed("opencv-python")

import os
import sys
import cv2
import threading
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QMessageBox, QGroupBox, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from astropy.io import fits


class SignalBridge(QObject):
    """Signal bridge for background thread callbacks"""
    extraction_complete = pyqtSignal(str, str)  # (status, filename)
    recombine_complete = pyqtSignal(str)  # (status)
    error_occurred = pyqtSignal(str)  # (error_message)
    progress_update = pyqtSignal(str, float)  # (message, progress)


class LuminanceWindow(QWidget):
    def __init__(self):
        """Constructor for the Luminance extractor/recombiner UI"""
        super().__init__()
        self.setWindowTitle("Luminance Channel Extractor")
        self.setFixedWidth(500)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        # Siril connection
        self.siril = s.SirilInterface()
        try:
            self.siril.connect()
        except s.SirilConnectionError:
            QMessageBox.critical(self, "Error", "Failed to connect to Siril")
            self.close()
            return

        try:
            self.siril.cmd("requires", "1.3.6")
        except s.CommandError:
            QMessageBox.critical(self, "Error", "Siril version requirement not met")
            self.siril.disconnect()
            self.close()
            return

        if not self.siril.is_image_loaded():
            QMessageBox.critical(self, "Error", "No image loaded")
            self.siril.disconnect()
            self.close()
            return

        # Signal bridge for thread callbacks
        self.signals = SignalBridge()
        self.signals.extraction_complete.connect(self.on_extraction_complete)
        self.signals.recombine_complete.connect(self.on_recombine_complete)
        self.signals.error_occurred.connect(self.on_error)

        self.luminance_file_path = ""
        self.current_image_filename = ""
        self.extract_btn = None
        self.recombine_btn = None
        self.luminance_line = None

        self.CreateWidgets()
        self.DetectLuminanceFile()

    def CreateWidgets(self):
        """Create the GUI widgets"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Create group box for luminance controls
        lum_box = QGroupBox(" Luminance ")
        lum_layout = QVBoxLayout()
        lum_box.setLayout(lum_layout)
        lum_box.setContentsMargins(10, 25, 10, 15)

        # Row 1: File selection
        file_row = QHBoxLayout()
        file_row.setSpacing(6)

        select_btn = QPushButton("Select")
        select_btn.clicked.connect(self.OnSelectLuminance)
        file_row.addWidget(select_btn)

        self.luminance_line = QLineEdit()
        self.luminance_line.setReadOnly(True)
        file_row.addWidget(self.luminance_line, 1)
 
        lum_layout.addLayout(file_row)
        lum_layout.addSpacing(10)

        # Row 2: Extract and Recombine buttons (centered)
        button_row = QHBoxLayout()
        button_row.addStretch()
        
        self.extract_btn = QPushButton("Extract")
        self.extract_btn.clicked.connect(self.OnExtract)
        button_row.addWidget(self.extract_btn)

        button_row.addSpacing(20)

        self.recombine_btn = QPushButton("Recombine")
        self.recombine_btn.clicked.connect(self.OnRecombine)
        button_row.addWidget(self.recombine_btn)
        
        button_row.addStretch()
        lum_layout.addLayout(button_row)

        layout.addWidget(lum_box)

    def DetectLuminanceFile(self):
        """Check if a _luma file exists for the current image"""
        try:
            curfilename = self.siril.get_image_filename()
            self.current_image_filename = curfilename
            basename = os.path.basename(curfilename)
            directory = os.path.dirname(curfilename)
            name_without_ext = os.path.splitext(basename)[0]

            luma_basename = f"{name_without_ext}_luma.fits"
            luma_path = os.path.join(directory, luma_basename)

            if os.path.exists(luma_path):
                self.luminance_file_path = luma_path
                self.luminance_line.setText(luma_basename)
                self.recombine_btn.setEnabled(True)
            else:
                self.recombine_btn.setEnabled(False)
        except Exception as e:
            self.siril.log(f"Error detecting luminance file: {e}", s.LogColor.SALMON)
            self.recombine_btn.setEnabled(False)

    def OnSelectLuminance(self):
        """Open file dialog to select luminance file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select luminance file", "", "FITS files (*.fits);;All files (*.*)"
        )
        if file_path:
            self.luminance_line.setText(os.path.basename(file_path))
            self.luminance_file_path = file_path
            self.recombine_btn.setEnabled(True)

    def OnExtract(self):
        """Extract luminance channel from current image"""
        self.extract_btn.setEnabled(False)
        self.recombine_btn.setEnabled(False)
        threading.Thread(target=self._run_extract, daemon=True).start()

    def _run_extract(self):
        """Background thread to extract luminance"""
        try:
            self.siril.update_progress("Extracting luminance channel...", 0)

            with self.siril.image_lock():
                img_data = self.siril.get_image_pixeldata()

            # Extract luminance from the image
            luminance = extract_luminance(img_data)

            # Generate output filename
            basename = os.path.basename(self.current_image_filename)
            directory = os.path.dirname(self.current_image_filename)
            name_without_ext = os.path.splitext(basename)[0]
            output_filename = os.path.join(directory, f"{name_without_ext}_luma.fits")

            # Save to FITS file
            self.siril.update_progress("Saving luminance to FITS...", 0.8)

            # Create HDU with luminance data
            hdu = fits.PrimaryHDU(luminance)
            hdu.writeto(output_filename, overwrite=True)

            self.luminance_file_path = output_filename
            self.siril.log(f"Luminance extracted to {os.path.basename(output_filename)}", s.LogColor.GREEN)
            self.signals.extraction_complete.emit("success", os.path.basename(output_filename))

        except Exception as e:
            self.siril.log(f"Error extracting luminance: {e}", s.LogColor.SALMON)
            self.signals.error_occurred.emit(f"Error extracting luminance: {e}")
        finally:
            self.siril.reset_progress()
    
    def on_extraction_complete(self, status, filename):
        """Handle extraction completion in main thread"""
        self.luminance_line.setText(filename)
        self.recombine_btn.setEnabled(True)
        self.extract_btn.setEnabled(True)

    def OnRecombine(self):
        """Recombine current image with extracted luminance"""
        if not self.luminance_file_path or not os.path.exists(self.luminance_file_path):
            QMessageBox.warning(self, "Error", "No luminance file selected or file does not exist")
            return

        self.extract_btn.setEnabled(False)
        self.recombine_btn.setEnabled(False)
        threading.Thread(target=self._run_recombine, daemon=True).start()

    def _run_recombine(self):
        """Background thread to recombine luminance"""
        try:
            self.siril.update_progress("Loading luminance channel...", 0)

            # Load luminance file as float32 luminance data
            with fits.open(self.luminance_file_path) as hdul:
                lum_data = hdul[0].data
                lum_data = np.array(lum_data, dtype=np.float32)

            self.siril.update_progress("Recombining with current image...", 0.3)

            with self.siril.image_lock():
                img_data = self.siril.get_image_pixeldata()
                self.siril.undo_save_state("Recombine luminance")

                # Recombine luminance with current image
                result = recombine_luminance(img_data, lum_data)

                self.siril.set_image_pixeldata(result)

            self.siril.log("Luminance recombined successfully", s.LogColor.GREEN)
            self.signals.recombine_complete.emit("success")

        except Exception as e:
            self.siril.log(f"Error recombining luminance: {e}", s.LogColor.SALMON)
            self.signals.error_occurred.emit(f"Error recombining luminance: {e}")
        finally:
            self.siril.reset_progress()

    def on_recombine_complete(self, status):
        """Handle recombine completion in main thread"""
        self.extract_btn.setEnabled(True)
        self.recombine_btn.setEnabled(self.luminance_file_path != "")

    def on_error(self, error_msg):
        """Handle error in main thread"""
        QMessageBox.critical(self, "Error", error_msg)
        self.extract_btn.setEnabled(True)
        self.recombine_btn.setEnabled(self.luminance_file_path != "")

    def closeEvent(self, event):
        """Clean up on close"""
        self.siril.disconnect()
        super().closeEvent(event)


def extract_luminance(image: np.ndarray) -> np.ndarray:
    """
    Extract the luminance (L) channel from an image.

    Parameters
    ----------
    image : float32 numpy array in Siril planes-first layout:
        RGB  -> (3, H, W)
        Mono -> (1, H, W) or (H, W)

    Returns
    -------
    float32 numpy array with the luminance channel (H, W) in range [0, 1]
    """
    img = image.astype(np.float32)

    mono = img.ndim == 2 or (img.ndim == 3 and img.shape[0] == 1)

    if mono:
        squeezed = img.squeeze()
        img_min, img_max = squeezed.min(), squeezed.max()
        if img_max > img_min:
            squeezed = (squeezed - img_min) / (img_max - img_min)
        return squeezed
    else:
        img_min, img_max = img.min(), img.max()
        if img_max > img_min:
            img = (img - img_min) / (img_max - img_min)

        # planes-first (3, H, W) -> interleaved (H, W, 3)
        hwc = np.transpose(img, (1, 2, 0))

        # Convert RGB to LAB (L in [0, 255] for float32 input in [0, 1])
        lab = cv2.cvtColor(hwc, cv2.COLOR_RGB2LAB)
        L = lab[:, :, 0].astype(np.float32)  # [0, 255]

        return L / 255.0  # normalize to [0, 1] for storage


def recombine_luminance(image: np.ndarray, luminance: np.ndarray) -> np.ndarray:
    """
    Recombine an image with a new luminance channel.

    Parameters
    ----------
    image : float32 numpy array in Siril planes-first layout:
        RGB  -> (3, H, W)
        Mono -> (1, H, W) or (H, W)
    luminance : float32 numpy array with shape (H, W) in range [0, 1]

    Returns
    -------
    float32 numpy array with the same shape as the input image
    """
    img = image.astype(np.float32)
    
    mono = img.ndim == 2 or (img.ndim == 3 and img.shape[0] == 1)

    if mono:
        # For monochrome, luminance is the image.
        return np.array(luminance, dtype=np.float32).reshape(img.shape)
    else:
        # For RGB, convert to LAB, replace L channel, and convert back
        # Normalize image to [0, 1] first
        img_min, img_max = img.min(), img.max()
        if img_max > img_min:
            img = (img - img_min) / (img_max - img_min)
        
        # planes-first (3, H, W) -> interleaved (H, W, 3)
        hwc = np.transpose(img, (1, 2, 0))

        # Convert RGB to LAB
        lab = cv2.cvtColor(hwc, cv2.COLOR_RGB2LAB)

        lum_norm = np.array(luminance, dtype=np.float32)
        lum_norm = np.clip(lum_norm, 0.0, 1.0)
        lum_L = lum_norm * 255.0

        # Replace L channel
        lab[:, :, 0] = lum_L

        # Convert back to RGB
        result_hwc = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        result_hwc = np.clip(result_hwc, 0.0, 1.0).astype(np.float32)

        # Back to planes-first (3, H, W) and scale back to original range
        result = np.transpose(result_hwc, (2, 0, 1))
        if img_max > img_min:
            result = result * (img_max - img_min) + img_min
        
        return result


def main():
    try:
        app = QApplication(sys.argv)
        window = LuminanceWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
