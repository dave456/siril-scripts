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
s.ensure_installed("tifffile")

import os
import sys
import threading
import importlib
import cv2
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QGroupBox, QCheckBox
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
        mask_box.setContentsMargins(8, 20, 10, 10)

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
        mask_layout.addSpacing(10)

        self.invert_checkbox = QCheckBox("Invert mask")
        mask_layout.addWidget(self.invert_checkbox)

        layout.addWidget(mask_box)
        layout.addSpacing(10)

        # Mask button
        button_row = QHBoxLayout()
        button_row.addStretch()

        self.mask_btn = QPushButton("Mask")
        self.mask_btn.clicked.connect(self.OnMask)
        self.mask_btn.setEnabled(False)
        button_row.addWidget(self.mask_btn)
        button_row.addStretch()

        self.help_btn = QPushButton("Help")
        self.help_btn.clicked.connect(self.ShowHelp)
        button_row.addWidget(self.help_btn)
        button_row.addStretch()

        layout.addLayout(button_row)


    def OnSelectMask(self):
        """Open file dialog to select mask file"""
        # prefer tiff because that's what I use for masking
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

    def ShowHelp(self):
        """Show help message box"""
        help_text = (
            "This utility allows you to apply a mask to blend the current image with the previous state from the undo stack.\n\n"
            "1. Load an image in Siril and make some adjustments, e.g. denoise, curves, etc.\n"
            "2. Click 'Select' to choose a mask file (FITS or TIFF format).\n"
            "3. Optionally invert the mask if desired.\n"
            "4. Click 'Mask' to apply the blending operation.\n\n"
            "The result will be a blend of the current and previous images based on the mask, and will be added to the undo stack "
            "for further adjustments if needed.\n\n"
            "Note: Plate solved images may be flipped in Siril, resulting in an incorrect orientation of the mask when exported "
            "as anything other than FITS. If you export as TIFF and edit in another application this orientation information is lost, "
            "so you may need to experiment with flipping it in an external editor if the result looks wrong."
        )
        QMessageBox.information(self, "Help - Image Masking Utility", help_text)

    def OnMask(self):
        """Apply masking operation"""
        if not self.mask_file_path or not os.path.exists(self.mask_file_path):
            QMessageBox.warning(self, "Error", "No mask file selected or file does not exist")
            return

        self.mask_btn.setEnabled(False)
        threading.Thread(target=self.RunMaskThread, daemon=True).start()

    def OnMaskComplete(self, status):
        """Handle mask operation completion in main thread"""
        self.mask_btn.setEnabled(self.mask_file_path != "")

    def OnError(self, error_msg):
        """Handle error in main thread"""
        QMessageBox.critical(self, "Error", error_msg)
        self.mask_btn.setEnabled(self.mask_file_path != "")

    def OnProgressUpdate(self, message: str, progress: float):
        """Handle progress update in main thread"""
        self.siril.update_progress(message, progress)

    def closeEvent(self, event):
        """Method cverrride for our custom cleanup"""
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
                result = self.ApplyMask(current_data, previous_data, mask_data)

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
                mask = self.LoadTiffMask(file_path)
            else:
                # Assume FITS file
                with fits.open(file_path) as hdul:
                    mask = hdul[0].data
                    if mask is None:
                        return None

                    mask = np.array(mask)
                    mask = np.squeeze(mask)
                    # TODO: This is a hack, maybe extract luminance or something??
                    if mask.ndim == 3:
                        mask = mask[0]

                    # Normalize to [0, 1], handling special values first.
                    original_dtype = mask.dtype
                    mask = np.nan_to_num(mask, nan=0.0, posinf=1.0, neginf=0.0)
                    mask = NormalizeMask(mask, original_dtype)

            if mask.ndim != 2:
                raise ValueError(f"Mask must be 2D after loading; got shape {mask.shape}")
            
            return mask
        
        except Exception as e:
            self.siril.log(f"Error loading mask file: {e}", s.LogColor.SALMON)
            return None


    def LoadTiffMask(self, file_path: str) -> np.ndarray:
        """Load TIFF mask with metadata-aware channel and polarity handling."""
        # ugh - so this is really complicated due to the ways that applications can save tiff files.
        # Specifically, photo editing apps (ahem, photoshop) often save masks as RGB or RGBA tiffs, 
        # where the actual mask data is in the alpha channel, and the RGB channels are just a preview. 
        # Other apps may save as grayscale, but with photometric metadata that indicates whether white 
        # or black is the "1" value. We started with imread and we got to here...
        # The problem is, I really like creating my custom masks in other apps, but this may have gotten
        # away from me.
        try:
            tifffile_module = importlib.import_module("tifffile")

            with tifffile_module.TiffFile(file_path) as tif:
                if len(tif.pages) == 0:
                    return None

                # Use the largest page to avoid preview/thumbnail pages.
                best_page = None
                best_area = -1
                for page in tif.pages:
                    try:
                        shape = tuple(int(v) for v in page.shape)
                    except Exception:
                        continue

                    if len(shape) == 0:
                        continue

                    if len(shape) == 2:
                        h, w = shape
                    elif len(shape) == 3:
                        if shape[-1] in (1, 2, 3, 4):
                            h, w = shape[0], shape[1]
                        elif shape[0] in (1, 2, 3, 4):
                            h, w = shape[1], shape[2]
                        else:
                            h, w = shape[0], shape[1]
                    else:
                        h, w = shape[-2], shape[-1]

                    area = int(h) * int(w)
                    if area > best_area:
                        best_area = area
                        best_page = page

                if best_page is None:
                    return None

                mask = np.array(best_page.asarray())
                mask = np.squeeze(mask)
                photometric = str(getattr(best_page, "photometric", "")).upper()

                extrasamples = []
                try:
                    extrasamples = [str(v).lower() for v in best_page.extrasamples]
                except Exception:
                    extrasamples = []

            if mask.ndim == 3:
                channel_axis = None
                if mask.shape[-1] in (1, 2, 3, 4):
                    channel_axis = -1
                elif mask.shape[0] in (1, 2, 3, 4):
                    channel_axis = 0

                if channel_axis is None:
                    raise ValueError(f"Unsupported TIFF mask shape {mask.shape}")

                mask_channels_last = np.moveaxis(mask, channel_axis, -1)
                use_alpha = any("alpha" in name for name in extrasamples) and mask_channels_last.shape[-1] >= 2

                if use_alpha:
                    # Many tools store matte in alpha while RGB channels are for preview.
                    mask = mask_channels_last[:, :, -1]
                    self.siril.log("TIFF mask: using alpha channel", s.LogColor.BLUE)
                elif mask_channels_last.shape[-1] >= 3:
                    # Convert RGB-like TIFF to grayscale luminance - barf, this is overkill!
                    rgb = mask_channels_last[:, :, :3].astype(np.float32)
                    mask = 0.114 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.299 * rgb[:, :, 2]
                else:
                    mask = np.mean(mask_channels_last.astype(np.float32), axis=2)

            if mask.ndim != 2:
                raise ValueError(f"TIFF mask must be 2D after conversion; got shape {mask.shape}")

            original_dtype = mask.dtype
            mask = np.nan_to_num(mask, nan=0.0, posinf=1.0, neginf=0.0)
            mask = NormalizeMask(mask, original_dtype)

            # TIFF photometric WhiteIsZero means white pixels are numerically low.
            if "MINISWHITE" in photometric or photometric.endswith(".0") or photometric == "0":
                mask = 1.0 - mask
                self.siril.log("TIFF mask: detected MINISWHITE, auto-inverted", s.LogColor.BLUE)

            return mask.astype(np.float32)

        except Exception as e:
            self.siril.log(f"TIFF metadata load failed ({e}), falling back to OpenCV", s.LogColor.BLUE)

            # Fallback path for uncommon TIFF variants not decoded by tifffile.
            mask = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
            if mask is None:
                return None

            if mask.ndim == 3:
                if mask.shape[2] == 4:
                    mask = cv2.cvtColor(mask, cv2.COLOR_BGRA2GRAY)
                else:
                    mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)

            original_dtype = mask.dtype
            mask = np.nan_to_num(mask, nan=0.0, posinf=1.0, neginf=0.0)
            mask = NormalizeMask(mask, original_dtype)
            return mask.astype(np.float32)
        

    def ApplyMask(self, current: np.ndarray, previous: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """
        Blend the current and previous images together using the mask.
        
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
            # mask is (H, W), expand to (1, H, W)
            mask_expanded = mask[np.newaxis, :, :]
            if self.invert_checkbox.isChecked():
                mask_expanded = 1.0 - mask_expanded
            result = current * mask_expanded + previous * (1 - mask_expanded)
        else:
            # 2D case
            if self.invert_checkbox.isChecked():
                mask = 1.0 - mask
            result = current * mask + previous * (1 - mask)
        
        return result.astype(np.float32)


def NormalizeMask(mask_array: np.ndarray, original_dtype: np.dtype) -> np.ndarray:
    """Normalize mask values to [0, 1] while preserving bright=1 semantics."""
    # ugh - a lot of gunk in here. We handle multiple tiff bit depths. We basically
    # need to ensure that we get a normalized float32 in [0..1]. We also nuke nan-data.
    # This should never happen, but paranoia and all that.
    mask_array = mask_array.astype(np.float32)
    if original_dtype == np.uint8:
        mask_array = mask_array / 255.0
    elif original_dtype == np.uint16:
        mask_array = mask_array / 65535.0
    else:
        # assumes 32bit flaot
        mask_min = np.nanmin(mask_array)
        mask_max = np.nanmax(mask_array)
        if mask_max > mask_min:
            mask_array = (mask_array - mask_min) / (mask_max - mask_min)
        else:
            mask_array = np.zeros_like(mask_array, dtype=np.float32)

    return np.clip(mask_array, 0.0, 1.0).astype(np.float32)


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
