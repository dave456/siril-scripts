# (c) Dave Lindner 2025
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Adds Ha data to RGB images by blending a continuum-subtracted Ha component
into the RGB image, with user-adjustable parameters.
"""
import sirilpy as s
s.ensure_installed("ttkthemes")
s.ensure_installed("astropy")
s.ensure_installed("numpy")

import os
import sys

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from ttkthemes import ThemedTk # type: ignore
from sirilpy import tksiril
from astropy.io import fits # type: ignore
import numpy as np # type: ignore

class SirilCSInterface:
    def __init__(self, root):
        """SirilCSInterface constructor"""
        self.root = root
        self.root.title(f"Continuum Subtraction")
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

            # Components Frame
            components_frame = ttk.LabelFrame(main_frame, text="Components", padding=10)
            components_frame.pack(fill=tk.X, padx=5, pady=5)

            # component file variables
            self.r_file_var = tk.StringVar()
            self.g_file_var = tk.StringVar()
            self.b_file_var = tk.StringVar()
            self.ha_file_var = tk.StringVar()
            self.hacs_file_var = tk.StringVar()

            # R COMPONENT INPUT
            R_frame = ttk.Frame(components_frame)
            R_frame.pack(fill=tk.X, padx=5, pady=5)
            ttk.Label(R_frame, text="R:", width=6).pack(side=tk.LEFT)
            r_entry = ttk.Entry(R_frame, textvariable=self.r_file_var, width=60)
            r_entry.pack(side=tk.LEFT, padx=5)

            def select_r_file():
                filename = filedialog.askopenfilename(title="Select R Component File", filetypes=[("FITS files", "*.fits"), ("All files", "*.*")])
                if filename:
                    self.r_file_var.set(filename)

            r_button = ttk.Button(R_frame, text="Select...", command=select_r_file)
            r_button.pack(side=tk.LEFT, padx=5)

            # G COMPONENT INPUT
            G_frame = ttk.Frame(components_frame)
            G_frame.pack(fill=tk.X, padx=5, pady=5)
            ttk.Label(G_frame, text="G:", width=6).pack(side=tk.LEFT)
            g_entry = ttk.Entry(G_frame, textvariable=self.g_file_var, width=60)
            g_entry.pack(side=tk.LEFT, padx=5)

            def select_g_file():
                filename = filedialog.askopenfilename(title="Select G Component File", filetypes=[("FITS files", "*.fits"), ("All files", "*.*")])
                if filename:
                    self.g_file_var.set(filename)
            
            g_button = ttk.Button(G_frame, text="Select...", command=select_g_file)
            g_button.pack(side=tk.LEFT, padx=5)

            # B COMPONENT INPUT
            B_frame = ttk.Frame(components_frame)
            B_frame.pack(fill=tk.X, padx=5, pady=5)
            ttk.Label(B_frame, text="B:", width=6).pack(side=tk.LEFT)
            b_entry = ttk.Entry(B_frame, textvariable=self.b_file_var, width=60)
            b_entry.pack(side=tk.LEFT, padx=5)

            def select_b_file():
                filename = filedialog.askopenfilename(title="Select B Component File", filetypes=[("FITS files", "*.fits"), ("All files", "*.*")])
                if filename:
                    self.b_file_var.set(filename)
            
            b_button = ttk.Button(B_frame, text="Select...", command=select_b_file)
            b_button.pack(side=tk.LEFT, padx=5)

            # HA COMPONENT INPUT
            HA_frame = ttk.Frame(components_frame)
            HA_frame.pack(fill=tk.X, padx=5, pady=5)
            ttk.Label(HA_frame, text="Ha:", width=6).pack(side=tk.LEFT)
            ha_entry = ttk.Entry(HA_frame, textvariable=self.ha_file_var, width=60)
            ha_entry.pack(side=tk.LEFT, padx=5)

            def select_ha_file():
                filename = filedialog.askopenfilename(title="Select Ha Component File", filetypes=[("FITS files", "*.fits"), ("All files", "*.*")])
                if filename:
                    self.ha_file_var.set(filename)
            
            ha_button = ttk.Button(HA_frame, text="Select...", command=select_ha_file)
            ha_button.pack(side=tk.LEFT, padx=5)

            # HaCS COMPONENT INPUT
            HaCS_frame = ttk.Frame(components_frame)
            HaCS_frame.pack(fill=tk.X, padx=5, pady=5)
            ttk.Label(HaCS_frame, text="HaCS:", width=6).pack(side=tk.LEFT)
            hacs_entry = ttk.Entry(HaCS_frame, textvariable=self.hacs_file_var, width=60)
            hacs_entry.pack(side=tk.LEFT, padx=5)

            def select_hacs_file():
                filename = filedialog.askopenfilename(title="Select HaCS Component File", filetypes=[("FITS files", "*.fits"), ("All files", "*.*")])
                if filename:
                    self.hacs_file_var.set(filename)

            hacs_button = ttk.Button(HaCS_frame, text="Select...", command=select_hacs_file)
            hacs_button.pack(side=tk.LEFT, padx=5)

            # HaCS Computation Frame            
            hacs_frame = ttk.LabelFrame(main_frame, text="HaCS Computation", padding=10)
            hacs_frame.pack(fill=tk.X, padx=5, pady=5)

            # determine scaling factor c
            c_selection_frame = ttk.Frame(hacs_frame)
            c_selection_frame.pack(fill=tk.X, pady=5)
            ttk.Label(c_selection_frame, text="c:", width=10).pack(side=tk.LEFT)

            self.c_scaling_var = tk.DoubleVar()

            ttk.Label(
                c_selection_frame,
                textvariable=self.c_scaling_var,
                width=10
            ).pack(side=tk.LEFT)

            hasl_scaling_scale = ttk.Scale(
                c_selection_frame,
                from_=0.0,
                to=1.0,
                orient=tk.HORIZONTAL,
                variable=self.c_scaling_var,
                length=350
            )
            hasl_scaling_scale.pack(side=tk.LEFT, padx=10, expand=True)
            self.c_scaling_var.trace_add("write", self.OnCUpdate)
            self.c_scaling_var.set(0.5)

            # HaCS Action Buttons
            hacs_button_frame = ttk.Frame(main_frame)
            hacs_button_frame.pack(pady=10)

            estimate_c_btn = ttk.Button(
                hacs_button_frame,
                text="Estimate c",
                command=self.OnEstimateC,
                style="TButton"
            )
            estimate_c_btn.pack(side=tk.LEFT, padx=5)

            view_hasl_btn = ttk.Button(
                hacs_button_frame,
                text="Generate HaCS",
                command=self.OnGenerateHaCS,
                style="TButton"
            )
            view_hasl_btn.pack(side=tk.LEFT, padx=5)

            # Blending Options Frame
            blend_frame = ttk.LabelFrame(main_frame, text="Blending Options", padding=10)
            blend_frame.pack(fill=tk.X, padx=5, pady=5)

            # Blending factor q
            q_selection_frame = ttk.Frame(blend_frame)
            q_selection_frame.pack(fill=tk.X, pady=5)
            ttk.Label(q_selection_frame, text="Strength:", width=10).pack(side=tk.LEFT)

            self.q_blend_var = tk.DoubleVar()
            ttk.Label(
                q_selection_frame,
                textvariable=self.q_blend_var,
                width=10
            ).pack(side=tk.LEFT)

            blend_q_scale = ttk.Scale(
                q_selection_frame,
                from_=0.5,
                to=12.0,
                orient=tk.HORIZONTAL,
                variable=self.q_blend_var,
                length=350
            )
            blend_q_scale.pack(side=tk.LEFT, padx=10, expand=True)
            self.q_blend_var.trace_add("write", self.OnQUpdate)
            self.q_blend_var.set(2.0)

            # Blue Channel Adjustment
            blue_adjust_frame = ttk.Frame(blend_frame)
            blue_adjust_frame.pack(fill=tk.X, pady=5)
            ttk.Label(blue_adjust_frame, text="Blue mix:", width=9).pack(side=tk.LEFT)

            self.blue_adjust_var = tk.DoubleVar()
            ttk.Label(
                blue_adjust_frame,
                textvariable=self.blue_adjust_var,
                width=9
            ).pack(side=tk.LEFT, padx=5)

            blend_blue_adjust_scale = ttk.Scale(
                blue_adjust_frame,
                from_=0.0,
                to=1.0,
                orient=tk.HORIZONTAL,
                variable=self.blue_adjust_var,
                length=350
            )
            blend_blue_adjust_scale.pack(side=tk.LEFT, padx=10, expand=True)
            self.blue_adjust_var.trace_add("write", self.OnBluUpdate)
            self.blue_adjust_var.set(0.2)

            # Blend into Blue Channel Checkbox
            self.blend_blue_channel_var = tk.BooleanVar(value=False)
            blend_blue_check = ttk.Checkbutton(
                blend_frame,
                text="Blend Ha into Blue Channel",
                variable=self.blend_blue_channel_var
            )
            blend_blue_check.pack(side=tk.LEFT, padx=5, pady=5)

            # Action Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)

            # Blend Button
            blend_btn = ttk.Button(
                button_frame,
                text="Blend",
                command=self.OnBlend,
                style="TButton"
            )
            blend_btn.pack(side=tk.LEFT, padx=5)

            # Close Button
            close_btn = ttk.Button(
                button_frame,
                text="Close",
                command=self.OnClose,
                style="TButton"
            )
            close_btn.pack(side=tk.LEFT, padx=5)

    def OnCUpdate(self, *args):
        """Update the scaling factor c display - round to 4 decimal places"""
        self.c_scaling_var.set(f"{self.c_scaling_var.get():.4f}")

    def OnBluUpdate(self, *args):
        """Update the scaling factor Blue display - round to 2 decimal places"""
        self.blue_adjust_var.set(f"{self.blue_adjust_var.get():.2f}")

    def OnQUpdate(self, *args):
        """Update the blending factor q display - round to 2 decimal places"""
        self.q_blend_var.set(f"{self.q_blend_var.get():.2f}")
    
    def OnGenerateHaCS(self):
        """Generate and view the HaCS image"""
        r_file = os.path.basename(self.r_file_var.get())
        ha_file = os.path.basename(self.ha_file_var.get())
        r_file_base = os.path.splitext(r_file)[0]
        ha_file_base = os.path.splitext(ha_file)[0]
        c = self.c_scaling_var.get()

        if not all([r_file, ha_file]):
            print("Please select both R and Ha component files.")
            return
        
        try:
            pm_expr = f"\"${ha_file_base}$ - {c:.4f} * ${r_file_base}$\""
            self.siril.cmd("pm", pm_expr)
            hacs_file = "HaCS-generated.fits"
            self.siril.cmd("save", hacs_file)
            self.hacs_file_var.set(hacs_file)

        except Exception as e:
            print(f"Error generating HaCS: {e}")
    
    def OnEstimateC(self):
        """Estimate the scaling factor c for HaCS computation"""
        r_file = self.r_file_var.get()
        g_file = self.g_file_var.get()
        b_file = self.b_file_var.get()
        ha_file = self.ha_file_var.get()

        if not all([r_file, g_file, b_file, ha_file]):
            print("Please select component files (R, G, B, Ha).")
            return

        try:
            # Load FITS files
            r_data = fits.getdata(r_file)
            g_data = fits.getdata(g_file)
            b_data = fits.getdata(b_file)
            ha_data = fits.getdata(ha_file)

            # Compute the scaling factor c
            rgb_sum = r_data + g_data + b_data
            ha_mean = np.mean(ha_data[rgb_sum > 0])
            rgb_mean = np.mean(rgb_sum[rgb_sum > 0])
            c = ha_mean / rgb_mean if rgb_mean != 0 else 1.0

            # Update the scaling variable
            self.c_scaling_var.set(c)

        except Exception as e:
            print(f"Error estimating scaling factor: {str(e)}")
 
    def OnBlend(self):
        """Perform blending of HaCS into RGB image"""
        r_file = os.path.basename(self.r_file_var.get())
        g_file = os.path.basename(self.g_file_var.get())
        b_file = os.path.basename(self.b_file_var.get())
        hacs_file = os.path.basename(self.hacs_file_var.get())

        if not all([r_file, g_file, b_file, hacs_file]):
            print("Please select all component files (R, G, B, HaCS).")
            return

        q = self.q_blend_var.get()
        blend_blue = self.blend_blue_channel_var.get()
        blue_adjust = self.blue_adjust_var.get()

        try:
            r_data = fits.getdata(r_file)
            g_data = fits.getdata(g_file)
            b_data = fits.getdata(b_file)
            hacs_data = fits.getdata(hacs_file)

            hacs_median = np.median(hacs_data)
            new_rdata = r_data + (hacs_data - hacs_median) * q
            new_bdata = b_data + (hacs_data - hacs_median) * q * blue_adjust if blend_blue else b_data
            combined_data = np.array([new_rdata, g_data, new_bdata])

            # Save to FITS file
            hdu = fits.PrimaryHDU(combined_data)
            hdu.writeto("Ha-RGB-blended.fits", overwrite=True)
            self.siril.cmd("load", "Ha-RGB-blended.fits")

        except Exception as e:
            print(f"Error during blending: {str(e)}")

    def OnClose(self):
        """Callback for the Close button."""
        self.siril.disconnect()
        self.root.quit()
        self.root.destroy()

def main():
    try:
        root = ThemedTk(theme="arc")
        app = SirilCSInterface(root)
        root.mainloop()
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
