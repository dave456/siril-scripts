#
# Tool to align files using Siril's alignment algorithms
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2026 lindner234 <AT> gmail
#

import sirilpy as s
s.ensure_installed("ttkthemes")

import sys
import os
import shutil

import tkinter as tk
from tkinter import ttk, filedialog
from ttkthemes import ThemedTk
from sirilpy import tksiril

ALIGN_WORKING_DIR = "align_working"

class SirilAlignInterface:
    def __init__(self, root):
        self.root = root
        root.title("Siril Alignment Tool")
        self.root.resizable(True, True)
        self.root.attributes("-topmost", True)
        self.style = tksiril.standard_style()
        self.files_to_align = []

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
        """Create the GUI widgets for our alignment tool."""
        # main frame
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # add/remove 
        add_remove_frame = ttk.Frame(main_frame, padding=10)
        add_remove_frame.pack(fill=tk.X)
        self.add_button = ttk.Button(add_remove_frame, text="➕", command=self.add_files, width=4)
        self.add_button.pack(side=tk.LEFT, padx=5)
        self.add_button.tooltip = tksiril.create_tooltip(self.add_button, "Add files to align")
        self.remove_button = ttk.Button(add_remove_frame, text="➖", command=self.remove_files, width=4)
        self.remove_button.pack(side=tk.LEFT, padx=5)
        self.remove_button.tooltip = tksiril.create_tooltip(self.remove_button, "Remove selected files from list")

        # files frame
        files_frame = ttk.LabelFrame(main_frame, text="Files to Align", padding=10)
        files_frame.pack(fill=tk.BOTH, expand=True)

        # files list
        self.file_listbox = ttk.Treeview(files_frame, columns=("name",), show="tree", selectmode="extended", height=10)
        self.file_listbox.pack(pady=5, fill=tk.BOTH, expand=True)

        # align button - DO IT
        self.align_button = ttk.Button(main_frame, text="Align Images", command=self.align_files)
        self.align_button.pack(pady=10)

    def add_files(self):
        """Callback for add button - open file dialog to select files to align."""
        files = filedialog.askopenfilenames(parent=self.root, title="Select files to align",
                                            filetypes=[("FITS files", ("*.fit", "*.fits")), ("All files", "*.*")])
        
        for file in files:
            if file in self.files_to_align:
                continue  # avoid duplicates

            self.files_to_align.append(file)
            self.file_listbox.insert("", "end", text=os.path.basename(file))

    def remove_files(self):
        """Callback for remove button - remove selected files from list."""
        selected = self.file_listbox.selection()
        for item in selected:
            self.file_listbox.delete(item)

    def align_files(self):
        """Callback for align button - perform alignment on selected files."""
        try:
            old_cwd = os.getcwd()

            # create our working directory
            if not os.path.exists(ALIGN_WORKING_DIR):
                os.mkdir(ALIGN_WORKING_DIR)

            # create siril sequence of files to align
            seqnum = 1
            for file in self.files_to_align:
                if not os.path.isfile(file):
                    continue
                shutil.copyfile(file, f"{ALIGN_WORKING_DIR}/align_{seqnum:04d}.fits")   
                seqnum += 1

            # do some siril magic
            self.siril.cmd("cd", ALIGN_WORKING_DIR)
            self.siril.cmd("register", "align", "-2pass")
            self.siril.cmd("seqapplyreg", "align", "-framing=min")
            self.siril.cmd("cd", "..")

            # rename our newly aligned files using original names and -aligned suffix
            seqnum = 1
            for file in self.files_to_align:
                if not os.path.isfile(file):
                    self.siril.log(f"File not found, skipping: {file}")
                    continue
                aligned_filename = os.path.splitext(file)[0] + "-aligned.fits"
                if os.path.isfile(aligned_filename):
                    self.siril.log(f"Overwriting existing aligned file: {aligned_filename}")
                    os.remove(aligned_filename)
                os.rename(f"{ALIGN_WORKING_DIR}/r_align_{seqnum:04d}.fits", aligned_filename)
                seqnum += 1

        except Exception as e:
            self.siril.log(f"Error during alignment: {str(e)}")

        finally:
            if os.getcwd() != old_cwd:
                self.siril.cmd("cd", old_cwd)
            if os.path.exists(ALIGN_WORKING_DIR):
                shutil.rmtree(ALIGN_WORKING_DIR)

def main():
    try:
        root = ThemedTk()
        SirilAlignInterface(root)
        root.mainloop()
    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
