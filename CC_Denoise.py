#
# Simplfied Cosmic Clarity Denoise interface for Siril
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2026 lindner234 <AT> gmail
#

import sirilpy as s
s.ensure_installed("ttkthemes")
s.ensure_installed("astropy")
s.ensure_installed("numpy")
s.ensure_installed("sv_ttk")

import os
import re
import sys
import asyncio
import subprocess
import threading

import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedTk
import sv_ttk
from sirilpy import tksiril
from astropy.io import fits
import numpy as np

denoiseExecutable = "C:/Program Files/SetiAstroSuitePro/setiastrosuitepro.exe"

class SirilDenoiseInterface:
    # constructor
    def __init__(self, root):
        self.root = root
        self.root.title(f"Cosmic Clarity Denoise")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.style = tksiril.standard_style()

        # Initialize Siril connection
        self.siril = s.SirilInterface()

        try:
            self.siril.connect()
        except s.SirilConnectionError:
            self.siril.error_messagebox("Failed to connect to Siril!", True)
            self.close_dialog()
            return

        self.CreateWidgets()

    def CreateWidgets(self):
            """Create the GUI widgets for the Cosmic Clarity Denoise interface."""
            # Main frame
            main_frame = ttk.Frame(self.root, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Denoise Mode Group Box
            mode_frame = ttk.LabelFrame(main_frame, text="Denoise Mode", padding=10)
            mode_frame.pack(fill=tk.X, padx=5, pady=5)

            # Denoising modes
            self.denoise_mode_var = tk.StringVar(value="full")
            denoise_modes = ["luminance", "full"]
            for mode in denoise_modes:
                ttk.Radiobutton(
                    mode_frame,
                    text=mode.capitalize(),
                    variable=self.denoise_mode_var,
                    value=mode
                ).pack(anchor=tk.W, pady=2)

            # Strength frame
            strength_frame = ttk.LabelFrame(main_frame, text="Denoise Strength", padding=10)
            strength_frame.pack(fill=tk.X, padx=5, pady=5)

            # Luminance strength slider
            luminance_str_frame = ttk.Frame(strength_frame)
            luminance_str_frame.pack(fill=tk.X, pady=5)
            ttk.Label(luminance_str_frame, text=" Luminance:", width=12).pack(side=tk.LEFT)
            self.lum_strength_var = tk.DoubleVar(value=0.75)
            denoise_strength_scale = ttk.Scale(
                luminance_str_frame,
                from_=0.0,
                to=1.0,
                orient=tk.HORIZONTAL,
                variable=self.lum_strength_var,
                length=200
            )
            denoise_strength_scale.pack(side=tk.LEFT, padx=10, expand=True)
            self.lum_strength_var.trace_add("write", self.UpdateLuminanceStr)

            # Luminance strength display
            self.lum_strength_display = tk.StringVar(value=f"{self.lum_strength_var.get():.2f}")
            ttk.Label(
                luminance_str_frame,
                textvariable=self.lum_strength_display,
                width=5
            ).pack(side=tk.LEFT)

            # Color strength slider
            color_str_frame = ttk.Frame(strength_frame)
            color_str_frame.pack(fill=tk.X, pady=5)
            ttk.Label(color_str_frame, text=" Color:", width=12).pack(side=tk.LEFT)
            self.color_strength_var = tk.DoubleVar(value=0.55)
            color_strength_scale = ttk.Scale(
                color_str_frame,
                from_=0.0,
                to=1.0,
                orient=tk.HORIZONTAL,
                variable=self.color_strength_var,
                length=200
            )
            color_strength_scale.pack(side=tk.LEFT, padx=10, expand=True)
            self.color_strength_var.trace_add("write", self.UpdateColorStr)

            # Color strength display
            self.color_strength_display = tk.StringVar(value=f"{self.color_strength_var.get():.2f}")
            ttk.Label(
                color_str_frame,
                textvariable=self.color_strength_display,
                width=5
            ).pack(side=tk.LEFT)
            
            # Options Mode Group Box
            options_frame = ttk.LabelFrame(main_frame, text="Options", padding=10)
            options_frame.pack(fill=tk.X, padx=5, pady=5)

            # GPU Checkbox
            self.use_gpu_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(
                options_frame,
                text="Use GPU",
                variable=self.use_gpu_var
            ).pack(anchor=tk.W, pady=2)

            # Denoise RGB channels individually
            self.separate_channels = tk.BooleanVar(value=False)
            ttk.Checkbutton(
                options_frame,
                text="Separate RGB channels",
                variable=self.separate_channels
            ).pack(anchor=tk.W, pady=2)
        
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

    def UpdateLuminanceStr(self, *args):
        """Update luminance strength display value to two decimal places."""
        self.lum_strength_display.set(f"{self.lum_strength_var.get():.2f}")

    def UpdateColorStr(self, *args):
        """Update color denoise strength display value to two decimal places."""
        self.color_strength_display.set(f"{self.color_strength_var.get():.2f}")

    def OnApply(self):
        """Callback for the Apply button."""
        if not self.siril.is_image_loaded():
            self.siril.error_messagebox("No image loaded!", True)
            return
        self.apply_btn.state(['disabled'])
        self.root.after(0, self.RunApplyChanges)

    def RunApplyChanges(self):
        """Run Apply changes in a separate thread to avoid blocking the GUI."""
        threading.Thread(target=lambda: asyncio.run(self.ApplyChanges()), daemon=True).start()

    async def RunCosmicClarity(self, inputFile, outputFile):
        """Run Cosmic Clarity denoise."""
        try:
            command = [
                denoiseExecutable,
                "cc",
                "denoise",
                f"-i={inputFile}",
                f"-o={outputFile}",
                f"--denoise-mode={self.denoise_mode_var.get()}",
                f"--denoise-luma={self.lum_strength_display.get()}",
                f"--denoise-color={self.color_strength_display.get()}"
            ]

            if not self.use_gpu_var.get():
                command.append("--disable_gpu")

            self.siril.log(f"Denoise mode: {self.denoise_mode_var.get()}", s.LogColor.BLUE)
            self.siril.log(f"Luma strength: {self.lum_strength_display.get()}", s.LogColor.BLUE)
            self.siril.log(f"Color strength: {self.color_strength_display.get()}", s.LogColor.BLUE)

            if self.separate_channels.get():
                command.append("--separate-channels")
                self.siril.log("Denoise separate channels", s.LogColor.BLUE)

            #print(f"Running command: {' '.join(command)}")
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
                        self.siril.update_progress("Denoising...", percentage / 100)

                buffer = lines[-1]

            await process.wait()

            if process.returncode != 0:
                stderr = await process.stderr.read()
                error_message = stderr.decode('utf-8', errors='ignore')
                raise subprocess.CalledProcessError(
                    process.returncode,
                    denoiseExecutable,
                    error_message
                )

            return True
        
        except Exception as e:
            self.siril.log(f"Unhandled exception in RunCosmicClarity(): {str(e)}", s.LogColor.SALMON)
            return False

    async def ApplyChanges(self):
        try:
            # Claim the processing thread
            with self.siril.image_lock():
                # get the current image filename and construct our new temp file names
                cwd = os.path.dirname(self.siril.get_image_filename())
                inputFile = os.path.join(cwd, "cc-denoise-temp-input.fits")
                outputFile = os.path.join(cwd, "cc-denoise-temp-output.fits")

                # get current image data and save to our temp input file
                data = self.siril.get_image_pixeldata()
                hdu = fits.PrimaryHDU(data)
                hdu.writeto(inputFile, overwrite=True)

                # kick off the denoise process
                self.siril.update_progress("Cosmic Clarity Denoise starting...", 0)
                success = await self.RunCosmicClarity(inputFile, outputFile)

                # load up the file on success and get out of dodge
                if success:
                    # load the resulting image and set it in Siril
                    with fits.open(outputFile) as hdul:
                        data = hdul[0].data
                        if data.dtype != np.float32:
                            data = np.array(data, dtype=np.float32)
                        self.siril.undo_save_state(f"CC denoise: mode='{self.denoise_mode_var.get()}' "
                                                   f"luma={self.lum_strength_var.get():.2f} "
                                                   f"color={self.color_strength_var.get():.2f}")
                        self.siril.set_image_pixeldata(data)
                    self.siril.log("Denoise complete.", s.LogColor.GREEN)
                else:
                    self.siril.log("Denose failed.", s.LogColor.SALMON)

        except Exception as e:
            self.siril.log(f"Unhandled exception in ApplyChanges(): {str(e)}", s.LogColor.SALMON)
            self.siril.log("Denoise failed.", s.LogColor.SALMON)

        finally:
            if os.path.exists(inputFile):
                os.remove(inputFile)
            if os.path.exists(outputFile):
                os.remove(outputFile)

            # always modify tkinter widgets from the main thread    
            self.root.after(0, lambda: self.apply_btn.state(['!disabled']))
            self.siril.reset_progress()

def main():
    try:
        root = ThemedTk()
        SirilDenoiseInterface(root)
        sv_ttk.set_theme("dark")
        root.mainloop()
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
