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
s.ensure_installed("scipy")

import os
import sys
import numpy as np                      # type: ignore
import matplotlib.pyplot as plt         # type: ignore

from PyQt6.QtWidgets import (           # type: ignore
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QGroupBox, QCheckBox, QSlider,
    QTextEdit, QComboBox, QMainWindow
)
from PyQt6.QtCore import Qt, QTimer     # type: ignore
from astropy.io import fits             # type: ignore
from scipy.optimize import curve_fit    # type: ignore
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg # type: ignore

version = "v1.x.y"

class SirilCSWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Continuum Subtraction {version}")
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

    def add_file_row(self, label_text, lineedit, width):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(width) # tweak for label alignment
        row.addWidget(label)
        row.addWidget(lineedit, 1)
        btn = QPushButton("Select")
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
            "<b>Continuum Subtraction and Blending Tool</b><br><br>"
            "This tool allows you to generate a continuum-subtracted image "
            "and blend it with RGB channels to create a final image. Select the desired "
            "component files, adjust the parameters, generate the continuum subtracted image, "
            "and apply the blend.<br><br>"
            "<i>Note:</i> Ensure that the component FITS files are aligned, unstretched and in "
            "32-bit float format for best results."
        )
        desc.setFixedHeight(110)
        desc.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(desc)

        # Components selection group
        comps = QGroupBox("Components")
        comps_layout = QHBoxLayout()
        comps_layout.setContentsMargins(8, 8, 8, 8)
        comps_layout.setSpacing(12)
        comps.setLayout(comps_layout)

        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        right_col = QVBoxLayout()
        right_col.setSpacing(6)

        self.cont_desc = QLabel("Color Components")
        right_col.addWidget(self.cont_desc, alignment=Qt.AlignmentFlag.AlignHCenter)

        # ui constants
        COMPONENT_LABEL_WIDTH = 10
        EMISSION_LABEL_WIDTH = 20

        self.r_line = QLineEdit()
        self.r_file = ""
        row, btn = self.add_file_row("R:", self.r_line, COMPONENT_LABEL_WIDTH)
        btn.clicked.connect(lambda: self.on_select_file("r_file", self.r_line))
        right_col.addLayout(row)

        self.g_line = QLineEdit()
        self.g_file = ""
        row, btn = self.add_file_row("G:", self.g_line, COMPONENT_LABEL_WIDTH)
        btn.clicked.connect(lambda: self.on_select_file("g_file", self.g_line))
        right_col.addLayout(row)

        self.b_line = QLineEdit()
        self.b_file = ""
        row, btn = self.add_file_row("B:", self.b_line, COMPONENT_LABEL_WIDTH)
        btn.clicked.connect(lambda: self.on_select_file("b_file", self.b_line))
        right_col.addLayout(row)

        self.emission_desc = QLabel("Emission Line Components", alignment=Qt.AlignmentFlag.AlignHCenter)
        left_col.addWidget(self.emission_desc)

        self.ha_line = QLineEdit()
        self.ha_file = ""
        row, btn = self.add_file_row("Ha:", self.ha_line, EMISSION_LABEL_WIDTH)
        btn.clicked.connect(lambda: self.on_select_file("ha_file", self.ha_line))
        left_col.addLayout(row)

        self.sii_line = QLineEdit()
        self.sii_file = ""
        row, btn = self.add_file_row("SII:", self.sii_line, EMISSION_LABEL_WIDTH)
        btn.clicked.connect(lambda: self.on_select_file("sii_file", self.sii_line))
        left_col.addLayout(row)

        self.oiii_line = QLineEdit()
        self.oiii_file = ""
        row, btn = self.add_file_row("OIII:", self.oiii_line, EMISSION_LABEL_WIDTH)
        btn.clicked.connect(lambda: self.on_select_file("oiii_file", self.oiii_line))
        left_col.addLayout(row)

        comps_layout.addLayout(left_col, 1)
        comps_layout.addLayout(right_col, 1)
        layout.addWidget(comps)

        # CS generation group
        hacs_group = QGroupBox("Continuum Subtraction Generation")
        hacs_layout = QVBoxLayout()
        hacs_group.setLayout(hacs_layout)

        # drop-down to select which emission line to operate on
        self.emission_desc = QLabel("Emission Line Selection")
        hacs_layout.addWidget(self.emission_desc)
        self.emission_combo = QComboBox()
        self.emission_combo.addItems(["Ha", "SII", "OIII"])
        # default to Ha
        self.emission_combo.setCurrentIndex(0)
        self.emission_combo.setFixedWidth(70)
        self.emission_combo.currentTextChanged.connect(self.on_emission_changed)
        hacs_layout.addWidget(self.emission_combo)

        # explain this stuff
        gen_desc = QTextEdit()
        gen_desc.setReadOnly(True)
        gen_desc.setHtml(
            "Optionally compute the ideal continuum scaling factor <i>c</i>. Load the corresponding "
            "color component into Siril based upon the selected emission line. Select a region in the image "
            "in Siril that contains stars but minimal emission, then click 'Estimate'.<br><br>"
            "Alternatively, set <i>c</i> manually using the slider. Click 'Generate' to create and view the "
            "continuum-subtracted image." 
        )
        gen_desc.setFixedHeight(80)
        gen_desc.setStyleSheet("background: transparent; border: none;")
        hacs_layout.addWidget(gen_desc)

        # load and estimate buttons
        btn_row = QHBoxLayout()
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self.on_load)
        estimate_btn = QPushButton("Estimate")
        estimate_btn.clicked.connect(self.on_estimate)
        self.plot_check_box = QCheckBox("Plot Solution")
        btn_row.addWidget(load_btn)
        btn_row.addWidget(estimate_btn)
        btn_row.addWidget(self.plot_check_box)
        btn_row.addStretch()    
        hacs_layout.addLayout(btn_row)

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

        # generate button
        gen_btn = QPushButton("Generate")
        gen_btn.clicked.connect(self.on_generate)
        gen_btn.setFixedWidth(80)
        hacs_layout.addWidget(gen_btn)

        # add the group to main layout
        layout.addWidget(hacs_group)

        # Blending options
        blend_group = QGroupBox("Blending Options")
        blend_layout = QVBoxLayout()
        blend_group.setLayout(blend_layout)

        # q strength slider (determines Ha contribution to final image)
        q_row = QHBoxLayout()
        q_row.addWidget(QLabel("Strength (q):"))
        self.q_slider = QSlider(Qt.Orientation.Horizontal)
        self.q_slider.setRange(0, 1200)
        self.q_slider.setValue(200)
        q_row.addWidget(self.q_slider)
        self.q_value_label = QLabel(f"{self.q_slider.value() / 100:.2f}")
        q_row.addWidget(self.q_value_label)
        self.q_slider.valueChanged.connect(lambda v: self.q_value_label.setText(f"{v / 100:.2f}"))
        blend_layout.addLayout(q_row)
        blend_layout.addSpacing(15)  # fudge for spacing

        # blending help text
        mix_desc = QTextEdit()
        mix_desc.setReadOnly(True)
        mix_desc.setHtml(
            "Optionally adjust the mixing percentages for the RGB channels when blending the "
            "continuum subtracted image."
        )
        mix_desc.setFixedHeight(40)
        mix_desc.setStyleSheet("background: transparent; border: none;")
        blend_layout.addWidget(mix_desc)

        # ui constants
        COLOR_LABEL_WIDTH = 35
        VALUE_LABEL_WIDTH = 35

        # optional red channel blending slider
        red_slider_row = QHBoxLayout()
        red_label = QLabel("Red:")
        red_label.setFixedWidth(COLOR_LABEL_WIDTH)
        red_slider_row.addWidget(red_label)
        self.red_slider = QSlider(Qt.Orientation.Horizontal)
        self.red_slider.setRange(0, 100)
        self.red_slider.setValue(100)
        red_slider_row.addWidget(self.red_slider)
        self.red_value_label = QLabel(f"{self.red_slider.value()}%")
        self.red_value_label.setFixedWidth(VALUE_LABEL_WIDTH)
        red_slider_row.addWidget(self.red_value_label)
        self.red_slider.valueChanged.connect(lambda v: self.red_value_label.setText(f"{v}%"))
        blend_layout.addLayout(red_slider_row)

        # optional blue channel blending slider
        blu_slider_row = QHBoxLayout()
        blu_label = QLabel("Blue:")
        blu_label.setFixedWidth(COLOR_LABEL_WIDTH)
        blu_slider_row.addWidget(blu_label)
        self.blu_slider = QSlider(Qt.Orientation.Horizontal)
        self.blu_slider.setRange(0, 100)
        self.blu_slider.setValue(0)
        blu_slider_row.addWidget(self.blu_slider)
        self.blu_value_label = QLabel(f"{self.blu_slider.value()}%")
        self.blu_value_label.setFixedWidth(VALUE_LABEL_WIDTH)
        blu_slider_row.addWidget(self.blu_value_label)
        self.blu_slider.valueChanged.connect(lambda v: self.blu_value_label.setText(f"{v}%"))
        blend_layout.addLayout(blu_slider_row)

        # optional green channel blending slider
        green_slider_row = QHBoxLayout()
        green_label = QLabel("Green:")
        green_label.setFixedWidth(COLOR_LABEL_WIDTH)
        green_slider_row.addWidget(green_label)
        self.green_slider = QSlider(Qt.Orientation.Horizontal)
        self.green_slider.setRange(0, 100)
        self.green_slider.setValue(0)
        green_slider_row.addWidget(self.green_slider)
        self.green_value_label = QLabel(f"{self.green_slider.value()}%")
        self.green_value_label.setFixedWidth(VALUE_LABEL_WIDTH)
        self.green_value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        green_slider_row.addWidget(self.green_value_label)
        self.green_slider.valueChanged.connect(lambda v: self.green_value_label.setText(f"{v}%"))
        blend_layout.addLayout(green_slider_row)

        blend_layout.addSpacing(15)  # fudge for spacing

        # Blend button
        blend_btn = QPushButton("Blend")
        blend_btn.clicked.connect(self.on_blend)
        blend_btn.setFixedWidth(80)
        blend_layout.addWidget(blend_btn)

        layout.addWidget(blend_group)

    def on_load(self):
        if not self.emission_file or not self.component_file:
            QMessageBox.warning(self, "Missing file", "Please select the emission line component and corresponding color component files.")
            return
        self.siril.cmd("load", self.emission_file)

    def on_emission_changed(self, text: str):
        if text == "Ha":
            self.emission_file = self.ha_file
            self.component_file = self.r_file
        if text == "SII":
            self.emission_file = self.sii_file
            self.component_file = self.g_file
        if text == "OIII":
            self.emission_file = self.oiii_file
            self.component_file = self.b_file

    def on_select_file(self, file_attr: str, lineedit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(self, "Select file", "", "FITS files (*.fits *.fit *.fts *.fits.gz *.fit.gz *.fz *.fz2);;All files (*)")
        if path:
            lineedit.setText(os.path.basename(path))
            setattr(self, file_attr, path)
            self.on_emission_changed(self.emission_combo.currentText())

    def on_generate(self):
        c = self.c_slider.value() / 10000.0

        if not self.r_file or not self.ha_file:
            QMessageBox.warning(self, "Missing files", "Please select both Emission and Color component files.")
            return

        try:
            r_data = fits.getdata(self.r_file)
            ha_data = fits.getdata(self.ha_file)
            hacs_data = ha_data - c * r_data

            out_name = "CS-generated.fits"
            self.cs_file = out_name
            hdu = fits.PrimaryHDU(hacs_data)
            hdu.writeto(out_name, overwrite=True)

            # Load into Siril
            self.siril.cmd("load", out_name)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error generating continuum subtracted image:\n{e}")

    def on_blend(self):
        cs_file = self.cs_file

        if not all([self.r_file, self.g_file, self.b_file, cs_file]):
            QMessageBox.warning(self, "Missing components", "Please select R, G, B and ensure the continuum subtracted image is generated.")
            return

        q = self.q_slider.value() / 100.0
        red_adjust = self.red_slider.value() / 100.0
        blue_adjust = self.blu_slider.value() / 100.0
        green_adjust = self.green_slider.value() / 100.0

        try:
            r_data = fits.getdata(self.r_file).astype(np.float32)
            g_data = fits.getdata(self.g_file).astype(np.float32)
            b_data = fits.getdata(self.b_file).astype(np.float32)
            hacs_data = fits.getdata(cs_file).astype(np.float32)

            hacs_median = np.median(hacs_data)
            new_rdata = r_data + (hacs_data - hacs_median) * q
            new_bdata = b_data + (hacs_data - hacs_median) * q * blue_adjust
            combined_data = np.array([new_rdata, g_data, new_bdata])

            # Ensure output shape (3, height, width) as Siril expects planes-first format
            combined_data = np.array([new_rdata, g_data, b_data], dtype=np.float32)

            out_name = "CS-RGB-blended.fits"
            hdu = fits.PrimaryHDU(combined_data)
            hdu.writeto(out_name, overwrite=True)

            # Load into Siril
            self.siril.cmd("load", out_name)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error during blending:\n{e}")

    def on_estimate(self):
        c_median = 0.0
        
        with self.siril.image_lock():
            if not self.siril.is_image_loaded():
                QMessageBox.warning(self, "Missing Image", "Color component image not loaded in Siril")
                return
        
            if self.siril.get_image_filename() != self.emission_file:
                QMessageBox.warning(self, "Invalid Image", "Loaded image does not match selected emission image")
                return
        
            # get the median of the selected region in the current image
            selection = self.siril.get_siril_selection()
            if selection is None or selection[2] <= 0 or selection[3] <= 0:
                QMessageBox.warning(self, "Invalid Region", "Please select a region in the image in Siril")
                return
            c_median = self.siril.get_selection_stats(selection, 0).median

        # load the narrowband and continuum data
        narrowband_data = fits.getdata(self.emission_file)
        continuum_data = fits.getdata(self.component_file)

        # verify shapes match, e.g. same dimensions, mono images, etc.
        if continuum_data.shape != narrowband_data.shape:
            QMessageBox.critical(self, "Mismatched Images", "Image sizes and types must match.")
            return
        
        scale_factor = self.compute_continuum_subtraction(
            narrowband_data,
            continuum_data,
            selection,
            c_median,
            self.plot_check_box.isChecked()
        )

        print(f"Estimated scale factor: {scale_factor:.4f}")
        self.c_slider.setValue(int(scale_factor * 10000))

    def compute_continuum_subtraction(self, narrowband_image, continuum_image, selection, c_median, plot_optimization):                    
        x, y, w, h = selection
        def slc(im): return im[y:y+h, x:x+w]
        nb = slc(narrowband_image)
        co = slc(continuum_image)

        approx_min = find_min(nb, co, c_median, self.siril)
        max_val = approx_min + 1.0
        min_val = approx_min - 1.0

        scale_factors = np.linspace(min_val, max_val, 40)
        aad_values = []

        for i, sf in enumerate(scale_factors):
            value = aad(nb - (co - c_median) * sf)
            aad_values.append(value)
            self.siril.update_progress("Optimizing continuum subtraction...", i / (len(scale_factors) - 1))
        self.siril.reset_progress()

        def smooth_v(x, A, s0, eps, B):
            return A * np.sqrt((x - s0)**2 + eps**2) + B

        B0 = np.min(aad_values)
        s0_0 = scale_factors[np.argmin(aad_values)]
        slope_est = (aad_values[-1] - aad_values[0]) / (scale_factors[-1] - scale_factors[0])
        A0 = slope_est
        eps0 = 0.01
        p0 = [A0, s0_0, eps0, B0]
        lb = [-1.0, 0.00, 0.0, 0.00]
        ub = [np.inf, 2*max_val, np.inf, np.inf]

        popt, _ = curve_fit(smooth_v, scale_factors, aad_values, p0=p0, bounds=(lb, ub))
        A_opt, s0_opt, eps_opt, B_opt = popt
        optimal_scale = float(np.clip(s0_opt, 0, 1))

        if plot_optimization and self is not None:
            def show_plot():
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.scatter(scale_factors, aad_values, color='C0', alpha=0.6, label='AAD values')
                fx = np.linspace(min_val, max_val, 500)
                fy = smooth_v(fx, *popt)
                ax.plot(fx, fy, 'C3-', label="Smooth-V fit")
                min_aad = smooth_v(optimal_scale, *popt)
                ax.plot([optimal_scale], [min_aad], 'go', ms=10, label=f'Optimal scale = {optimal_scale:.4f}')
                ax.axvline(optimal_scale, color='green', ls='--', alpha=0.5)
                ax.set_title('Optimization for Continuum Subtraction')
                ax.set_xlabel('Scale Factor')
                ax.set_ylabel('AAD')
                ax.grid(alpha=0.3)
                ax.legend(loc='best')

                plot_window = QMainWindow(self)
                plot_window.setWindowTitle("Continuum Subtraction Optimization")
                canvas = FigureCanvasQTAgg(fig)
                central = QWidget()
                layout = QVBoxLayout(central)
                layout.addWidget(canvas)
                plot_window.setCentralWidget(central)
                plot_window.resize(800, 600)
                plot_window.show()

            QTimer.singleShot(0, show_plot)

        return optimal_scale


def aad(data):
    mean = np.mean(data)
    return np.mean(np.abs(data - mean))


def find_min(nb, co, c_median, siril):
    scale_factors = np.linspace(-1, 5, 12)
    aad_values = []

    for i, sf in enumerate(scale_factors):
        value = aad(nb - (co - c_median) * sf)
        aad_values.append(value)
        siril.update_progress("Coarse bounds check...", i / (len(scale_factors) - 1))
    siril.reset_progress()

    min_val = scale_factors[np.argmin(aad_values)]
    return min_val



def main():
    app = QApplication(sys.argv)
    win = SirilCSWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()