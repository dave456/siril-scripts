import sirilpy as s
s.ensure_installed("PyQt6")
s.ensure_installed("astropy")
s.ensure_installed("numpy")

import os
import sys
import asyncio
import subprocess

from PyQt6 import QtCore # type: ignore
from PyQt6.QtWidgets import ( # type: ignore
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QDoubleSpinBox, QPushButton, QMessageBox, QSlider
)
from astropy.io import fits # type: ignore
import numpy as np # type: ignore

graxpertTemp = "graxpert-temp.fits"
graxpertExecutable = "c:/GraXpert2/GraXpert.exe"

class Worker(QtCore.QObject):
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)

    def __init__(self, siril, gradient_value):
        super().__init__()
        self.siril = siril
        self.gradient_value = gradient_value

    @QtCore.pyqtSlot()
    def run(self):
        try:
            asyncio.run(self.apply_changes())
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

    async def apply_changes(self):
        try:
            with self.siril.image_lock():
                curfilename = self.siril.get_image_filename()
                basename = os.path.basename(curfilename)
                directory = os.path.dirname(curfilename)
                outputFileNoSuffix = os.path.join(directory, f"{basename.split('.')[0]}-bge")
                outputFile = outputFileNoSuffix + ".fits"

                if os.path.exists(graxpertTemp):
                    os.remove(graxpertTemp)

                self.siril.cmd("save", outputFile)

                args = [
                    outputFile, "-cli", "-cmd", "background-extraction",
                    "-ai_version", "-smoothing", str(self.gradient_value / 100),
                    "-output", "graxpert-temp"
                ]

                print("Running GraXpert:", args)

                # Run GraXpert CLI
                subprocess.run([graxpertExecutable] + args, check=True, text=True, capture_output=True)

                # load the resulting image and set it in Siril
                with fits.open(os.path.basename(graxpertTemp)) as hdul:
                    data = hdul[0].data
                    if data.dtype != np.float32:
                        data = np.array(data, dtype=np.float32)
                    self.siril.undo_save_state(f"GraXpert background extraction smoothing={self.gradient_value:.2f}")
                    self.siril.set_image_pixeldata(data)

        finally:
            if os.path.exists(graxpertTemp):
                os.remove(graxpertTemp)

class GraxpertBGEWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GraXpert Background Extract")
        self.setFixedSize(420, 140)

        # Connect to Siril
        self.siril = s.SirilInterface()
        try:
            self.siril.connect()
        except s.SirilConnectionError:
            QMessageBox.critical(self, "Error", "Failed to connect to Siril")
            self.close()
            return

        if not self.siril.is_image_loaded():
            QMessageBox.critical(self, "Error", "No image loaded in Siril")
            self.siril.disconnect()
            self.close()
            return

        try:
            self.siril.cmd("requires", "1.3.6")
        except s.CommandError:
            QMessageBox.critical(self, "Error", "Siril version requirement not met")
            self.siril.disconnect()
            self.close()
            return

        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout()
        central.setLayout(layout)

        # Gradient smoothing controls
        gs_layout = QHBoxLayout()
        gs_layout.addWidget(QLabel("Gradient Smoothing:"))

        self.gs_slider = QSlider(QtCore.Qt.Orientation.Horizontal)
        self.gs_slider.setRange(1, 100)
        self.gs_slider.setValue(85)
        gs_layout.addWidget(self.gs_slider)
        self.gs_value_label = QLabel(f"{self.gs_slider.value()}")
        gs_layout.addWidget(self.gs_value_label)
        self.gs_slider.valueChanged.connect(lambda v: self.gs_value_label.setText(f"{v}"))
        layout.addLayout(gs_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self.on_apply)
        btn_layout.addWidget(self.apply_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.on_close)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

        # Thread placeholders
        self.thread = None
        self.worker = None

    def on_apply(self):
        self.apply_btn.setEnabled(False)
        self.close_btn.setEnabled(False)

        gradient_value = self.gs_slider.value()

        # Create worker and thread
        self.worker = Worker(self.siril, gradient_value)
        self.thread = QtCore.QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def on_worker_finished(self):
        self.cleanup_and_close()

    def on_worker_error(self, msg):
        print("Error during GraXpert processing:", msg)
        self.apply_btn.setEnabled(True)
        self.close_btn.setEnabled(True)

    def cleanup_and_close(self):
        try:
            self.siril.disconnect()
        except Exception:
            pass
        self.close()

    def on_close(self):
        try:
            self.siril.disconnect()
        except Exception:
            pass
        self.close()

def main():
    app = QApplication(sys.argv)
    win = GraxpertBGEWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()