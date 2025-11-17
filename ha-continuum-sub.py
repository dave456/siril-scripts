# (c) Dave Lindner 2025
# SPDX-License-Identifier: GPL-3.0-or-later
# lindner234  <AT> gmail
"""
Adds Ha data to RGB images by blending a continuum-subtracted Ha component
into the RGB image, with user-adjustable parameters.
"""
import sirilpy as s
s.ensure_installed("PyQt6")
s.ensure_installed("astropy")
s.ensure_installed("numpy")

import os
import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QGroupBox, QCheckBox, QSlider,
    QTextEdit
)
from PyQt6.QtCore import Qt
from astropy.io import fits
import numpy as np

version = "v1.0.1"

class SirilCSWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Ha Continuum Subtraction {version}")
        self.setFixedWidth(760)

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

        self._create_ui()

    def _file_row(self, label_text, lineedit):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(30) # fudge for alignment
        row.addWidget(label)
        row.addWidget(lineedit, 1)
        btn = QPushButton("Select...")
        row.addWidget(btn)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        return row, btn

    def _create_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        desc = QTextEdit()
        desc.setReadOnly(True)
        desc.setHtml(
            "<b>Ha Continuum Subtraction and Blending Tool</b><br><br>"
            "This tool allows you to generate a continuum-subtracted Ha component "
            "and blend it with RGB channels to create a final image. Select the required "
            "component files, adjust the parameters, generate the HaCS, and apply the blend.<br><br>"
            "The script will also allow you to estimate the ideal continuum scaling factor 'c'. "
            "This value can be fine-tuned using the slider before generating the HaCS component. "    
            "Generating the HaCS component will allow the user to view it before blending.<br><br>"
            "<i>Note:</i> Ensure that the component FITS files are aligned, unstretched and in "
            "32-bit float format for best results."
        )
        desc.setFixedHeight(175)
        desc.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(desc)

        # Components selection group
        comps = QGroupBox("Components")
        comps_layout = QVBoxLayout()
        comps_layout.setContentsMargins(6, 6, 6, 6)
        comps_layout.setSpacing(6)
        comps.setLayout(comps_layout)

        self.r_line = QLineEdit()
        row, btn = self._file_row("R:", self.r_line)
        btn.clicked.connect(lambda: self._select_file(self.r_line))
        comps_layout.addLayout(row)

        self.g_line = QLineEdit()
        row, btn = self._file_row("G:", self.g_line)
        btn.clicked.connect(lambda: self._select_file(self.g_line))
        comps_layout.addLayout(row)

        self.b_line = QLineEdit()
        row, btn = self._file_row("B:", self.b_line)
        btn.clicked.connect(lambda: self._select_file(self.b_line))
        comps_layout.addLayout(row)

        self.ha_line = QLineEdit()
        row, btn = self._file_row("Ha:", self.ha_line)
        btn.clicked.connect(lambda: self._select_file(self.ha_line))
        comps_layout.addLayout(row)

        # Originally showed this in UI, but it was confusing, so we just keep the member variable.
        self.hacs_line = QLineEdit()
        #row, btn = self._file_row("HaCS:", self.hacs_line)
        #btn.clicked.connect(lambda: self._select_file(self.hacs_line))
        #comps_layout.addLayout(row)

        layout.addWidget(comps)

        # HaCS generation group
        hacs_group = QGroupBox("HaCS Generation")
        hacs_layout = QVBoxLayout()
        hacs_group.setLayout(hacs_layout)

        # c constant continuum slider
        c_row = QHBoxLayout()
        c_row.addWidget(QLabel("c:"))
        self.c_slider = QSlider(Qt.Orientation.Horizontal)
        self.c_slider.setRange(0, 10000)
        self.c_slider.setValue(2000)
        c_row.addWidget(self.c_slider)
        self.c_value_label = QLabel(f"{self.c_slider.value() / 10000:.4f}")
        c_row.addWidget(self.c_value_label)
        self.c_slider.valueChanged.connect(lambda v: self.c_value_label.setText(f"{v / 10000:.4f}"))
        hacs_layout.addLayout(c_row)

        # estimate and generate buttons
        btn_row = QHBoxLayout()
        est_btn = QPushButton("Estimate c")
        est_btn.clicked.connect(self.on_estimate_c)
        gen_btn = QPushButton("Generate HaCS")
        gen_btn.clicked.connect(self.on_generate_hacs_numpy)
        btn_row.addWidget(est_btn)
        btn_row.addWidget(gen_btn)
        btn_row.addStretch()
        hacs_layout.addLayout(btn_row)

        layout.addWidget(hacs_group)

        # Blending options
        blend_group = QGroupBox("Blending Options")
        blend_layout = QVBoxLayout()
        blend_group.setLayout(blend_layout)

        # q strength slider (determines Ha contribution to final image)
        q_row = QHBoxLayout()
        q_row.addWidget(QLabel("Ha strength (q):"))
        self.q_slider = QSlider(Qt.Orientation.Horizontal)
        self.q_slider.setRange(0, 1200)
        self.q_slider.setValue(200)
        q_row.addWidget(self.q_slider)
        self.q_value_label = QLabel(f"{self.q_slider.value() / 100:.2f}")
        q_row.addWidget(self.q_value_label)
        self.q_slider.valueChanged.connect(lambda v: self.q_value_label.setText(f"{v / 100:.2f}"))
        blend_layout.addLayout(q_row)

        blend_layout.addSpacing(15)  # fudge for spacing

        # optional blue channel blending checkbox
        blu_check_row = QHBoxLayout()
        self.blend_blue_chk = QCheckBox("Blend Ha into Blue Channel")
        blu_check_row.addWidget(self.blend_blue_chk)
        blu_check_row.addStretch()
        blend_layout.addLayout(blu_check_row)

        # optional blue channel blending slider
        blu_slider_row = QHBoxLayout()
        blu_slider_row.addWidget(QLabel("Blue mix:"))
        self.blu_slider = QSlider(Qt.Orientation.Horizontal)
        self.blu_slider.setRange(1, 100)
        self.blu_slider.setValue(20)
        blu_slider_row.addWidget(self.blu_slider)
        self.blu_value_label = QLabel(f"{self.blu_slider.value()}%")
        blu_slider_row.addWidget(self.blu_value_label)
        self.blu_slider.valueChanged.connect(lambda v: self.blu_value_label.setText(f"{v}%"))
        blend_layout.addLayout(blu_slider_row)

        btn_row2 = QHBoxLayout()
        blend_btn = QPushButton("Blend")
        blend_btn.clicked.connect(self.on_blend)
        #close_btn = QPushButton("Close")
        #close_btn.clicked.connect(self.on_close)
        btn_row2.addWidget(blend_btn)
        #btn_row2.addWidget(close_btn)
        btn_row2.addStretch()
        blend_layout.addLayout(btn_row2)

        layout.addWidget(blend_group)

    def _select_file(self, lineedit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(self, "Select file", "", "FITS files (*.fits);;All files (*)")
        if path:
            lineedit.setText(path)

    # initially implemented using Siril pm command, but switched to numpy for better control
    def on_generate_hacs_numpy(self):
        r_file = self.r_line.text()
        ha_file = self.ha_line.text()
        c = self.c_slider.value() / 10000.0

        if not r_file or not ha_file:
            QMessageBox.warning(self, "Missing files", "Please select both R and Ha component files.")
            return

        try:
            r_data = fits.getdata(r_file)
            ha_data = fits.getdata(ha_file)
            hacs_data = ha_data - c * r_data

            out_name = "HaCS-generated.fits"
            hdu = fits.PrimaryHDU(hacs_data)
            hdu.writeto(out_name, overwrite=True)
            self.hacs_line.setText(out_name)

            # Load into Siril
            self.siril.cmd("load", out_name)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error generating HaCS:\n{e}")

    def on_estimate_c(self):
        r_file = self.r_line.text()
        g_file = self.g_line.text()
        b_file = self.b_line.text()
        ha_file = self.ha_line.text()

        if not all([r_file, g_file, b_file, ha_file]):
            QMessageBox.warning(self, "Missing components", "Please select R, G, B and Ha component files.")
            return

        try:
            r_data = fits.getdata(r_file)
            g_data = fits.getdata(g_file)
            b_data = fits.getdata(b_file)
            ha_data = fits.getdata(ha_file)

            rgb_sum = r_data + g_data + b_data
            mask = rgb_sum > 0
            if not np.any(mask):
                QMessageBox.warning(self, "Estimate failed", "No positive pixels found in RGB sum.")
                return

            ha_mean = np.mean(ha_data[mask])
            rgb_mean = np.mean(rgb_sum[mask])
            c = ha_mean / rgb_mean if rgb_mean != 0 else 1.0
            self.c_slider.setValue(int(c * 10000))
            QMessageBox.information(self, "Estimated c", f"Estimated c = {c:.6f}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error estimating c:\n{e}")

    def on_blend(self):
        r_file = self.r_line.text()
        g_file = self.g_line.text()
        b_file = self.b_line.text()
        hacs_file = self.hacs_line.text()

        if not all([r_file, g_file, b_file, hacs_file]):
            QMessageBox.warning(self, "Missing components", "Please select R, G, B and ensure HaCS component file is generated.")
            return

        q = self.q_slider.value() / 100.0
        blend_blue = self.blend_blue_chk.isChecked()
        blue_adjust = self.blu_slider.value() / 100.0

        print("Blending with q =", q, "blend_blue =", blend_blue, "blue_adjust =", blue_adjust)

        try:
            r_data = fits.getdata(r_file).astype(np.float32)
            g_data = fits.getdata(g_file).astype(np.float32)
            b_data = fits.getdata(b_file).astype(np.float32)
            hacs_data = fits.getdata(hacs_file).astype(np.float32)

            hacs_median = np.median(hacs_data)
            new_rdata = r_data + (hacs_data - hacs_median) * q
            new_bdata = b_data + (hacs_data - hacs_median) * q * blue_adjust if blend_blue else b_data
            combined_data = np.array([new_rdata, g_data, new_bdata])

            # Ensure output shape (3, height, width) as Siril expects planes-first format
            combined_data = np.array([new_rdata, g_data, new_bdata], dtype=np.float32)

            out_name = "Ha-RGB-blended.fits"
            hdu = fits.PrimaryHDU(combined_data)
            hdu.writeto(out_name, overwrite=True)

            # Load into Siril
            self.siril.cmd("load", out_name)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error during blending:\n{e}")

    def on_close(self):
        try:
            self.siril.disconnect()
        except Exception:
            pass
        self.close()

def main():
    app = QApplication(sys.argv)
    win = SirilCSWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()