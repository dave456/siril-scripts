#
# Simplfied GraXpert Denoise interface for Siril
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2026 lindner234 <AT> gmail
#

import sirilpy
sirilpy.ensure_installed("ttkthemes")
sirilpy.ensure_installed("astropy")
sirilpy.ensure_installed("numpy")

import os
import sys
import asyncio
import subprocess
import threading
from astropy.io import fits
import numpy as np

import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedTk
from sirilpy import tksiril

graxpertExecutable = "c:/GraXpert2/GraXpert.exe"


class SirilDenoiseInterface:
    # constructor
    def __init__(self, root):
        self.root = root
        self.root.title(f"GraXpert Denoise")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.style = tksiril.standard_style()

        # Initialize Siril connection
        self.siril = sirilpy.SirilInterface()

        try:
            self.siril.connect()
        except sirilpy.SirilConnectionError:
            self.siril.error_messagebox("Failed to connect to Siril")
            self.close_dialog()
            return

        tksiril.match_theme_to_siril(self.root, self.siril)
        self.create_widgets()

    def create_widgets(self):
            """Creates the GUI widgets for the GraXpert Denoise interface."""
            # Main frame
            main_frame = ttk.Frame(self.root, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Strength Frame
            options_frame = ttk.LabelFrame(main_frame, text="", padding=10)
            options_frame.pack(fill=tk.X, padx=5, pady=5)

            # Denoise Strength
            denoise_strength_frame = ttk.Frame(options_frame)
            denoise_strength_frame.pack(fill=tk.X, pady=5)

            ttk.Label(denoise_strength_frame, text="Denoise Strength:").pack(side=tk.LEFT)
            self.denoise_strength_var = tk.DoubleVar(value=0.80)
            denoise_strength_scale = ttk.Scale(
                denoise_strength_frame,
                from_=0.0,
                to=1.0,
                orient=tk.HORIZONTAL,
                variable=self.denoise_strength_var,
                length=200
            )
            denoise_strength_scale.pack(side=tk.LEFT, padx=10, expand=True)
            ttk.Label(
                denoise_strength_frame,
                textvariable=self.denoise_strength_var,
                width=5
            ).pack(side=tk.LEFT)

            # Add trace to update display when slider changes
            self.denoise_strength_var.trace_add("write", self.update_denoise_strength)        
        
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

    def update_denoise_strength(self, *args):
            """Update the strength value in the slider widget to two decimal places."""
            self.denoise_strength_var.set(f"{self.denoise_strength_var.get():.2f}")
    
    def OnApply(self):
        """Callback for the Apply button."""
        if not self.siril.is_image_loaded():
            self.siril.error_messagebox("No image loaded")
            return
        self.apply_btn.state(['disabled'])
        self.root.after(0, self.RunApplyChanges)

    def RunApplyChanges(self):
        """Run Apply changes asynchronously."""
        threading.Thread(target=lambda: asyncio.run(self.ApplyChanges()), daemon=True).start()

    async def ApplyChanges(self):
        """
        Apply the denoise changes using GraXpert. This does all the work in a 
        separate thread to avoid blocking the GUI.
        """
        try:
            # Claim the processing thread
            with self.siril.image_lock():
                
                # Read user input values
                denoise_strength = self.denoise_strength_var.get()

                # get the current image filename and construct our new output filename
                curfilename = self.siril.get_image_filename()
                basename = os.path.basename(curfilename)
                directory = os.path.dirname(curfilename)
                outputFileNoSuffix = os.path.join(directory, f"{basename.split('.')[0]}-grax_nr-temp")
                outputFile = outputFileNoSuffix + ".fits"
                graxpertTemp = f"{basename.split('.')[0]}-temp-in.fits"

                # grab the current image data from siril and save to a temporary fits file
                data = self.siril.get_image_pixeldata()
                hdu = fits.PrimaryHDU(data)
                hdu.writeto(graxpertTemp, overwrite=True)

                # Call graxpert to run denoise, graxpert will add the .fits suffix
                args = [graxpertTemp, "-cli", "-cmd", "denoising", "-strength", str(denoise_strength), "-output", outputFileNoSuffix]

                # see if the output file already exists - remove it if it does
                if os.path.exists(outputFile):
                    print(f"Output file {outputFile} already exists. Removing it.")
                    os.remove(outputFile)

                # run graxpert
                self.siril.log(f"GraXpert denoise: ai=latest, strength={denoise_strength:.2f}...")
                #print(f"Command: {graxpertExecutable} {' '.join(args)}")
                self.siril.update_progress("GraXpert denoise running...", 0)
                subprocess.run([graxpertExecutable] + args, check=True, text=True, capture_output=True)

                # load image back into Siril
                with fits.open(os.path.basename(outputFile)) as hdul:
                    data = hdul[0].data
                    if data.dtype != np.float32:
                        data = np.array(data, dtype=np.float32)
                    self.siril.undo_save_state(f"GraXpert denoise: ai=latest, strength={denoise_strength:.2f}")
                    self.siril.set_image_pixeldata(data)

                self.siril.log("GraXpert denoise completed.", sirilpy.LogColor.GREEN)
                
        except subprocess.CalledProcessError as e:
            print(f"Error occurred while running GraXpert: {e}")
        
        except Exception as e:
            print(f"Error in denoise: {str(e)}")

        finally:
            if os.path.exists(graxpertTemp):
                os.remove(graxpertTemp)
            if os.path.exists(outputFile):
                os.remove(outputFile)

            # always modify tkinter widgets from the main thread    
            self.root.after(0, lambda: self.apply_btn.state(['!disabled']))

def main():
    try:
        root = ThemedTk()
        SirilDenoiseInterface(root)
        root.mainloop()
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
