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

from astropy.io import fits
import cv2
import numpy as np
import matplotlib.pyplot as plt
import os

import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedTk
from sirilpy import tksiril


class SirilHistogramInterface:
    """ Simple GUI toolbar like button for generating histograms. Always on top."""
    # constructor
    def __init__(self, root):
        self.root = root
        self.root.title("")
        self.root.resizable(False, False)
        self.root.geometry("200x70")
        self.root.attributes("-topmost", True)
        self.style = s.tksiril.standard_style()

        # Initialize Siril connection
        self.siril = s.SirilInterface()

        try:
            self.siril.connect()
        except s.SirilConnectionError:
            self.siril.error_messagebox("Failed to connect to Siril")
            self.close_dialog()
            return

        try:
            self.siril.cmd("requires", "1.3.6")
        except s.CommandError:
            print("Incompatible Siril version")
            self.siril.disconnect()
            self.close_dialog()
            return

        s.tksiril.match_theme_to_siril(self.root, self.siril)
        self.create_widgets()

    def create_widgets(self):
        """Creates the GUI widgets for the Histogram Viewer interface."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Action Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        close_btn = ttk.Button(
            button_frame,
            text="Histogram",
            command=self.OnView,
            style="TButton"
        )
        close_btn.pack(side=tk.LEFT, padx=5)

        self.linear_chk = ttk.Checkbutton(
            button_frame,
            text="Zoom",
            style="TCheckbutton"
        )
        self.linear_chk.pack(side=tk.LEFT, padx=5)

    def OnView(self):
        """Handles the View button click event."""
        if not self.siril.is_image_loaded():
            print("No image loaded.")
            return

        data = self.siril.get_image_pixeldata()
        linear = False
        if self.linear_chk.instate(['selected']):
            print("Displaying histogram in linear mode.")
            linear = True
        compute_and_plot_color_hist(data, os.path.basename(self.siril.get_image_filename()), dark=True, linear=linear)

def compute_and_plot_color_hist(data, title, bins=256, save_path=None, show=True, dark=False, linear=False, linear_pct=99.1):
    #data = fits.getdata(fits_path)

    # Normalize layout: (3,H,W) -> (H,W,3)
    if data.ndim == 3 and data.shape[0] in (3, 4):
        data = np.transpose(data, (1, 2, 0))
    # If grayscale, replicate channels
    if data.ndim == 2:
        data = np.stack([data] * 3, axis=-1)

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
    # Choose visible colors for fill and outlines depending on theme
    if dark:
        # prefer a dark gray background instead of pure black
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

    # If linear==True, zoom the histogram to the left side where linear FITS data usually resides.
    # We compute the cutoff on the 8-bit image by percentile (default 99.5) and restrict the
    # plotted range to [0, cutoff]. This ignores clipping to the right which is typically
    # uninteresting for linear raw data visualisation.
    if linear:
        # compute cutoff on the 8-bit pixel values, but ignore zero/background pixels
        all_vals = img_rgb[..., :3].ravel()
        nonzero = all_vals[all_vals > 0]
        if nonzero.size > 0:
            cutoff = int(np.percentile(nonzero, linear_pct))
        else:
            cutoff = int(np.percentile(all_vals, linear_pct))
        cutoff = max(1, min(255, cutoff))

        nbins = cutoff + 1
        x = np.arange(nbins)
        for i, color in enumerate(fill_colors):
            hist = cv2.calcHist([img_bgr], [i], None, [nbins], [0, nbins]).flatten()
            ax.fill_between(x, hist, color=color, alpha=fill_alpha, step='mid')
            ax.plot(x, hist, color=color, linewidth=0.9, alpha=edge_alpha)
        ax.set_xlim([0, cutoff])
    else:
        x = np.arange(bins)
        for i, color in enumerate(fill_colors):
            hist = cv2.calcHist([img_bgr], [i], None, [bins], [0, 256]).flatten()
            ax.fill_between(x, hist, color=color, alpha=fill_alpha, step='mid')
            ax.plot(x, hist, color=color, linewidth=0.9, alpha=edge_alpha)
        ax.set_xlim([0, bins - 1])

    # Title and labels: ensure visibility in dark mode
    ax.set_title(f'{title}', color=text_color)

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    if show and not save_path:
        plt.show()

def main():
    try:
        root = ThemedTk()
        SirilHistogramInterface(root)
        root.mainloop()
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        return

if __name__ == "__main__":
    main()
