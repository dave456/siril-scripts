#
# Contrast Localized Histogram Equalization
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2026 lindner234 <AT> gmail
#

import sirilpy
sirilpy.ensure_installed("PyQt6")
sirilpy.ensure_installed("numpy")
#sirilpy.ensure_installed("opencv-python")

import sys
import cv2
import asyncio
import subprocess
import threading
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QSlider, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal


class SirilBGEInterface(QWidget):
    _enable_apply = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Histogram Equalization")
        self.setFixedWidth(450)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        # Initialize Siril connection
        self.siril = sirilpy.SirilInterface()

        try:
            self.siril.connect()
        except sirilpy.SirilConnectionError:
            QMessageBox.critical(self, "Error", "Failed to connect to Siril!")
            self.close()
            return

        self._enable_apply.connect(lambda: self.apply_btn.setEnabled(True))
        self.CreateWidgets()

    def CreateWidgets(self):
        """Creates the GUI widgets for the CLAHE interface."""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # CLAHE Parameters group box
        params_box = QGroupBox(" CLAHE Parameters ")
        params_layout = QGridLayout()
        params_layout.setColumnStretch(1, 1)
        params_box.setLayout(params_layout)
        params_box.setContentsMargins(8, 23, 8, 13)

        # Row 0 — Clip Limit (range 0.1–2.0, stored as int 1–20)
        params_layout.addWidget(QLabel("Clip Limit:"), 0, 0)
        self.cliplimit_slider = QSlider(Qt.Orientation.Horizontal)
        self.cliplimit_slider.setMinimum(1)
        self.cliplimit_slider.setMaximum(20)
        self.cliplimit_slider.setValue(20)
        params_layout.addWidget(self.cliplimit_slider, 0, 1)
        self.cliplimit_label = QLabel("2.00")
        self.cliplimit_label.setFixedWidth(40)
        self.cliplimit_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        params_layout.addWidget(self.cliplimit_label, 0, 2)
        self.cliplimit_slider.valueChanged.connect(
            lambda v: self.cliplimit_label.setText(f"{v / 10:.2f}")
        )

        # Row 1 — Tile Size (range 4–256)
        params_layout.addWidget(QLabel("Tile Size:"), 1, 0)
        self.tilesize_slider = QSlider(Qt.Orientation.Horizontal)
        self.tilesize_slider.setMinimum(4)
        self.tilesize_slider.setMaximum(256)
        self.tilesize_slider.setValue(8)
        params_layout.addWidget(self.tilesize_slider, 1, 1)
        self.tilesize_label = QLabel("8")
        self.tilesize_label.setFixedWidth(40)
        self.tilesize_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        params_layout.addWidget(self.tilesize_label, 1, 2)
        self.tilesize_slider.valueChanged.connect(
            lambda v: self.tilesize_label.setText(str(v))
        )

        # Row 2 — Strength (range 0.01–1.0, stored as int 1–100)
        params_layout.addWidget(QLabel("Strength:"), 2, 0)
        self.strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.strength_slider.setMinimum(1)
        self.strength_slider.setMaximum(100)
        self.strength_slider.setValue(50)
        params_layout.addWidget(self.strength_slider, 2, 1)
        self.strength_label = QLabel("0.50")
        self.strength_label.setFixedWidth(40)
        self.strength_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        params_layout.addWidget(self.strength_label, 2, 2)
        self.strength_slider.valueChanged.connect(
            lambda v: self.strength_label.setText(f"{v / 100:.2f}")
        )

        # Row 3 — Shadow Mask (range 1–100): protects dark/shadow regions
        params_layout.addWidget(QLabel("Shadow Mask:"), 3, 0)
        self.masklevel_slider = QSlider(Qt.Orientation.Horizontal)
        self.masklevel_slider.setMinimum(1)
        self.masklevel_slider.setMaximum(100)
        self.masklevel_slider.setValue(80)
        params_layout.addWidget(self.masklevel_slider, 3, 1)
        self.masklevel_label = QLabel("80")
        self.masklevel_label.setFixedWidth(40)
        self.masklevel_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        params_layout.addWidget(self.masklevel_label, 3, 2)
        self.masklevel_slider.valueChanged.connect(
            lambda v: self.masklevel_label.setText(str(v))
        )

        # Row 4 — Highlight Mask (range 1–100): protects bright/highlight regions
        params_layout.addWidget(QLabel("Highlight Mask:"), 4, 0)
        self.highlightlevel_slider = QSlider(Qt.Orientation.Horizontal)
        self.highlightlevel_slider.setMinimum(1)
        self.highlightlevel_slider.setMaximum(100)
        self.highlightlevel_slider.setValue(100)
        params_layout.addWidget(self.highlightlevel_slider, 4, 1)
        self.highlightlevel_label = QLabel("100")
        self.highlightlevel_label.setFixedWidth(40)
        self.highlightlevel_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        params_layout.addWidget(self.highlightlevel_label, 4, 2)
        self.highlightlevel_slider.valueChanged.connect(
            lambda v: self.highlightlevel_label.setText(str(v))
        )

        layout.addWidget(params_box)

        # Apply button
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

    async def ApplyChanges(self):
        """Apply CLAHE."""
        try:
            # Claim the processing thread
            with self.siril.image_lock():

                # Read user input values
                smoothing = self.cliplimit_slider.value() / 10.0
                mask_level = self.masklevel_slider.value()
                highlight_level = self.highlightlevel_slider.value()
                tile_size = self.tilesize_slider.value()
                strength = self.strength_slider.value() / 100.0

                # grab the current image data from siril
                data = self.siril.get_image_pixeldata()

                img = basic_clahe(data, strength=strength, clip_limit=smoothing, tile_size=tile_size, mask_level=mask_level, highlight_level=highlight_level)
                self.siril.undo_save_state("CLAHE")
                self.siril.set_image_pixeldata(img)

                self.siril.log("CLAHE completed.", sirilpy.LogColor.GREEN)

        except subprocess.CalledProcessError as e:
            self.siril.log(f"Error occurred while running GraXpert: {e}", sirilpy.LogColor.SALMON)

        except Exception as e:
            self.siril.log(f"Error in script: {str(e)}", sirilpy.LogColor.SALMON)

        finally:
            self.siril.reset_progress()
            self._enable_apply.emit()


