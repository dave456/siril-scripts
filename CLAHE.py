#
# Contrast Localized Histogram Equalization
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2026 lindner234 <AT> gmail
#

import sirilpy
sirilpy.ensure_installed("ttkthemes")
sirilpy.ensure_installed("astropy")
sirilpy.ensure_installed("numpy")
sirilpy.ensure_installed("sv_ttk")
#sirilpy.ensure_installed("opencv-python")

import sys
import cv2
import asyncio
import subprocess
import threading
import numpy as np

import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedTk
import sv_ttk
from sirilpy import tksiril


class SirilBGEInterface:
    # constructor
    def __init__(self, root):
        self.root = root
        self.root.title(f"Histogram Equalization")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.style = tksiril.standard_style()

        # Initialize Siril connection
        self.siril = sirilpy.SirilInterface()

        try:
            self.siril.connect()
        except sirilpy.SirilConnectionError:
            self.siril.error_messagebox("Failed to connect to Siril!", True)
            self.close_dialog()
            return

        #tksiril.match_theme_to_siril(self.root, self.siril)
        self.CreateWidgets()

    def CreateWidgets(self):
            """Creates the GUI widgets for the CLAHE interface."""
   
            main_frame = ttk.Frame(self.root, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)

            options_frame = ttk.LabelFrame(main_frame, text="CLAHE Parameters", padding=10)
            options_frame.pack(fill=tk.X, padx=5, pady=5)

            # CLAHE parameters — grid layout so all sliders align
            grid_frame = ttk.Frame(options_frame)
            grid_frame.pack(fill=tk.X, pady=5)
            grid_frame.columnconfigure(1, weight=1)

            # Row 0 — Clip Limit
            ttk.Label(grid_frame, text="Clip Limit:", anchor=tk.W).grid(row=0, column=0, sticky=tk.W, pady=4)
            self.cliplimit_var = tk.DoubleVar(value=2.0)
            ttk.Scale(
                grid_frame, from_=0.1, to=2.0, orient=tk.HORIZONTAL,
                variable=self.cliplimit_var, length=200
            ).grid(row=0, column=1, sticky=tk.EW, padx=10)
            self.cliplimit_display = tk.StringVar(value=f"{self.cliplimit_var.get():.2f}")
            ttk.Label(grid_frame, textvariable=self.cliplimit_display, width=5, anchor=tk.E).grid(row=0, column=2, sticky=tk.E)
            self.cliplimit_var.trace_add("write", self.UpdateClipLimit)

            # Row 1 — Tile Size
            ttk.Label(grid_frame, text="Tile Size:", anchor=tk.W).grid(row=1, column=0, sticky=tk.W, pady=4)
            self.tilesize_var = tk.IntVar(value=8)
            ttk.Scale(
                grid_frame, from_=4, to=256, orient=tk.HORIZONTAL,
                variable=self.tilesize_var, length=200
            ).grid(row=1, column=1, sticky=tk.EW, padx=10)
            self.tilesize_display = tk.StringVar(value="8")
            ttk.Label(grid_frame, textvariable=self.tilesize_display, width=5, anchor=tk.E).grid(row=1, column=2, sticky=tk.E)
            self.tilesize_var.trace_add("write", self.UpdateTileSize)

            # Row 2 — Strength
            ttk.Label(grid_frame, text="Strength:", anchor=tk.W).grid(row=2, column=0, sticky=tk.W, pady=4)
            self.strength_var = tk.DoubleVar(value=0.5)
            ttk.Scale(
                grid_frame, from_=0.01, to=1.0, orient=tk.HORIZONTAL,
                variable=self.strength_var, length=200
            ).grid(row=2, column=1, sticky=tk.EW, padx=10)
            self.strength_display = tk.StringVar(value="0.50")
            ttk.Label(grid_frame, textvariable=self.strength_display, width=5, anchor=tk.E).grid(row=2, column=2, sticky=tk.E)
            self.strength_var.trace_add("write", self.UpdateStrength)

            # Row 3 — Mask Level
            ttk.Label(grid_frame, text="Mask Level:", anchor=tk.W).grid(row=3, column=0, sticky=tk.W, pady=4)
            self.masklevel_var = tk.IntVar(value=80)
            ttk.Scale(
                grid_frame, from_=1, to=100, orient=tk.HORIZONTAL,
                variable=self.masklevel_var, length=200
            ).grid(row=3, column=1, sticky=tk.EW, padx=10)
            self.masklevel_display = tk.StringVar(value="80")
            ttk.Label(grid_frame, textvariable=self.masklevel_display, width=5, anchor=tk.E).grid(row=3, column=2, sticky=tk.E)
            self.masklevel_var.trace_add("write", self.UpdateMaskLevel)

            # Apply Button
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)
            self.apply_btn = ttk.Button(
                button_frame,
                text="Apply",
                command=self.OnApply,
                style="TButton"
            )
            self.apply_btn.pack(side=tk.LEFT, padx=5)

    def UpdateClipLimit(self, *args):
            """Update the gradient value in the slider widget to two decimal places."""
            self.cliplimit_display.set(f"{self.cliplimit_var.get():.2f}")

    def UpdateStrength(self, *args):
            """Update the strength display label."""
            self.strength_display.set(f"{self.strength_var.get():.2f}")

    def UpdateMaskLevel(self, *args):
            """Update the mask level display label."""
            self.masklevel_display.set(str(self.masklevel_var.get()))

    def UpdateTileSize(self, *args):
            """Update the tile size display label."""
            self.tilesize_display.set(str(self.tilesize_var.get()))
    
    def OnApply(self):
        """Callback for the Apply button."""
        if not self.siril.is_image_loaded():
            self.siril.error_messagebox("No image loaded!", True)
            return
        self.apply_btn.state(['disabled'])
        self.root.after(0, self.RunApplyChanges)

    def RunApplyChanges(self):
        """Run Apply changes asynchronously."""
        threading.Thread(target=lambda: asyncio.run(self.ApplyChanges()), daemon=True).start()

    async def ApplyChanges(self):
        """
        Apply CLAHE.
        """
        try:
            # Claim the processing thread
            with self.siril.image_lock():
                
                # Read user input values
                smoothing = self.cliplimit_var.get()
                mask_level = self.masklevel_var.get()
                tile_size = self.tilesize_var.get()
                strength = self.strength_var.get()

                # grab the current image data from siril and save to a temporary fits file
                data = self.siril.get_image_pixeldata()

                #img = multiscale_clahe_lhe(inputFile, 0.5)
                img = basic_clahe(data, strength=strength, clip_limit=smoothing, tile_size=tile_size, mask_level=mask_level)
                self.siril.undo_save_state(f"CLAHE")
                self.siril.set_image_pixeldata(img)

                self.siril.log("CLAHE completed.", sirilpy.LogColor.GREEN)
                
        except subprocess.CalledProcessError as e:
            self.siril.log(f"Error occurred while running GraXpert: {e}", sirilpy.LogColor.SALMON)
        
        except Exception as e:
            self.siril.log(f"Error in script: {str(e)}", sirilpy.LogColor.SALMON)

        finally:
            self.siril.reset_progress()
            self.root.after(0, lambda: self.apply_btn.state(['!disabled']))


