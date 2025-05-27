import sirilpy
sirilpy.ensure_installed("ttkthemes")
sirilpy.ensure_installed("astropy")

import os
import sys
import math
import asyncio
import subprocess
from astropy.io import fits # type: ignore

import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedTk # type: ignore
from sirilpy import tksiril

graxpertTemp = "graxpert-temp.fits"
graxpertExecutable = "c:/GraXpert2/GraXpert.exe"


class SirilDenoiseInterface:
    # constructor
    def __init__(self, root):
        self.root = root
        self.root.title(f"GraXpert Denoise")
        self.root.resizable(False, False)
        self.style = tksiril.standard_style()

        # Initialize Siril connection
        self.siril = sirilpy.SirilInterface()

        try:
            self.siril.connect()
        except sirilpy.SirilConnectionError:
            self.siril.error_messagebox("Failed to connect to Siril")
            self.close_dialog()
            return

        if not self.siril.is_image_loaded():
            self.siril.error_messagebox("No image loaded")
            self.close_dialog()
            return

        try:
            self.siril.cmd("requires", "1.3.6")
        except sirilpy.CommandError:
            self.close_dialog()
            return

        tksiril.match_theme_to_siril(self.root, self.siril)
        self.create_widgets()

    def truncate(self, value, precision=2):
            """Truncate a value to the specified number of decimal places.

            Args:
                value (float): The value to truncate.
                precision (int): The number of decimal places to truncate to. Default is 2.
            """
            factor = 10 ** precision
            return math.floor(value * factor) / factor

    def update_denoise_strength_display(self, *args):
            """Update the strength value in the slider widget"""
            value = self.denoise_strength_var.get()
            rounded_value = self.truncate(value)
            self.denoise_strength_var.set(f"{rounded_value:.2f}")

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
            self.denoise_strength_var = tk.DoubleVar(value=1.0)
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
            self.denoise_strength_var.trace_add("write", self.update_denoise_strength_display)        
        
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
        """Callback for the Apply button."""
        self.root.after(0, self._run_async_task)

    def OnClose(self):
        """Callback for the Close button."""
        self.root.quit()
        self.root.destroy()

    def _run_async_task(self):
        """Run Apply changes asynchronously."""
        asyncio.run(self.ApplyChanges())

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
                #print(f"Denoise strength: {denoise_strength}")

                # get the current image filename and construct our new output filename
                curfilename = self.siril.get_image_filename()
                basename = os.path.basename(curfilename)
                directory = os.path.dirname(curfilename)
                outputFileNoSuffix = os.path.join(directory, f"{basename.split('.')[0]}-nr")
                outputFile = outputFileNoSuffix + ".fits"
                #print(f"Output file will be: {outputFileNoSuffix}")

                # save the current image to a temporary fits file and move to input directory
                if os.path.exists(graxpertTemp):
                    os.remove(graxpertTemp)
                self.siril.cmd("save", graxpertTemp)

                # Call graxpert.exe to run denoise, graxpert will add the .fits suffix
                args = [graxpertTemp, "-cli", "-cmd", "denoising", "-strength", str(denoise_strength), "-output", outputFileNoSuffix]
                #print(f"Running GraXpert with arguments: {args}")

                # see if the output file already exists - remove it if it does
                if os.path.exists(outputFile):
                    print(f"Output file {outputFile} already exists. Removing it.")
                    os.remove(outputFile)

                # run graxpert
                print("Running GraXpert denoise...")
                self.siril.update_progress("Graxpert Denoise running...", 0.10)
                result = subprocess.run([graxpertExecutable] + args, check=True, text=True, capture_output=True)
                print("GraXpert denoise completed.")

                AddHistory(outputFile, f"GraXpert Denoise applied with strength {denoise_strength:.2f}")

                # load up the file on success and get out of dodge
                self.siril.cmd("load", os.path.basename(outputFile))
                
        except subprocess.CalledProcessError as e:
            print(f"Error occurred while running GraXpert: {e}")
        
        except Exception as e:
            print(f"Error in denoise: {str(e)}")

        finally:
            if os.path.exists(graxpertTemp):
                os.remove(graxpertTemp)
            self.siril.reset_progress()
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
        app = SirilDenoiseInterface(root)
        root.mainloop()
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