def basic_clahe(image: np.ndarray, strength: float = 0.5, clip_limit: float = 2.0, tile_size: int = 64, mask_level: int = 100, highlight_level: int = 100) -> np.ndarray:
    """
    Apply CLAHE to a normalised float32 numpy image.

    Parameters
    ----------
    image           : float32 numpy array in Siril planes-first layout:
                        RGB  -> (3, H, W)
                        Mono -> (1, H, W)  or  (H, W)
    strength        : blend factor in [0.01, 1.0].
                      1.0 = full CLAHE result; 0.01 = very subtle effect.
    clip_limit      : CLAHE clip limit passed to cv2.createCLAHE.
    tile_size       : pixel size of each CLAHE tile (tileGridSize). Smaller values
                      produce more localised contrast enhancement; larger values
                      approach global histogram equalisation.
    mask_level      : shadow mask threshold in [1, 100].
                      100 = no masking; lower values increasingly protect dark regions.
    highlight_level : highlight mask threshold in [1, 100].
                      100 = no masking; lower values increasingly protect bright regions.

    Returns
    -------
    float32 numpy array with the same shape as the input.
    """
    strength = float(np.clip(strength, 0.01, 1.0))
    tile_size = max(1, int(tile_size))
    mask_level = int(np.clip(mask_level, 1, 100))
    highlight_level = int(np.clip(highlight_level, 1, 100))
    # Shadow mask power: 0 = no masking, 3.0 = strong suppression of dark pixels.
    mask_power = ((100 - mask_level) / 100.0) * 3.0
    # Highlight mask: threshold-based cutoff.
    # highlight_level=100 → no masking; lower values protect pixels above that luminosity.
    # A soft transition band of ±10% of the threshold is used to avoid hard edges.
    highlight_threshold = highlight_level / 100.0
    highlight_half_width = max(0.01, highlight_threshold * 0.1)

    # ---- normalize to [0, 1] float32 ----
    img = image.astype(np.float32)
    img_min, img_max = img.min(), img.max()
    if img_max > img_min:
        img = (img - img_min) / (img_max - img_min)

    clahe = cv2.createCLAHE(clipLimit=float(clip_limit), tileGridSize=(tile_size, tile_size))

    mono = img.ndim == 2 or (img.ndim == 3 and img.shape[0] == 1)

    if mono:
        # ---- mono path ----
        squeezed = img.squeeze()                        # (H, W)
        L16 = (squeezed * 65535).astype(np.uint16)
        enhanced = clahe.apply(L16).astype(np.float32) / 65535
        shadow_mask = 1.0 if mask_power == 0.0 else np.power(squeezed, mask_power)
        if highlight_level >= 100:
            highlight_mask = 1.0
        else:
            highlight_mask = np.clip((highlight_threshold - squeezed) / highlight_half_width + 0.5, 0.0, 1.0)
        lum_mask = shadow_mask * highlight_mask
        result = squeezed + strength * lum_mask * (enhanced - squeezed)
        result = np.clip(result, 0.0, 1.0)
        # restore original shape
        return result.reshape(img.shape)

    else:
        # ---- RGB path ----
        # planes-first (3, H, W) -> interleaved (H, W, 3)
        hwc = np.transpose(img, (1, 2, 0))

        # convert to LAB (cv2 expects uint8/uint16 or float32 in [0,1] for RGB2LAB)
        lab = cv2.cvtColor(hwc, cv2.COLOR_RGB2LAB)      # L in [0, 255] for float32 input
        L = lab[:, :, 0].astype(np.float32)             # [0, 255]

        L_norm = L / 255.0
        L16 = (L_norm * 65535).astype(np.uint16)
        enhanced = clahe.apply(L16).astype(np.float32) / 65535  # [0, 1]

        shadow_mask = 1.0 if mask_power == 0.0 else np.power(L_norm, mask_power)
        if highlight_level >= 100:
            highlight_mask = 1.0
        else:
            highlight_mask = np.clip((highlight_threshold - L_norm) / highlight_half_width + 0.5, 0.0, 1.0)
        lum_mask = shadow_mask * highlight_mask
        L_final = L_norm + strength * lum_mask * (enhanced - L_norm)
        L_final = np.clip(L_final, 0.0, 1.0)
        lab[:, :, 0] = (L_final * 255.0).astype(np.float32)

        result_hwc = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        result_hwc = np.clip(result_hwc, 0.0, 1.0).astype(np.float32)

        # back to planes-first (3, H, W)
        return np.transpose(result_hwc, (2, 0, 1))


def main():
    try:
        app = QApplication(sys.argv)
        window = SirilBGEInterface()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error initializing script: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
