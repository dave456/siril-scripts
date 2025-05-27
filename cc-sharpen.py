
import sirilpy as s
s.ensure_installed("ttkthemes")
s.ensure_installed("astropy")

import os
import re
import sys
import math
import asyncio
import subprocess
from astropy.io import fits # type: ignore

import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedTk # type: ignore
from sirilpy import tksiril

sharpenTemp = "sharpen-temp.fits"
sharpenResult = "sharpen-temp_sharpened.fits"
cosmicClarityLocation = "C:/CosmicClarity"
sharpenExecutable = "C:/CosmicClarity/setiastrocosmicclarity.exe"

class SirilCosmicClarityInterface:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Cosmic Clarity Sharpening")
        self.root.resizable(False, False)

        self.style = tksiril.standard_style()

        # Initialize Siril connection
        self.siril = s.SirilInterface()

        try:
            self.siril.connect()
        except s.SirilConnectionError:
            self.siril.error_messagebox("Failed to connect to Siril")
            self.close_dialog()
            return

        if not self.siril.is_image_loaded():
            self.siril.error_messagebox("No image loaded")
            self.close_dialog()
            return

        try:
            self.siril.cmd("requires", "1.3.6")
        except s.CommandError:
            self.close_dialog()
            return

        tksiril.match_theme_to_siril(self.root, self.siril)

        # Create widgets
        self.create_widgets()

    def truncate(self, value, precision=2):
            """Truncate a value to the specified number of decimal places.

            Args:
                value (float): The value to truncate.
                precision (int): The number of decimal places to truncate to. Default is 2.
            """
            factor = 10 ** precision
            return math.floor(value * factor) / factor

    def update_stellar_amount_display(self, *args):
        value = self.stellar_amount_var.get()
        rounded_value = self.truncate(value)
        self.stellar_amount_var.set(f"{rounded_value:.2f}")

    def update_non_stellar_amount_display(self, *args):
        value = self.non_stellar_amount_var.get()
        rounded_value = self.truncate(value)
        self.non_stellar_amount_var.set(f"{rounded_value:.2f}")

    def update_non_stellar_psf_display(self, *args):
        value = self.non_stellar_psf_var.get()
        rounded_value = self.truncate(value)
        self.non_stellar_psf_var.set(f"{rounded_value:.1f}")

    def create_widgets(self):
        """Create the main dialog widgets."""

        # Main frame
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Sharpening Mode Frame
        strength_frame = ttk.LabelFrame(main_frame, text="Options", padding=10)
        strength_frame.pack(fill=tk.X, padx=5, pady=5)

        # GPU Checkbox
        self.use_gpu_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            strength_frame,
            text="Use GPU",
            variable=self.use_gpu_var,
            style="TCheckbutton"
        ).pack(anchor=tk.W, pady=2)

        # Sharpen channels separately Checkbox
        self.sharpen_channels_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            strength_frame,
            text="Sharpen channels separately",
            variable=self.sharpen_channels_var,
            style="TCheckbutton"
        ).pack(anchor=tk.W, pady=2)

        # Sharpening Mode Frame
        mode_frame = ttk.LabelFrame(main_frame, text="Sharpening Mode", padding=10)
        mode_frame.pack(fill=tk.X, padx=5, pady=5)

        self.sharpening_mode_var = tk.StringVar(value="Both")
        sharpening_modes = ["Stellar Only", "Non-Stellar Only", "Both"]
        for mode in sharpening_modes:
            ttk.Radiobutton(
                mode_frame,
                text=mode,
                variable=self.sharpening_mode_var,
                value=mode
            ).pack(anchor=tk.W, pady=2)

        # Sharpening Strength Frame
        strength_frame = ttk.LabelFrame(main_frame, text="Strength", padding=10)
        strength_frame.pack(fill=tk.X, padx=5, pady=5)

        # Non-Stellar PSF
        non_stellar_psf_frame = ttk.Frame(strength_frame)
        non_stellar_psf_frame.pack(fill=tk.X, pady=5)
        ttk.Label(non_stellar_psf_frame, text="Non-Stellar PSF:").pack(side=tk.LEFT)

        self.non_stellar_psf_var = tk.DoubleVar(value="3.0")
        non_stellar_psf_scale = ttk.Scale(
            non_stellar_psf_frame,
            from_=1.0,
            to=8.0,
            orient=tk.HORIZONTAL,
            variable=self.non_stellar_psf_var,
            length=200
        )
        non_stellar_psf_scale.pack(side=tk.LEFT, padx=10, expand=True)
        ttk.Label(
            non_stellar_psf_frame,
            textvariable=self.non_stellar_psf_var,
            width=5
        ).pack(side=tk.LEFT)

        # set callback to update display when slider changes
        self.non_stellar_psf_var.trace_add("write", self.update_non_stellar_psf_display)

        # Stellar Sharpening Amount
        stellar_amount_frame = ttk.Frame(strength_frame)
        stellar_amount_frame.pack(fill=tk.X, pady=5)
        ttk.Label(stellar_amount_frame, text="Stellar Sharpening:").pack(side=tk.LEFT)

        self.stellar_amount_var = tk.DoubleVar(value=0.5)
        stellar_amount_scale = ttk.Scale(
            stellar_amount_frame,
            from_=0.0,
            to=1.0,
            orient=tk.HORIZONTAL,
            variable=self.stellar_amount_var,
            length=200
        )
        stellar_amount_scale.pack(side=tk.LEFT, padx=10, expand=True)
        ttk.Label(
            stellar_amount_frame,
            textvariable=self.stellar_amount_var,
            width=5
        ).pack(side=tk.LEFT)

        # Add trace to update display when slider changes
        self.stellar_amount_var.trace_add("write", self.update_stellar_amount_display)

        # Non-Stellar Sharpening Amount
        non_stellar_amount_frame = ttk.Frame(strength_frame)
        non_stellar_amount_frame.pack(fill=tk.X, pady=5)
        ttk.Label(non_stellar_amount_frame, text="Non-Stellar Sharpening:").pack(side=tk.LEFT)

        self.non_stellar_amount_var = tk.DoubleVar(value=0.5)
        non_stellar_strength_scale = ttk.Scale(
            non_stellar_amount_frame,
            from_=0.0,
            to=1.0,
            orient=tk.HORIZONTAL,
            variable=self.non_stellar_amount_var,
            length=200
        )
        non_stellar_strength_scale.pack(side=tk.LEFT, padx=10, expand=True)
        ttk.Label(
            non_stellar_amount_frame,
            textvariable=self.non_stellar_amount_var,
            width=5
        ).pack(side=tk.LEFT)

        # Add callback to update display when slider changes
        self.non_stellar_amount_var.trace_add("write", self.update_non_stellar_amount_display)

        # Action Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        close_btn = ttk.Button(
            button_frame,
            text="Close",
            command=self.OnClose,
            style="TButton"
        )
        close_btn.pack(side=tk.LEFT, padx=5)

        apply_btn = ttk.Button(
            button_frame,
            text="Apply",
            command=self.OnApply,
            style="TButton"
        )
        apply_btn.pack(side=tk.LEFT, padx=5)

    def OnApply(self):
        """Handle apply button click."""
        self.root.after(0, self.RunApplyChanges)

    def OnClose(self):
        """Handle close button click."""
        self.root.quit()
        self.root.destroy()

    def RunApplyChanges(self):
        asyncio.run(self.ApplyChanges())

    async def run_cosmic_clarity(self):
        """Run Cosmic Clarity"""
        try:
            command = [
                sharpenExecutable,
                f"--sharpening_mode={self.sharpening_mode_var.get()}",
                f"--stellar_amount={self.stellar_amount_var.get()}",
                f"--nonstellar_amount={self.non_stellar_amount_var.get()}",
                f"--nonstellar_strength={self.non_stellar_psf_var.get()}"
            ]

            if not self.use_gpu_var.get():
                command.append("--disable_gpu")

            if self.sharpen_channels_var.get():
                command.append("--sharpen_channels_separately")

            print(f"Running command: {' '.join(command)}")

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
                    match = re.search(r'(\d+\.\d+)%', line)
                    if match:
                        percentage = float(match.group(1))
                        message = "Seti Astro Cosmic Clarity Sharpen progress..."
                        self.siril.update_progress(message, percentage / 100)
                    else:
                        print(line.strip())

                buffer = lines[-1]

            await process.wait()

            if process.returncode != 0:
                stderr = await process.stderr.read()
                error_message = stderr.decode('utf-8', errors='ignore')
                raise subprocess.CalledProcessError(
                    process.returncode,
                    sharpenExecutable,
                    error_message
                )
            
            return True

        except Exception as e:
            print(f"Error in run_cosmic_clarity: {str(e)}")
            return False

    async def ApplyChanges(self):
        try:
            # claim the processing thread
            with self.siril.image_lock():

                # save the current image to a temporary fits file and move to input directory
                if os.path.exists(sharpenTemp):
                    os.remove(sharpenTemp)
                self.siril.cmd("save", sharpenTemp)
                os.rename(sharpenTemp, os.path.join(cosmicClarityLocation, "input", sharpenTemp))

                # kick off the sharpening process
                self.siril.update_progress("Seti Astro Cosmic Clarity Sharpen starting...", 0)
                success = await self.run_cosmic_clarity()

                if success:
                    # get the current image filename and construct our new output filename
                    curfilename = self.siril.get_image_filename()
                    basename = os.path.basename(curfilename)
                    directory = os.path.dirname(curfilename)
                    outputfilename = os.path.join(directory, f"{basename.split('.')[0]}-sharp.fits")

                    # grab the sharpened result
                    if os.path.exists(os.path.join(cosmicClarityLocation, "output", sharpenResult)):
                        print(f"Moving {sharpenResult} to {outputfilename}")
                        if os.path.isfile(outputfilename):
                            os.remove(outputfilename)
                        os.rename(
                            os.path.join(cosmicClarityLocation, "output", sharpenResult),
                            outputfilename
                        )

                    # update the FITS header with the sharpening parameters
                    AddHistory(os.path.basename(outputfilename), 
                                f"Cosmic Clarity Sharpen: mode='{self.sharpening_mode_var.get()}', "
                                f"stellar amount={self.stellar_amount_var.get()}, "
                                f"non-stellar amount={self.non_stellar_amount_var.get()}, "
                                f"non-stellar PSF={self.non_stellar_psf_var.get()}")
                    
                    # load the image up in the GUI, and reset the status
                    self.siril.cmd("load", os.path.basename(outputfilename))
                    self.siril.reset_progress()
                    self.siril.log("Seti Astro Cosmic Clarity Sharpening complete.")

        except Exception as e:
            print(f"Error in apply_changes: {str(e)}")
            self.siril.update_progress(f"Error: {str(e)}", 0)

        finally:
            if os.path.exists(sharpenTemp):
                os.remove(sharpenTemp)
            if os.path.exists(os.path.join(cosmicClarityLocation, "input", sharpenTemp)):
                os.remove(os.path.join(cosmicClarityLocation, "input", sharpenTemp))
            self.root.quit()
            self.root.destroy()

def AddHistory(filename, history_text):
    """Adds a history record to the header of a FITS file.

    Args:
        filename (str): Path to the FITS file.
        history_text (str): The history text to add.
    """
    try:
        with fits.open(filename, mode='update') as hdul:
            hdul[0].header.add_history(history_text)
    except FileNotFoundError:
        print(f"Error: The file '{filename}' was not found.")
    except Exception as e:
         print(f"An error occurred: {e}")

def main():
    try:
        root = ThemedTk()
        app = SirilCosmicClarityInterface(root)
        root.mainloop()
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
