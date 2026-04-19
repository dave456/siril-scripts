#
# Display color histogram of the currently loaded image in Siril
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2025 lindner234 <AT> gmail
#

import sirilpy as s
s.ensure_installed("astropy")
s.ensure_installed("numpy")
s.ensure_installed("matplotlib")
s.ensure_installed("opencv-python")
s.ensure_installed("PyQt6")

from astropy.io import fits
import cv2
import numpy as np
import matplotlib.pyplot as plt
import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton, QVBoxLayout, QWidget, QFrame


class SirilHistogramInterface(QWidget):
    """Simple always-on-top PyQt6 window for generating histograms."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Histogram")
        self.setFixedSize(128, 60)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self._drag_offset = None

        # Initialize Siril connection
        self.siril = s.SirilInterface()

        try:
            self.siril.connect()
        except s.SirilConnectionError:
            QMessageBox.critical(self, "Histogram", "Failed to connect to Siril")
            raise

        try:
            self.siril.cmd("requires", "1.3.6")
        except s.CommandError:
            QMessageBox.critical(self, "Histogram", "Incompatible Siril version")
            self.siril.disconnect()
            raise

        self.create_widgets()

    def create_widgets(self):
        """Creates the GUI widgets for the Histogram Viewer interface."""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(8, 6, 8, 12)
        main_layout.setSpacing(4)

        # Small dedicated strip to make the compact window easier to drag.
        self.drag_strip = QFrame()
        self.drag_strip.setFixedHeight(8)
        self.drag_strip.setCursor(Qt.CursorShape.SizeAllCursor)
        main_layout.addWidget(self.drag_strip)

        histogram_btn = QPushButton("Hist")
        histogram_btn.setFixedSize(78, 24)
        btn_font = QFont(histogram_btn.font())
        btn_font.setPointSize(9)
        histogram_btn.setFont(btn_font)
        histogram_btn.clicked.connect(self.on_view)
        main_layout.addWidget(histogram_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.setLayout(main_layout)

    def on_view(self):
        """Handles the Histogram button click event and creates the histogram plot."""
        if not self.siril.is_image_loaded():
            QMessageBox.information(self, "Histogram", "No image loaded.")
            return

        data = self.siril.get_image_pixeldata()
        compute_and_plot_color_hist(
            data,
            os.path.basename(self.siril.get_image_filename()),
            dark=self._is_dark_theme(),
        )

    def _is_dark_theme(self):
        """Infer dark mode from the current Qt palette."""
        return self.palette().window().color().lightness() < 128

    def mousePressEvent(self, event):
        """Start moving when press occurs in the drag strip."""
        if event.button() == Qt.MouseButton.LeftButton and self.drag_strip.geometry().contains(event.pos()):
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Move the window while dragging from the drag strip."""
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """End drag operation."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def closeEvent(self, event):
        """Disconnect cleanly when closing the window."""
        try:
            self.siril.disconnect()
        except Exception:
            pass
        super().closeEvent(event)

def compute_and_plot_color_hist(data, title, bins=256, save_path=None, show=True, dark=False, linear=False):
    """Compute and plot the color histogram of the given image data."""

    # tweak for sirils odd channel layout
    if data.ndim == 3 and data.shape[0] in (3, 4):
        data = np.transpose(data, (1, 2, 0))

    # If grayscale, replicate channels
    if data.ndim == 2:
        data = np.stack([data] * 3, axis=-1)

    # sanity check for rgb or grayscale images - we expect 3 channels in the last dimension after the above adjustments
    if data.ndim != 3 or data.shape[2] < 3:
        raise ValueError('Expected a 3-channel color image in FITS (H,W,3) or (3,H,W).')

    chans8 = []
    for c in range(3):
        chan = np.array(data[..., c], dtype=np.float64)
        chan = np.nan_to_num(chan, nan=np.nanmin(chan))
        lo, hi = np.nanmin(chan), np.nanmax(chan)
        if hi == lo:
            chan8 = np.zeros_like(chan, dtype=np.uint8)
        else:
            chan_norm = (chan - lo) / (hi - lo)
            chan8 = (np.clip(chan_norm, 0.0, 1.0) * 255).astype(np.uint8)
        chans8.append(chan8)

    img_rgb = np.stack(chans8, axis=-1)
    img_bgr = img_rgb[..., ::-1]

    # Apply dark mode style if requested
    if dark:
        bg_color = '#2b2b2b'  # dark gray
        plt.style.use('dark_background')
        fill_colors = ('deepskyblue', 'lime', 'salmon')
        edge_alpha = 0.95
        fill_alpha = 0.45
        text_color = 'w'
    else:
        bg_color = None
        fill_colors = ('b', 'g', 'r')
        edge_alpha = 0.9
        fill_alpha = 0.35
        text_color = 'k'

    # Create figure and axes; set facecolor for dark background
    fig, ax = plt.subplots(figsize=(8, 5), facecolor=bg_color)
    if bg_color is not None:
        ax.set_facecolor(bg_color)
        # adjust tick and spine colors for visibility
        ax.tick_params(colors=text_color)
        for spine in ax.spines.values():
            spine.set_color(text_color)

    ax.ticklabel_format(style='plain', axis='y')

    x = np.arange(bins)
    for i, color in enumerate(fill_colors):
        hist = cv2.calcHist([img_bgr], [i], None, [bins], [0, 256]).flatten()
        ax.fill_between(x, hist, color=color, alpha=fill_alpha, step='mid')
        ax.plot(x, hist, color=color, linewidth=0.9, alpha=edge_alpha)
    ax.set_xlim([0, bins - 1])

    # set text and title colors based on dark mode
    ax.set_title(f'{title}', color=text_color)

    # hide x-axis values and ticks - we've normalized to 0-255 bins, so the x-axix values are meaningless
    ax.tick_params(axis='x', which='both', bottom=False, top=False, labelbottom=False)

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    if show and not save_path:
        # Avoid nested Qt event loops when running inside an existing QApplication.
        if QApplication.instance() is not None:
            plt.show(block=False)
        else:
            plt.show()

def main():
    app = QApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QApplication(sys.argv)

    window = None
    try:
        window = SirilHistogramInterface()
        window.show()
        if owns_app:
            app.exec()
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
    finally:
        if window is not None:
            try:
                window.siril.disconnect()
            except Exception:
                pass

if __name__ == "__main__":
    main()
