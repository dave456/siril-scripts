
import sirilpy as s
s.ensure_installed("ttkthemes")
s.ensure_installed("astropy")
s.ensure_installed("numpy")

import os
import re
import sys
import asyncio
import subprocess
import threading

import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedTk  # type: ignore
from sirilpy import tksiril
from astropy.io import fits     # type: ignore
import numpy as np              # type: ignore

denoiseTemp = ""
denoiseResult = ""
cosmicClarityLocation = "C:/CosmicClarity"
denoiseExecutable = "C:/CosmicClarity/setiastrocosmicclarity_denoise.exe"


class SirilDenoiseInterface:
    # constructor
    def __init__(self, root):
        self.root = root
        self.root.title(f"Cosmic Clarity Denoise")
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
        self.create_widgets()

    def create_widgets(self):
            """Create the GUI widgets for the Cosmic Clarity Denoise interface."""
            # Main frame
            main_frame = ttk.Frame(self.root, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Options Mode Frame
            options_frame = ttk.LabelFrame(main_frame, text="Options", padding=10)
            options_frame.pack(fill=tk.X, padx=5, pady=5)

            # GPU Checkbox
            self.use_gpu_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(
                options_frame,
                text="Use GPU",
                variable=self.use_gpu_var,
                style="TCheckbutton"
            ).pack(anchor=tk.W, pady=2)

            # Denoise Mode Frame
            mode_frame = ttk.LabelFrame(main_frame, text="Denoise Mode", padding=10)
            mode_frame.pack(fill=tk.X, padx=5, pady=5)

            self.denoise_mode_var = tk.StringVar(value="full")
            denoise_modes = ["luminance", "full", "separate"]
            for mode in denoise_modes:
                ttk.Radiobutton(
                    mode_frame,
                    text=mode.capitalize(),
                    variable=self.denoise_mode_var,
                    value=mode
                ).pack(anchor=tk.W, pady=2)

            # Strength Frame
            strength_frame = ttk.LabelFrame(main_frame, text="Strength Settings", padding=10)
            strength_frame.pack(fill=tk.X, padx=5, pady=5)

            # Denoise Strength
            denoise_str_frame = ttk.Frame(strength_frame)
            denoise_str_frame.pack(fill=tk.X, pady=5)
            ttk.Label(denoise_str_frame, text="  Denoise Strength:").pack(side=tk.LEFT)
            self.denoise_strength_var = tk.DoubleVar(value=0.80)
            denoise_strength_scale = ttk.Scale(
                denoise_str_frame,
                from_=0.0,
                to=1.0,
                orient=tk.HORIZONTAL,
                variable=self.denoise_strength_var,
                length=200
            )
            denoise_strength_scale.pack(side=tk.LEFT, padx=10, expand=True)
            ttk.Label(
                denoise_str_frame,
                textvariable=self.denoise_strength_var,
                width=5
            ).pack(side=tk.LEFT)
            self.denoise_strength_var.trace_add("write", self.update_denoise_strength)

            # Color Denoise Strength
            color_denoise_str_frame = ttk.Frame(strength_frame)
            color_denoise_str_frame.pack(fill=tk.X, pady=5)
            ttk.Label(color_denoise_str_frame, text="  Color Denoise Strength:").pack(side=tk.LEFT)
            self.color_denoise_strength_var = tk.DoubleVar(value=0.80)
            color_denoise_strength_scale = ttk.Scale(
                color_denoise_str_frame,
                from_=0.0,
                to=1.0,
                orient=tk.HORIZONTAL,
                variable=self.color_denoise_strength_var,
                length=200
            )
            color_denoise_strength_scale.pack(side=tk.LEFT, padx=10, expand=True)
            ttk.Label(
                color_denoise_str_frame,
                textvariable=self.color_denoise_strength_var,
                width=5
            ).pack(side=tk.LEFT)
            self.color_denoise_strength_var.trace_add("write", self.update_color_denoise_strength)
        
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

    def update_denoise_strength(self, *args):
        """Update denoise strength value to two decimal places."""
        self.denoise_strength_var.set(f"{self.denoise_strength_var.get():.2f}")

    def update_color_denoise_strength(self, *args):
        """Update color denoise strength value to two decimal places."""
        # TODO: we should really disable the apply and close buttons here to prevent multiple clicks
        self.color_denoise_strength_var.set(f"{self.color_denoise_strength_var.get():.2f}")

    def OnClose(self):
        """Callback for the Close button."""
        self.siril.disconnect()
        self.root.quit()
        self.root.destroy()

    def OnApply(self):
        """Callback for the Apply button."""
        self.root.after(0, self.RunApplyChanges)

    def RunApplyChanges(self):
        """Run Apply changes in a separate thread to avoid blocking the GUI."""
        threading.Thread(target=lambda: asyncio.run(self.ApplyChanges()), daemon=True).start()

    async def run_cosmic_clarity(self):
        """Run Cosmic Clarity denoise."""
        try:
            command = [
                denoiseExecutable,
                f"--denoise_mode={self.denoise_mode_var.get()}",
                f"--denoise_strength={self.denoise_strength_var.get()}",
                f"--color_denoise_strength={self.color_denoise_strength_var.get()}"
            ]

            if not self.use_gpu_var.get():
                command.append("--disable_gpu")

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
                        message = "Seti Astro Cosmic Clarity Denoise progress..."
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
                    denoiseExecutable,
                    error_message
                )

            return True
        
        except Exception as e:
            print(f"Error in run_cosmic_clarity: {str(e)}")
            return False

    async def ApplyChanges(self):
        try:
            # Claim the processing thread
            with self.siril.image_lock():
                # get the current image filename and construct our new output filename
                curfilename = self.siril.get_image_filename()
                basename = os.path.basename(curfilename)
                directory = os.path.dirname(curfilename)
                outputfilename = os.path.join(directory, f"{basename.split('.')[0]}-denoise-temp.fits")
                denoiseTemp = f"{basename.split('.')[0]}-denoise.fits"
                denoiseResult = f"{basename.split('.')[0]}-denoise_denoised.fits"

                # save the current image to a temporary fits file and move to input directory
                if os.path.exists(denoiseTemp):
                    os.remove(denoiseTemp)
                self.siril.cmd("save", denoiseTemp)
                os.rename(denoiseTemp, os.path.join(cosmicClarityLocation, "input", denoiseTemp))

                # kick off the denoise process
                self.siril.update_progress("Seti Astro Cosmic Clarity Denoise starting...", 0)
                success = await self.run_cosmic_clarity()

                # load up the file on success and get out of dodge
                if success:
                    if os.path.exists(os.path.join(cosmicClarityLocation, "output", denoiseResult)):
                        print(f"Moving {denoiseResult} to {outputfilename}")
                        if os.path.isfile(outputfilename):
                            os.remove(outputfilename)
                        os.rename(
                            os.path.join(cosmicClarityLocation, "output", denoiseResult),
                            outputfilename
                        )

                    # load the resulting image and set it in Siril
                    with fits.open(outputfilename) as hdul:
                        data = hdul[0].data
                        if data.dtype != np.float32:
                            data = np.array(data, dtype=np.float32)
                        self.siril.undo_save_state(f"CC denoise: mode='{self.denoise_mode_var.get()}' str={self.denoise_strength_var.get():.2f} color str={self.color_denoise_strength_var.get():.2f}")
                        self.siril.set_image_pixeldata(data)

                    self.siril.reset_progress()
                    self.siril.log("Seti Astro Cosmic Clarity Denoise complete.")

        except Exception as e:
            print(f"Error in apply_changes: {str(e)}")
            self.siril.update_progress(f"Error: {str(e)}", 0)

        finally:
            if os.path.exists(denoiseTemp):
                os.remove(denoiseTemp)
            if os.path.exists(os.path.join(cosmicClarityLocation, "input", denoiseTemp)):
                os.remove(os.path.join(cosmicClarityLocation, "input", denoiseTemp))
            if os.path.exists(outputfilename):
                os.remove(outputfilename)
            self.siril.disconnect()
            self.root.quit()
            self.root.destroy()

def main():
    try:
        root = ThemedTk()
        app = SirilDenoiseInterface(root)
        root.mainloop()
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