def basic_clahe(image: np.ndarray, strength: float = 0.5, clip_limit: float = 2.0, tile_size: int = 64, mask_level: int = 100) -> np.ndarray:
    """
    Apply CLAHE to a normalised float32 numpy image.

    Parameters
    ----------
    image       : float32 numpy array in Siril planes-first layout:
                    RGB  -> (3, H, W)
                    Mono -> (1, H, W)  or  (H, W)
    strength    : blend factor in [0.01, 1.0].
                  1.0 = full CLAHE result; 0.01 = very subtle effect.
    clip_limit  : CLAHE clip limit passed to cv2.createCLAHE.
    tile_size   : pixel size of each CLAHE tile (tileGridSize). Smaller values
                  produce more localised contrast enhancement; larger values
                  approach global histogram equalisation.
    mask_level  : luminance mask threshold in [1, 100].
                  100 = no masking (CLAHE applied everywhere).
                  Lower values restrict the effect to progressively brighter
                  pixels, protecting dark background regions.

    Returns
    -------
    float32 numpy array with the same shape as the input.
    """
    strength = float(np.clip(strength, 0.01, 1.0))
    tile_size = max(1, int(tile_size))
    mask_level = int(np.clip(mask_level, 1, 100))
    # Power used to build the luminance mask: 0 = flat (no masking), higher = darker pixels suppressed
    mask_power = (100 - mask_level) / 10.0

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
        lum_mask = 1.0 if mask_power == 0.0 else np.power(squeezed, mask_power)
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

        lum_mask = 1.0 if mask_power == 0.0 else np.power(L_norm, mask_power)
        L_final = L_norm + strength * lum_mask * (enhanced - L_norm)
        L_final = np.clip(L_final, 0.0, 1.0)
        lab[:, :, 0] = (L_final * 255.0).astype(np.float32)

        result_hwc = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        result_hwc = np.clip(result_hwc, 0.0, 1.0).astype(np.float32)

        # back to planes-first (3, H, W)
        return np.transpose(result_hwc, (2, 0, 1))


def main():
    try:
        root = ThemedTk()
        SirilBGEInterface(root)
        sv_ttk.set_theme("dark")
        root.mainloop()
    except Exception as e:
        print(f"Error initializing script: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
