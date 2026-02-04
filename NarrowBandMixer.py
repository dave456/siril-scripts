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
        self.red_ha = 100  # percentage of Ha in red channel
        self.red_oiii = 0  # percentage of OIII in red channel
        self.green_ha = 50  # percentage of Ha in green channel
        self.green_oiii = 50  # percentage of OIII in green channel
        self.blue_ha = 0  # percentage of Ha in blue channel
        self.blue_oiii = 100  # percentage of OIII in blue channel
        
        self.create_widgets()


    def create_widgets(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # ui constants
        LABEL_WIDTH = 20
        VALUE_LABEL_WIDTH = 50

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

        # RED channel mixer
        red_box = QGroupBox("Red  ")
        red_box.setLayout(QVBoxLayout())
        red_box.setFlat(True)
        blender_box.layout().addWidget(red_box)

        red_row = QHBoxLayout()
        self.red_ha_label = QLabel(f"Ha: {self.red_ha}%")
        self.red_ha_label.setFixedWidth(VALUE_LABEL_WIDTH)
        red_row.addWidget(self.red_ha_label)
        self.red_slider = QSlider(Qt.Orientation.Horizontal)
        self.red_slider.setRange(0, 100)
        self.red_slider.setValue(0)
        red_row.addWidget(self.red_slider)
        self.red_oiii_label = QLabel(f"OIII: {self.red_oiii}%")
        self.red_oiii_label.setFixedWidth(VALUE_LABEL_WIDTH)
        red_row.addWidget(self.red_oiii_label)
        self.red_slider.valueChanged.connect(self.on_red_slider_changed)
        red_box.layout().addLayout(red_row)

        # GREEN channel mixer
        green_box = QGroupBox("Green  ")
        green_box.setLayout(QVBoxLayout())
        green_box.setFlat(True)
        blender_box.layout().addWidget(green_box)

        green_row = QHBoxLayout()
        self.green_ha_label = QLabel(f"Ha: {self.green_ha}%")
        self.green_ha_label.setFixedWidth(VALUE_LABEL_WIDTH)
        green_row.addWidget(self.green_ha_label)
        self.green_slider = QSlider(Qt.Orientation.Horizontal)
        self.green_slider.setRange(0, 100)
        self.green_slider.setValue(50)
        green_row.addWidget(self.green_slider)
        self.green_oiii_label = QLabel(f"OIII: {self.green_oiii}%")
        self.green_oiii_label.setFixedWidth(VALUE_LABEL_WIDTH)
        green_row.addWidget(self.green_oiii_label)
        self.green_slider.valueChanged.connect(self.on_green_slider_changed)
        green_box.layout().addLayout(green_row)

        # BLUE channel mixer
        blue_box = QGroupBox("Blue  ")
        blue_box.setLayout(QVBoxLayout())
        blue_box.setFlat(True)
        blender_box.layout().addWidget(blue_box)

        blue_row = QHBoxLayout()
        self.blue_ha_label = QLabel(f"Ha: {self.blue_ha}%")
        self.blue_ha_label.setFixedWidth(VALUE_LABEL_WIDTH)
        blue_row.addWidget(self.blue_ha_label)
        self.blue_slider = QSlider(Qt.Orientation.Horizontal)
        self.blue_slider.setRange(0, 100)
        self.blue_slider.setValue(100)
        blue_row.addWidget(self.blue_slider)
        self.blue_oiii_label = QLabel(f"OIII: {self.blue_oiii}%")
        self.blue_oiii_label.setFixedWidth(VALUE_LABEL_WIDTH)
        blue_row.addWidget(self.blue_oiii_label)
        self.blue_slider.valueChanged.connect(self.on_blue_slider_changed)
        blue_box.layout().addLayout(blue_row)

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

    def on_red_slider_changed(self, value):
        """ Red channel slider changed """
        self.red_ha = 100 - value
        self.red_oiii = value
        self.red_ha_label.setText(f"Ha: {self.red_ha}%")
        self.red_oiii_label.setText(f"OIII: {self.red_oiii}%")

    def on_green_slider_changed(self, value):
        """ Green channel slider changed """
        self.green_ha = 100 - value
        self.green_oiii = value
        self.green_ha_label.setText(f"Ha: {self.green_ha}%")
        self.green_oiii_label.setText(f"OIII: {self.green_oiii}%")

    def on_blue_slider_changed(self, value):
        """ Blue channel slider changed """
        self.blue_ha = 100 - value
        self.blue_oiii = value
        self.blue_ha_label.setText(f"Ha: {self.blue_ha}%")
        self.blue_oiii_label.setText(f"OIII: {self.blue_oiii}%")

    def on_blend(self):
        """ Blend button callback """
        if not self.ha_file or not self.oiii_file:
            QMessageBox.warning(self, "Warning", "Please select both Ha and OIII files")
            return

        try:
            # Load images
            ha_data = fits.getdata(self.ha_file)
            oiii_data = fits.getdata(self.oiii_file)

            # Create RGB channels
            red_channel = (self.red_ha / 100) * ha_data + (self.red_oiii / 100) * oiii_data
            green_channel = (self.green_ha / 100) * ha_data + (self.green_oiii / 100) * oiii_data
            blue_channel = (self.blue_ha / 100) * ha_data + (self.blue_oiii / 100) * oiii_data

            # Ensure output shape (3, height, width) as Siril expects planes-first format
            combined_data = np.array([red_channel, green_channel, blue_channel], dtype=np.float32)

            # grab the fits header from the Ha file
            with fits.open(self.ha_file) as hdul:
                header = hdul[0].header
            header.add_history("Blended using NarrowBandMixer")

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
