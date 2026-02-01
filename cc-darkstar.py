#
# Simplfied Cosmic Clarity darkstar interface for Siril
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2026 lindner234 <AT> gmail
#

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
import shutil

import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedTk
from sirilpy import tksiril
from astropy.io import fits
import numpy as np

cosmicClarityLocation = "C:/CosmicClarity"
darkstarExecutable = "C:/CosmicClarity/setiastrocosmicclarity_darkstar.exe"

class SirilDarkstarInterface:
    # constructor
    def __init__(self, root):
        self.root = root
        self.root.title(f"Cosmic Clarity Darkstar")
        self.root.attributes("-topmost", True)
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

        tksiril.match_theme_to_siril(self.root, self.siril)
        self.create_widgets()

    def create_widgets(self):
            """Create the GUI widgets for the Darkstar interface."""
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

            # Create star mask
            self.create_star_mask = tk.BooleanVar(value=True)
            ttk.Checkbutton(
                options_frame,
                text="Create Star Mask",
                variable=self.create_star_mask,
                style="TCheckbutton"
            ).pack(anchor=tk.W, pady=2)

            # Star Removal Mode Frame
            mode_frame = ttk.LabelFrame(main_frame, text="Star Removal Mode", padding=10)
            mode_frame.pack(fill=tk.X, padx=5, pady=5)

            self.darkstar_mode_var = tk.StringVar(value="unscreen")
            darkstar_modes = ["unscreen", "additive"]
            for mode in darkstar_modes:
                ttk.Radiobutton(
                    mode_frame,
                    text=mode.capitalize(),
                    variable=self.darkstar_mode_var,
                    value=mode
                ).pack(anchor=tk.W, pady=2)

            # Chunksize Frame
            chunk_frame = ttk.LabelFrame(main_frame, text="Chunk Size", padding=10)
            chunk_frame.pack(fill=tk.X, padx=5, pady=5)

            # Chunk size
            chunk_size_frame = ttk.Frame(chunk_frame)
            chunk_size_frame.pack(fill=tk.X, pady=5)
            ttk.Label(chunk_size_frame, text="  Pixels:").pack(side=tk.LEFT)
            self.chunk_size = tk.IntVar(value=512)
            step = 64

            def on_scale_change(value):
                value = int(float(value))
                value = (value // step) * step
                self.chunk_size.set(value)
            
            chunk_size_scale = ttk.Scale(
                chunk_size_frame,
                from_=128,
                to=4096,
                orient=tk.HORIZONTAL,
                variable=self.chunk_size,
                length=200,
                command=on_scale_change
            )
            chunk_size_scale.pack(side=tk.LEFT, padx=10, expand=True)
            ttk.Label(
                chunk_size_frame,
                textvariable=self.chunk_size,
                width=5
            ).pack(side=tk.LEFT)
            self.chunk_size.trace_add("write", self.update_chunk_size)
        
            # Action Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)
            apply_btn = ttk.Button(
                button_frame,
                text="Apply",
                command=self.OnApply,
                style="TButton"
            )
            apply_btn.pack(side=tk.LEFT, padx=5)

    def update_chunk_size(self, *args):
        self.chunk_size.set(f"{self.chunk_size.get()}")

    def OnApply(self):
        """Callback for the Apply button."""
        self.root.after(0, self.RunApplyChanges)

    def RunApplyChanges(self):
        """Run Apply changes in a separate thread to avoid blocking the GUI."""
        threading.Thread(target=lambda: asyncio.run(self.ApplyChanges()), daemon=True).start()

    async def run_cosmic_clarity(self):
        """Run Cosmic Clarity Darkstar."""
        try:
            command = [
                darkstarExecutable,
                f"--star_removal_mode={self.darkstar_mode_var.get()}",
                f"--chunk_size={self.chunk_size.get()}",
                f"--overlap={self.chunk_size.get() // 8}"
            ]

            if not self.use_gpu_var.get():
                command.append("--disable_gpu")

            if self.create_star_mask.get():
                command.append("--show_extracted_stars")

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
                        message = "Seti Astro Darkstar progress..."
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
                    darkstarExecutable,
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
                starlessResult = f"{basename.split('.')[0]}_starless.fits"
                starmaskResult = f"{basename.split('.')[0]}_stars_only.fits"

                # save the current version of the file, because we will be opening the starless image
                self.siril.cmd("save", curfilename)
                shutil.copy(curfilename, os.path.join(cosmicClarityLocation, "input", os.path.basename(curfilename)))

                # kick off the darkstar process
                self.siril.update_progress("Seti Astro Darkstar starting...", 0)
                success = await self.run_cosmic_clarity()

                # load up the files on success and get out of dodge
                if success:
                    if os.path.exists(os.path.join(cosmicClarityLocation, "output", starlessResult)):
                        print(f"Moving {starlessResult} to {directory}")
                        if os.path.isfile(starlessResult):
                            os.remove(starlessResult)
                        os.rename(
                            os.path.join(cosmicClarityLocation, "output", starlessResult),
                            starlessResult
                        )

                    if os.path.exists(os.path.join(cosmicClarityLocation, "output", starmaskResult)):
                        print(f"Moving {starmaskResult} to {directory}")
                        if os.path.isfile(starmaskResult):
                            os.remove(starmaskResult)
                        os.rename(
                            os.path.join(cosmicClarityLocation, "output", starmaskResult),
                            starmaskResult
                        )

                    # load the resulting image and set it in Siril
                    self.siril.cmd("load", starlessResult)
                    self.siril.reset_progress()
                    self.siril.log("Seti Astro Darkstar complete.")

        except Exception as e:
            print(f"Error in apply_changes: {str(e)}")
            self.siril.update_progress(f"Error: {str(e)}", 0)

        finally:
            if os.path.exists(os.path.join(cosmicClarityLocation, "input", os.path.basename(curfilename))):
                print(f"Removing temporary input file {os.path.join(cosmicClarityLocation, "input", os.path.basename(curfilename))}")
                os.remove(os.path.join(cosmicClarityLocation, "input", os.path.basename(curfilename)))
            if os.path.exists(os.path.join(cosmicClarityLocation, "output", starlessResult)):
                os.remove(os.path.join(cosmicClarityLocation, "output", starlessResult))
            if os.path.exists(os.path.join(cosmicClarityLocation, "output", starmaskResult)):
                os.remove(os.path.join(cosmicClarityLocation, "output", starmaskResult))

def main():
    try:
        root = ThemedTk()
        app = SirilDarkstarInterface(root)
        root.mainloop()
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
