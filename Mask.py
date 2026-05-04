#
# Image masking utility for Siril
#
# This script uses the undo stack to blend the last two states with a mask allowing users to 
# apply masks to their images. The mask can be a FITS or TIFF file, and should be a single-channel 
# grayscale image where pixel values where white (1.0) indicate areas to take from the current image, 
# and black (0.0) indicate areas to take from the previous image, with values in between blending the two.
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
import threading
import cv2
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from astropy.io import fits


class SignalBridge(QObject):
    """Signal bridge for background thread callbacks"""
    mask_complete = pyqtSignal(str)  # (status)
    error_occurred = pyqtSignal(str)  # (error_message)
    progress_update = pyqtSignal(str, float)  # (message, progress)


class MaskWindow(QWidget):
    def __init__(self):
        """Constructor for the Mask utility UI"""
        super().__init__()
        self.setWindowTitle("Image Masking Utility")
        self.setFixedWidth(550)
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
        self.signals.mask_complete.connect(self.OnMaskComplete)
        self.signals.error_occurred.connect(self.OnError)
        self.signals.progress_update.connect(self.OnProgressUpdate)

        self.mask_file_path = ""
        self.mask_btn = None
        self.unmask_btn = None
        self.mask_line = None

        self.CreateWidgets()


    def CreateWidgets(self):
        """Create the GUI widgets"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Create group box for mask
        mask_box = QGroupBox(" Mask ")
        mask_layout = QVBoxLayout()
        mask_box.setLayout(mask_layout)
        mask_box.setContentsMargins(10, 25, 10, 15)

        # Mask file selection
        file_row = QHBoxLayout()
        file_row.setSpacing(6)

        select_btn = QPushButton("Select")
        select_btn.clicked.connect(self.OnSelectMask)
        file_row.addWidget(select_btn)

        self.mask_line = QLineEdit()
        self.mask_line.setReadOnly(True)
        file_row.addWidget(self.mask_line, 1)

        mask_layout.addLayout(file_row)
        layout.addWidget(mask_box)
        layout.addSpacing(10)

        # Mask and Unmask buttons
        button_row = QHBoxLayout()
        button_row.addStretch()

        self.mask_btn = QPushButton("Mask")
        self.mask_btn.clicked.connect(self.OnMask)
        self.mask_btn.setEnabled(False)
        button_row.addWidget(self.mask_btn)

        button_row.addSpacing(20)

        self.unmask_btn = QPushButton("Unmask")
        self.unmask_btn.clicked.connect(self.OnUnmask)
        self.unmask_btn.setEnabled(False)
        button_row.addWidget(self.unmask_btn)

        button_row.addStretch()
        layout.addLayout(button_row)


    def OnSelectMask(self):
        """Open file dialog to select mask file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select mask file", 
            "", 
            "TIFF files (*.tiff *.tif);;FITS files (*.fits);;All files (*.*)"
        )
        if file_path:
            self.mask_line.setText(os.path.basename(file_path))
            self.mask_file_path = file_path
            self.mask_btn.setEnabled(True)


    def OnMask(self):
        """Apply masking operation"""
        if not self.mask_file_path or not os.path.exists(self.mask_file_path):
            QMessageBox.warning(self, "Error", "No mask file selected or file does not exist")
            return

        self.mask_btn.setEnabled(False)
        self.unmask_btn.setEnabled(False)
        threading.Thread(target=self.RunMaskThread, daemon=True).start()


    def OnUnmask(self):
        """Unmask operation - not yet implemented"""
        QMessageBox.information(self, "Not Implemented", "Unmask operation is not yet implemented")


    def OnMaskComplete(self, status):
        """Handle mask operation completion in main thread"""
        self.mask_btn.setEnabled(self.mask_file_path != "")
        self.unmask_btn.setEnabled(False)


    def OnError(self, error_msg):
        """Handle error in main thread"""
        QMessageBox.critical(self, "Error", error_msg)
        self.mask_btn.setEnabled(self.mask_file_path != "")
        self.unmask_btn.setEnabled(False)


    def OnProgressUpdate(self, message: str, progress: float):
        """Handle progress update in main thread"""
        self.siril.update_progress(message, progress)


    def closeEvent(self, event):
        """Clean up on close"""
        self.siril.disconnect()
        super().closeEvent(event)


    def RunMaskThread(self):
        """Background thread to apply mask"""
        try:
            # Load mask file
            mask_data = self.LoadMask(self.mask_file_path)
            if mask_data is None:
                raise ValueError("Failed to load mask file")
            
            # We do the undo first, and outside the lock, because siril won't update the pixel data on an undo
            # with lock held. So we undo, lock, grab pixel data, redo and grab pixel data again, then apply the 
            # mask blend and set the result. *phew*
            self.siril.undo()

            with self.siril.image_lock():
                # Get previous image data
                previous_data = self.siril.get_image_pixeldata()

                # Call redo to get the current image data
                self.siril.redo()

                # Get the current image data
                current_data = self.siril.get_image_pixeldata()

                # sanity check to see if we really got two different pixel maps
                if np.array_equal(current_data, previous_data):
                    self.siril.log("Warning: Undo did not change image data - cannot apply mask", s.LogColor.SALMON)
                    self.signals.error_occurred.emit("Undo did not change image data - cannot apply mask")
                    return

                # Apply mask blend operation
                # output = current * mask + previous * (1 - mask)
                result = ApplyMask(current_data, previous_data, mask_data)

                self.signals.progress_update.emit("Setting result image...", 0.8)

                # Save the state for undo/redo
                self.siril.undo_save_state("Mask blend")

                # Set the result
                self.siril.set_image_pixeldata(result)

            self.siril.log("Mask applied successfully", s.LogColor.GREEN)
            self.signals.mask_complete.emit("success")

        except Exception as e:
            self.siril.log(f"Error applying mask: {e}", s.LogColor.SALMON)
            self.signals.error_occurred.emit(f"Error applying mask: {e}")

        finally:
            self.siril.reset_progress()


    def LoadMask(self, file_path: str) -> np.ndarray:
        """
        Load mask from FITS or TIFF file.
        
        Returns
        -------
        float32 numpy array normalized to [0, 1], shape (H, W)
        """
        try:
            if file_path.lower().endswith(('.tif', '.tiff')):
                mask = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
                if mask is None:
                    return None
                mask = np.array(mask, dtype=np.float32)
                # Normalize based on the original bit depth
                if mask.dtype == np.uint8:
                    mask = mask / 255.0
                elif mask.dtype == np.uint16:
                    mask = mask / 65535.0
                else:
                    # For other types, normalize to [0, 1] range
                    mask_min = mask.min()
                    mask_max = mask.max()
                    if mask_max > mask_min:
                        mask = (mask - mask_min) / (mask_max - mask_min)
            else:
                # Assume FITS file
                with fits.open(file_path) as hdul:
                    mask = hdul[0].data
                    if mask is None:
                        return None
                    mask = np.array(mask, dtype=np.float32)
                    # Normalize to [0, 1], handling special values
                    mask = np.nan_to_num(mask, nan=0.0, posinf=1.0, neginf=0.0)
                    mask_min = np.nanmin(mask)
                    mask_max = np.nanmax(mask)
                    if mask_max > mask_min:
                        mask = (mask - mask_min) / (mask_max - mask_min)
            
            return mask
        
        except Exception as e:
            self.siril.log(f"Error loading mask file: {e}", s.LogColor.SALMON)
            return None

def ApplyMask(current: np.ndarray, previous: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Apply mask operation: output = current * mask + previous * (1 - mask)
    
    Parameters
    ----------
    current : float32 numpy array
        Current image data in Siril planes-first layout: (channels, height, width) or (height, width)
    previous : float32 numpy array
        Previous image data (from undo) in same layout
    mask : float32 numpy array
        Mask data in range [0, 1], shape (height, width)
    
    Returns
    -------
    float32 numpy array
        Blended result in same layout as input
    """
    current = current.astype(np.float32)
    previous = previous.astype(np.float32)
    mask = mask.astype(np.float32)
    
    # Handle both planes-first (C, H, W) and 2D (H, W) formats
    if current.ndim == 3:
        # Planes-first: expand mask to match channels dimension
        # mask is (H, W), expand to (1, H, W) then broadcast
        mask_expanded = mask[np.newaxis, :, :]
        result = current * mask_expanded + previous * (1 - mask_expanded)
    else:
        # 2D case
        result = current * mask + previous * (1 - mask)
    
    return result.astype(np.float32)


def main():
    try:
        app = QApplication(sys.argv)
        window = MaskWindow()
        window.show()
        sys.exit(app.exec())

    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
