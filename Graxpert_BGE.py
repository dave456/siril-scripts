import sirilpy as s
s.ensure_installed("ttkthemes")
s.ensure_installed("astropy")
s.ensure_installed("numpy")

import os
import sys
import asyncio
import subprocess
import threading

import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedTk # type: ignore
from sirilpy import tksiril
from astropy.io import fits # type: ignore
import numpy as np # type: ignore

graxpertTemp = "graxpert-temp.fits"
graxpertExecutable = "c:/GraXpert2/GraXpert.exe"

class SirilBackgrounExtractInterface:
    """Siril interface class for background extraction using GraXpert."""

    def __init__(self, root):
        """SirilBackgrounExtractInterface constructor"""
        self.root = root
        self.root.title(f"GraXpert Background Extract")
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
            """Create the GUI widgets"""

            # Main frame
            main_frame = ttk.Frame(self.root, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Options Frame
            options_frame = ttk.LabelFrame(main_frame, text="Options", padding=10)
            options_frame.pack(fill=tk.X, padx=5, pady=5)

            # Gradient Smoothing Widget
            gradient_smoothing_frame = ttk.Frame(options_frame)
            gradient_smoothing_frame.pack(fill=tk.X, pady=5)
            ttk.Label(gradient_smoothing_frame, text="Gradient Smoothing:").pack(side=tk.LEFT)

            self.gradient_smoothing_var = tk.DoubleVar(value=1.0)
            gradient_smoothing_scale = ttk.Scale(
                gradient_smoothing_frame,
                from_=0.0,
                to=1.0,
                orient=tk.HORIZONTAL,
                variable=self.gradient_smoothing_var,
                length=200
            )

            gradient_smoothing_scale.pack(side=tk.LEFT, padx=10, expand=True)
            ttk.Label(
                gradient_smoothing_frame,
                textvariable=self.gradient_smoothing_var,
                width=5
            ).pack(side=tk.LEFT)

            # Add trace to update val when slider changes
            self.gradient_smoothing_var.trace_add("write", self.update_gradient_smoothing)

            # Action Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)

            # Close Button
            close_btn = ttk.Button(
                button_frame,
                text="Close",
                command=self.OnClose,
                style="TButton"
            )
            close_btn.pack(side=tk.LEFT, padx=5)

            # Apply Button
            apply_btn = ttk.Button(
                button_frame,
                text="Apply",
                command=self.OnApply,
                style="TButton"
            )
            apply_btn.pack(side=tk.LEFT, padx=5)

            # Bind keys for closing and applying
            self.root.protocol("WM_DELETE_WINDOW", self.OnClose)
            self.root.bind("<Escape>", lambda e: self.OnClose())
            self.root.bind("<Return>", lambda e: self.OnApply())
            self.root.bind("<KP_Enter>", lambda e: self.OnApply())
            
    def OnApply(self):
        """Callback for the Apply button."""
        self.root.after(0, self.RunApplyChanges)

    def RunApplyChanges(self):
        """Run the async task to apply changes."""
        threading.Thread(target=lambda: asyncio.run(self.ApplyChanges()), daemon=True).start()

    def OnClose(self):
        """Callback for the Close button."""
        self.siril.disconnect()
        self.root.quit()
        self.root.destroy()

    def update_gradient_smoothing(self, *args):
        """Update gradient smoothing value to two decimal places."""
        self.gradient_smoothing_var.set(f"{self.gradient_smoothing_var.get():.2f}")

    async def ApplyChanges(self):
        try:
            # Claim the processing thread
            with self.siril.image_lock():
                # Get the current image filename
                curfilename = self.siril.get_image_filename()
                basename = os.path.basename(curfilename)
                directory = os.path.dirname(curfilename)
                outputFileNoSuffix = os.path.join(directory, f"{basename.split('.')[0]}-bge-temp")
                outputFile = outputFileNoSuffix + ".fits"

                # Check if the temporary file exists and remove it                
                if os.path.exists(graxpertTemp):
                    os.remove(graxpertTemp)

                # Save the current image to a temporary fits file
                self.siril.cmd("save", graxpertTemp)

                args = [
                    graxpertTemp, "-cli", "-cmd", "background-extraction",
                    "-ai_version", "-smoothing", str(self.gradient_smoothing_var.get()),
                    "-output", outputFileNoSuffix
                ]

                # Check if the output file already exists
                if os.path.exists(outputFile):
                    print(f"Output file {outputFile} already exists. Removing it.")
                    os.remove(outputFile)

                # Run GraXpert
                print("Running background extraction...")
                print(f"Command: {graxpertExecutable} {' '.join(args)}")
                self.siril.update_progress("Graxpert background extraction running...", 0)
                subprocess.run([graxpertExecutable] + args, check=True, text=True, capture_output=True)
                print("Background extraction completed.")

                # load the resulting image and set it in Siril
                with fits.open(os.path.basename(outputFile)) as hdul:
                    print("Loading result: " + os.path.basename(outputFile))
                    data = hdul[0].data
                    if data.dtype != np.float32:
                        data = np.array(data, dtype=np.float32)
                    self.siril.undo_save_state(f"GraXpert background extraction smoothing={self.gradient_smoothing_var.get():.2f}")
                    self.siril.set_image_pixeldata(data)

        except Exception as e:
            print(f"Error in apply_changes: {str(e)}")
            self.siril.update_progress(f"Error: {str(e)}", 0)

        finally:
            # Clean up temporary file
            if os.path.exists(graxpertTemp):
                os.remove(graxpertTemp)
            if os.path.exists(outputFile):
                os.remove(outputFile)
            self.siril.disconnect()
            self.root.quit()
            self.root.destroy()

def main():
    try:
        root = ThemedTk(theme="arc")
        app = SirilBackgrounExtractInterface(root)
        root.mainloop()
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
