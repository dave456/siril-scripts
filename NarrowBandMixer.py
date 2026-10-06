#
# Narrow band mixer for dual narrow band images (Ha + OIII)
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2026 lindner234 <AT> gmail
#

import sirilpy as s
s.ensure_installed("PyQt6")
s.ensure_installed("astropy")
s.ensure_installed("numpy")

import os
import sys
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QGroupBox, QSlider
)
from PyQt6.QtCore import Qt
from astropy.io import fits


class NbMixerWindow(QWidget):
    def __init__(self):
        """ Constructor for our UI class """
        super().__init__()
        self.setWindowTitle(f"Dual Narrow Band Mixer")
        self.setFixedWidth(600)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        # Siril connection
        self.siril = s.SirilInterface()
        try:
            self.siril.connect()
        except s.SirilConnectionError:
            QMessageBox.critical(self, "Error", "Failed to connect to Siril")
            self.close()
            return

        try:
            self.siril.cmd("requires", "1.3.6")
        except s.CommandError:
            QMessageBox.critical(self, "Error", "Siril version requirement not met")
            self.siril.disconnect()
            self.close()
            return
        
        # initialize some member variables
        self.ha_file = ""
        self.oiii_file = ""
        # percentage of each component in each output channel (may exceed 100)
        self.mix = {
            "red": {"ha": 100, "oiii": 0},
            "green": {"ha": 50, "oiii": 50},
            "blue": {"ha": 0, "oiii": 100},
        }
        
        self.create_widgets()


    def create_widgets(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # ui constants
        LABEL_WIDTH = 20
        VALUE_LABEL_WIDTH = 70
        MAX_PERCENT = 200

        # create a box for our columns
        comps_box = QGroupBox(" Components ")
        comps_box.setLayout(QVBoxLayout())
    
        # add HA row
        ha_row = QHBoxLayout()
        ha_label = QLabel("Ha:")
        ha_label.setFixedWidth(LABEL_WIDTH)
        ha_row.addWidget(ha_label)
        self.ha_line = QLineEdit()
        ha_row.addWidget(self.ha_line, 1)
        ha_btn = QPushButton("Select")
        ha_btn.clicked.connect(lambda: self.on_select_file("ha_file", self.ha_line))
        ha_row.addWidget(ha_btn)
        ha_row.setContentsMargins(0, 0, 0, 0)
        ha_row.setSpacing(6)
        comps_box.layout().addLayout(ha_row)

        # add OIII row
        oiii_row = QHBoxLayout()
        oiii_label = QLabel("OIII:")
        oiii_label.setFixedWidth(LABEL_WIDTH)
        oiii_row.addWidget(oiii_label)
        self.oiii_line = QLineEdit()
        oiii_row.addWidget(self.oiii_line, 1)
        oiii_btn = QPushButton("Select")
        oiii_btn.clicked.connect(lambda: self.on_select_file("oiii_file", self.oiii_line))
        oiii_row.addWidget(oiii_btn)
        oiii_row.setContentsMargins(0, 0, 0, 0)
        oiii_row.setSpacing(6)
        comps_box.layout().addLayout(oiii_row)

        layout.addWidget(comps_box)
        layout.addSpacing(10)

        # Add Blender component
        blender_box = QGroupBox(" Mixer ")
        blender_box.setLayout(QVBoxLayout())

        # one Ha slider and one OIII slider per output channel
        for channel in ("red", "green", "blue"):
            box = QGroupBox(f"{channel.capitalize()}  ")
            box.setLayout(QVBoxLayout())
            box.setFlat(True)
            blender_box.layout().addWidget(box)

            for comp, comp_name in (("ha", "Ha"), ("oiii", "OIII")):
                row = QHBoxLayout()
                label = QLabel(f"{comp_name}: {self.mix[channel][comp]}%")
                label.setFixedWidth(VALUE_LABEL_WIDTH)
                row.addWidget(label)
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(0, MAX_PERCENT)
                slider.setValue(self.mix[channel][comp])
                slider.valueChanged.connect(
                    lambda value, c=channel, k=comp, n=comp_name, lbl=label:
                        self.on_slider_changed(c, k, n, lbl, value))
                row.addWidget(slider)
                box.layout().addLayout(row)

        layout.addWidget(blender_box)
        layout.addSpacing(10)

        # Blend button
        blend_btn = QPushButton("Blend")
        blend_btn.clicked.connect(self.on_blend)
        blend_btn.setFixedWidth(80)
        layout.addWidget(blend_btn, alignment=Qt.AlignmentFlag.AlignCenter)
    
    
    def on_select_file(self, file_attr: str, lineedit: QLineEdit):
        """ File selection button callback """
        path, _ = QFileDialog.getOpenFileName(self, "Select file", "", "FITS files (*.fits *.fit *.fts *.fits.gz *.fit.gz *.fz *.fz2);;All files (*)")
        if path:
            lineedit.setText(os.path.basename(path))
            setattr(self, file_attr, path)

    def on_slider_changed(self, channel, comp, comp_name, label, value):
        """ Any mixer slider changed """
        self.mix[channel][comp] = value
        label.setText(f"{comp_name}: {value}%")

    def on_blend(self):
        """ Blend button callback """
        if not self.ha_file or not self.oiii_file:
            QMessageBox.warning(self, "Warning", "Please select both Ha and OIII files")
            return

        try:
            # Load images
            ha_data = fits.getdata(self.ha_file)
            oiii_data = fits.getdata(self.oiii_file)

            # TODO: Some normalization ideas...
            #pHa = np.percentile(ha_data, 99)
            #pO = np.percentile(oiii_data, 99)
            #Ha_sig = np.median(ha_data) - np.median(bg_ha_data)
            #OIII_sig = np.median(oiii_data) - median(bg_oiii_data)
            #scale = pHa / pO
            #print(f"scale: {scale}")
            #oiii_data = oiii_data * scale

            # Create RGB channels
            channels = [(self.mix[c]["ha"] / 100) * ha_data + (self.mix[c]["oiii"] / 100) * oiii_data
                        for c in ("red", "green", "blue")]

            # Ensure output shape (3, height, width) as Siril expects planes-first format
            combined_data = np.array(channels, dtype=np.float32)

            # Clip values to the range [0, 1] to avoid pixels greater than 1.0, this will
            # likely make the image uglier at these points, but should be obvious and force
            # the user to adjust the mixer accordingly.
            np.minimum(combined_data, 1.0, out=combined_data)

            # grab the fits header from the Ha file
            with fits.open(self.ha_file) as hdul:
                header = hdul[0].header
            r, g, b = self.mix["red"], self.mix["green"], self.mix["blue"]
            header.add_history(f"NarrowBandMixer (Ha/OII) mix: R({r['ha']}%/{r['oiii']}%), "
                               f"G({g['ha']}%/{g['oiii']}%), B({b['ha']}%/{b['oiii']}%)")

            out_name = "NB-Blended.fits"
            hdu = fits.PrimaryHDU(combined_data, header=header)
            hdu.writeto(out_name, overwrite=True)

            # Load into Siril
            self.siril.cmd("load", out_name)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to blend images: {str(e)}")


def main():
    app = QApplication(sys.argv)
    win = NbMixerWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
