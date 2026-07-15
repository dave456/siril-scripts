#
# Image masking utility for Siril
#
# This script uses the undo stack to blend the last two states with a mask allowing users to 
# apply masks to their images. The mask can be a FITS or TIFF file, and should be a single-channel 
# grayscale image where pixel values where white (1.0) indicate areas to take from the current image, 
# and black (0.0) indicate areas to take from the previous image, with values in between blending 
# the two. Thanks to Riccardo Paterniti's code for creating masks which I ruthlessly swiped.
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2026 lindner234 <AT> gmail
#

import sirilpy as s
s.ensure_installed("PyQt6")
s.ensure_installed("astropy")
s.ensure_installed("numpy")
s.ensure_installed("opencv-python")
s.ensure_installed("tifffile")

import os
import sys
import threading
import importlib
import cv2
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QGroupBox, QCheckBox,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsPathItem,
    QGraphicsEllipseItem, QSlider, QLabel,
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QPen, QCursor, QPainterPath, QRadialGradient, QBrush
from astropy.io import fits


# ------------------------------------------------------------------------------
# DISPLAY HELPERS
# ------------------------------------------------------------------------------

def _autostretch_for_display(data: np.ndarray) -> np.ndarray:
    """
    Convert planes-first float32 (C, H, W) or 2D (H, W) to uint8 (H, W, 3) RGB.
    Uses MTF autostretch (median + MAD shadows-clipping) — same algorithm as VeraLux_Nox
    and Siril's own display stretch, so linear data looks the same as in the main window.
    """
    # Convert to HWC float32
    if data.ndim == 3:
        rgb = np.moveaxis(data, 0, -1).astype(np.float32)
        if rgb.shape[2] == 1:
            rgb = np.repeat(rgb, 3, axis=2)
        else:
            rgb = rgb[:, :, :3]
    else:
        rgb = np.stack([data, data, data], axis=-1).astype(np.float32)

    MAD_NORM       = 1.4826
    SHADOWS_CLIP   = -2.8
    TARGET_BG      = 0.25

    def _mtf(x, m, lo, hi):
        dist = hi - lo
        if dist < 1e-9:
            return np.zeros_like(x)
        xp  = np.clip((x - lo) / dist, 0.0, 1.0)
        num = (m - 1.0) * xp
        den = (2.0 * m - 1.0) * xp - m
        return num / (den + 1e-9)

    # Linked-channel stretch: average shadow/midtone across R, G, B
    sum_c0 = sum_med = 0.0
    for c in range(3):
        ch     = rgb[:, :, c]
        stride = max(1, ch.size // 100_000)
        sample = ch.ravel()[::stride]
        med    = float(np.median(sample))
        mad    = float(np.median(np.abs(sample - med))) * MAD_NORM or 1e-5
        sum_c0  += med + SHADOWS_CLIP * mad
        sum_med += med

    c0       = max(0.0, sum_c0 / 3.0)
    midtones = float(_mtf(np.array([sum_med / 3.0 - c0]), TARGET_BG, 0.0, 1.0)[0])

    return (np.clip(_mtf(rgb, midtones, c0, 1.0), 0.0, 1.0) * 255).astype(np.uint8)


# ------------------------------------------------------------------------------
# PAINT VIEW (canvas widget for mask painting)
# Adapted from VeraLux_Nox.py PaintView — kept close to source to ease merges.
# ------------------------------------------------------------------------------

class PaintView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.brush_size = 50
        self.tool_mode = 'brush'
        self.is_drawing = False
        self.is_space_held = False
        self.mask_pixmap_item = None
        self.mask_image = None
        self.temp_path_item = None
        self.current_lasso_path = None
        self.preview_item = None
        self.hardness_blur = 0
        # Cyan overlay — visible on both dark nebulae and bright backgrounds
        self.paint_color = QColor(100, 200, 255, 120)

    def set_content(self, qimg_bg: QImage) -> None:
        self.scene().clear()
        self.scene().addPixmap(QPixmap.fromImage(qimg_bg))
        w, h = qimg_bg.width(), qimg_bg.height()

        if self.mask_image is None or self.mask_image.width() != w or self.mask_image.height() != h:
            self.mask_image = QImage(w, h, QImage.Format.Format_ARGB32)
            self.mask_image.fill(QColor(0, 0, 0, 0))

        self.mask_pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(self.mask_image))
        self.mask_pixmap_item.setZValue(10)
        self.scene().addItem(self.mask_pixmap_item)
        self.scene().setSceneRect(0, 0, w, h)

        self.preview_item = QGraphicsEllipseItem()
        self.preview_item.setPen(QPen(QColor(136, 170, 255), 2, Qt.PenStyle.DashLine))
        self.preview_item.setZValue(100)
        self.preview_item.hide()
        self.scene().addItem(self.preview_item)

    def fit_view(self) -> None:
        if self.scene().items():
            self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def update_mask_display(self) -> None:
        if self.mask_pixmap_item and self.mask_image:
            self.mask_pixmap_item.setPixmap(QPixmap.fromImage(self.mask_image))

    def update_brush_preview_geometry(self, scene_pos=None) -> None:
        if not self.preview_item:
            return
        if scene_pos is None:
            scene_pos = self.mapToScene(self.viewport().rect().center())
        r = self.brush_size / 2.0
        self.preview_item.setRect(scene_pos.x() - r, scene_pos.y() - r, self.brush_size, self.brush_size)

    def enterEvent(self, event) -> None:
        self.setFocus()
        if self.tool_mode in ('brush', 'eraser') and not self.is_space_held:
            if self.preview_item:
                self.preview_item.show()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self.preview_item:
            self.preview_item.hide()
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.is_space_held = True
            if self.preview_item:
                self.preview_item.hide()
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.is_space_held = False
            self.update_custom_cursor()
        super().keyReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        if self.is_space_held or not self.is_drawing:
            factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)

    def update_custom_cursor(self) -> None:
        if self.is_space_held:
            return
        if self.tool_mode in ('brush', 'eraser'):
            self.setCursor(Qt.CursorShape.CrossCursor)
            if self.preview_item:
                pen_color = QColor(255, 255, 255) if self.tool_mode == 'eraser' else QColor(136, 170, 255)
                self.preview_item.setPen(QPen(pen_color, 2, Qt.PenStyle.DashLine))
                self.preview_item.show()
                pos = self.mapFromGlobal(QCursor.pos())
                if self.rect().contains(pos):
                    self.update_brush_preview_geometry(self.mapToScene(pos))
        elif self.tool_mode == 'lasso':
            if self.preview_item:
                self.preview_item.hide()
            self._set_lasso_cursor()
        else:
            if self.preview_item:
                self.preview_item.hide()
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def _set_lasso_cursor(self) -> None:
        pix = QPixmap(32, 32)
        pix.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(136, 170, 255), 2))
        path = QPainterPath()
        path.moveTo(20, 20)
        path.cubicTo(28, 10, 10, 0, 10, 10)
        path.cubicTo(10, 20, 25, 25, 20, 20)
        painter.drawPath(path)
        painter.drawLine(20, 20, 28, 28)
        painter.end()
        self.setCursor(QCursor(pix, 0, 0))

    def paint_brush_at(self, pos) -> None:
        if not self.mask_image:
            return

        radius = self.brush_size / 2.0
        blur   = min(int(radius), self.hardness_blur)

        painter = QPainter(self.mask_image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        if self.tool_mode == 'eraser':
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            if blur > 0:
                inner = max(0.0, (radius - blur) / radius)
                grad  = QRadialGradient(pos.x(), pos.y(), radius)
                grad.setColorAt(0.0,   QColor(0, 0, 0, 255))
                grad.setColorAt(inner, QColor(0, 0, 0, 255))
                grad.setColorAt(1.0,   QColor(0, 0, 0, 0))
                painter.setBrush(QBrush(grad))
            else:
                painter.setBrush(QColor(0, 0, 0, 255))
        else:
            # Keep brush translucency consistent (no alpha buildup from overlapping dabs).
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            if blur > 0:
                c     = self.paint_color
                inner = max(0.0, (radius - blur) / radius)
                grad  = QRadialGradient(pos.x(), pos.y(), radius)
                grad.setColorAt(0.0,   c)
                grad.setColorAt(inner, c)
                grad.setColorAt(1.0,   QColor(c.red(), c.green(), c.blue(), 0))
                painter.setBrush(QBrush(grad))
            else:
                painter.setBrush(self.paint_color)

        painter.drawEllipse(pos, radius, radius)
        painter.end()
        self.update_mask_display()

    def finish_lasso(self) -> None:
        if not self.mask_image or not self.current_lasso_path:
            return
        if self.temp_path_item:
            self.scene().removeItem(self.temp_path_item)
            self.temp_path_item = None
        self.current_lasso_path.closeSubpath()
        painter = QPainter(self.mask_image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.paint_color)
        painter.drawPath(self.current_lasso_path)
        painter.end()
        self.update_mask_display()
        self.current_lasso_path = None

    def mousePressEvent(self, event) -> None:
        if self.is_space_held:
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = True
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            pos = self.mapToScene(event.pos())
            if self.tool_mode in ('brush', 'eraser'):
                self.paint_brush_at(pos)
            elif self.tool_mode == 'lasso':
                self.current_lasso_path = QPainterPath(pos)
                self.temp_path_item = QGraphicsPathItem(self.current_lasso_path)
                pen = QPen(self.paint_color, 2)
                pen.setStyle(Qt.PenStyle.DashLine)
                self.temp_path_item.setPen(pen)
                self.temp_path_item.setBrush(QColor(0, 0, 0, 0))
                self.scene().addItem(self.temp_path_item)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        pos = self.mapToScene(event.pos())
        if self.tool_mode in ('brush', 'eraser') and not self.is_space_held:
            self.update_brush_preview_geometry(pos)
            if self.preview_item and not self.preview_item.isVisible():
                self.preview_item.show()
        if self.is_space_held:
            super().mouseMoveEvent(event)
            return
        if self.is_drawing:
            if self.tool_mode in ('brush', 'eraser'):
                self.paint_brush_at(pos)
            elif self.tool_mode == 'lasso' and self.current_lasso_path:
                self.current_lasso_path.lineTo(pos)
                if self.temp_path_item:
                    self.temp_path_item.setPath(self.current_lasso_path)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            self.is_drawing = False
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            if self.tool_mode == 'lasso':
                self.finish_lasso()
        super().mouseReleaseEvent(event)

    def clear_mask(self) -> None:
        if self.mask_image:
            self.mask_image.fill(QColor(0, 0, 0, 0))
            self.update_mask_display()

    def get_painted_mask(self) -> np.ndarray | None:
        """Return bool (H, W) array — True where the user has painted."""
        if not self.mask_image:
            return None
        ptr = self.mask_image.bits()
        ptr.setsize(self.mask_image.sizeInBytes())
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape(
            self.mask_image.height(), self.mask_image.width(), 4
        )
        return arr[:, :, 3] > 0


# ------------------------------------------------------------------------------
# MASK PAINTER DIALOG
# ------------------------------------------------------------------------------

class MaskPainterDialog(QDialog):
    """
    Full-screen interactive mask painter.
    Shows the current Siril image and lets the user paint a mask over it.
    Painted (white) areas become 65535 in the saved 16-bit TIFF; everything
    else is 0.  The mask is saved in FITS row orientation (row 0 = bottom).
    """

    def __init__(self, parent: QWidget, image_data: np.ndarray):
        super().__init__(parent)
        self.setWindowTitle("Create Mask — Paint on Image")
        self.setModal(True)
        self.resize(1200, 800)
        self._image_data = image_data
        self._saved_path: str | None = None
        self._setup_ui()
        self._load_image()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # ── Toolbar ────────────────────────────────────────────────────
        tb = QHBoxLayout()

        tb.addWidget(QLabel("Tool:"))
        self._btn_brush  = QPushButton("Brush")
        self._btn_eraser = QPushButton("Eraser")
        self._btn_lasso  = QPushButton("Lasso")
        for btn in (self._btn_brush, self._btn_eraser, self._btn_lasso):
            btn.setCheckable(True)
            tb.addWidget(btn)
        self._btn_brush.setChecked(True)
        self._btn_brush .clicked.connect(lambda: self._set_tool('brush'))
        self._btn_eraser.clicked.connect(lambda: self._set_tool('eraser'))
        self._btn_lasso .clicked.connect(lambda: self._set_tool('lasso'))

        tb.addSpacing(20)
        tb.addWidget(QLabel("Brush Size:"))
        self._slider_size = QSlider(Qt.Orientation.Horizontal)
        self._slider_size.setRange(5, 300)
        self._slider_size.setValue(50)
        self._slider_size.setFixedWidth(160)
        self._lbl_size = QLabel("50px")
        self._lbl_size.setFixedWidth(40)
        self._slider_size.valueChanged.connect(self._on_brush_size_changed)
        tb.addWidget(self._slider_size)
        tb.addWidget(self._lbl_size)

        tb.addSpacing(12)
        tb.addWidget(QLabel("Blur:"))
        self._slider_blur = QSlider(Qt.Orientation.Horizontal)
        self._slider_blur.setRange(0, 150)
        self._slider_blur.setValue(0)
        self._slider_blur.setFixedWidth(120)
        self._lbl_blur = QLabel("0px")
        self._lbl_blur.setFixedWidth(40)
        self._slider_blur.valueChanged.connect(self._on_blur_changed)
        tb.addWidget(self._slider_blur)
        tb.addWidget(self._lbl_blur)

        tb.addStretch()
        tb.addWidget(QLabel("Zoom:"))
        for label, factor in (("-", 1 / 1.25), ("+", 1.25)):
            btn = QPushButton(label)
            btn.setFixedWidth(32)
            btn.clicked.connect(lambda _=None, f=factor: self._view.scale(f, f))
            tb.addWidget(btn)
        btn_fit = QPushButton("Fit")
        btn_fit.setFixedWidth(36)
        btn_fit.clicked.connect(lambda: self._view.fit_view())
        tb.addWidget(btn_fit)

        tb.addSpacing(16)
        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(lambda: self._view.clear_mask())
        tb.addWidget(btn_clear)

        root.addLayout(tb)

        # ── Canvas ──────────────────────────────────────────────────────
        self._scene = QGraphicsScene()
        self._view = PaintView(self._scene, self)
        root.addWidget(self._view, 1)

        # ── Bottom buttons ──────────────────────────────────────────────
        br = QHBoxLayout()
        br.addWidget(QLabel("Scroll wheel or +/- to zoom  |  Hold Space + drag to pan  |  Paint white mask over the image"))
        br.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        br.addWidget(btn_cancel)
        btn_save = QPushButton("Save Mask…")
        btn_save.clicked.connect(self._on_save)
        br.addWidget(btn_save)
        root.addLayout(br)

        self._tool_btns = (self._btn_brush, self._btn_eraser, self._btn_lasso)

    def _load_image(self) -> None:
        uint8 = _autostretch_for_display(self._image_data)
        # FITS row 0 = bottom; flip so Qt displays it the right way up
        display = np.ascontiguousarray(np.flipud(uint8))
        h, w, _ = display.shape
        qimg = QImage(display.tobytes(), w, h, 3 * w, QImage.Format.Format_RGB888)
        self._view.set_content(qimg)
        self._view.fit_view()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _set_tool(self, tool: str) -> None:
        for btn in self._tool_btns:
            btn.setChecked(False)
        {"brush": self._btn_brush, "eraser": self._btn_eraser, "lasso": self._btn_lasso}[tool].setChecked(True)
        self._view.tool_mode = tool
        self._view.update_custom_cursor()

    def _on_brush_size_changed(self, value: int) -> None:
        self._view.brush_size = value
        self._lbl_size.setText(f"{value}px")

    def _on_blur_changed(self, value: int) -> None:
        self._view.hardness_blur = value
        self._lbl_blur.setText(f"{value}px")

    def _on_save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Mask as 16-bit TIFF", "", "TIFF files (*.tiff *.tif)"
        )
        if not path:
            return
        if not path.lower().endswith(('.tif', '.tiff')):
            path += '.tiff'

        painted = self._view.get_painted_mask()
        if painted is None or not painted.any():
            QMessageBox.warning(self, "Empty Mask", "Nothing has been painted yet.")
            return

        # Flip back to FITS orientation (row 0 = bottom) before saving
        mask_u16 = np.flipud(painted).astype(np.uint16) * 65535
        try:
            tifffile_mod = importlib.import_module("tifffile")
            tifffile_mod.imwrite(path, mask_u16)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save mask:\n{e}")
            return

        self._saved_path = path
        self.accept()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._view.fit_view()

    @property
    def saved_path(self) -> str | None:
        return self._saved_path


# ------------------------------------------------------------------------------
# SIGNAL BRIDGE
# ------------------------------------------------------------------------------

class SignalBridge(QObject):
    """Signal bridge for background thread callbacks"""
    mask_complete = pyqtSignal(str)  # (status)
    error_occurred = pyqtSignal(str)  # (error_message)
    progress_update = pyqtSignal(str, float)  # (message, progress)


class MaskWindow(QWidget):
    def __init__(self):
        """Constructor for the Mask utility UI"""
        super().__init__()
        self.setWindowTitle("Image Masking Utility")
        self.setFixedWidth(550)
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

        if not self.siril.is_image_loaded():
            QMessageBox.critical(self, "Error", "No image loaded")
            self.siril.disconnect()
            self.close()
            return

        # Signal bridge for thread callbacks
        self.signals = SignalBridge()
        self.signals.mask_complete.connect(self.OnMaskComplete)
        self.signals.error_occurred.connect(self.OnError)
        self.signals.progress_update.connect(self.OnProgressUpdate)

        self.mask_file_path = ""
        self.mask_btn = None
        self.mask_line = None

        self.CreateWidgets()


    def CreateWidgets(self):
        """Create the GUI widgets"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Create group box for mask
        mask_box = QGroupBox(" Mask ")
        mask_layout = QVBoxLayout()
        mask_box.setLayout(mask_layout)
        mask_box.setContentsMargins(8, 20, 10, 10)

        # Mask file selection
        file_row = QHBoxLayout()
        file_row.setSpacing(6)

        select_btn = QPushButton("Select")
        select_btn.clicked.connect(self.OnSelectMask)
        file_row.addWidget(select_btn)

        self.mask_line = QLineEdit()
        self.mask_line.setReadOnly(True)
        file_row.addWidget(self.mask_line, 1)
        mask_layout.addLayout(file_row)
        mask_layout.addSpacing(10)

        self.invert_checkbox = QCheckBox("Invert mask")
        mask_layout.addWidget(self.invert_checkbox)

        layout.addWidget(mask_box)
        layout.addSpacing(10)

        # Mask button
        button_row = QHBoxLayout()
        button_row.addStretch()

        self.create_btn = QPushButton("Create")
        self.create_btn.clicked.connect(self.OnCreateMask)
        button_row.addWidget(self.create_btn)
        button_row.addStretch()

        self.mask_btn = QPushButton("Mask")
        self.mask_btn.clicked.connect(self.OnMask)
        self.mask_btn.setEnabled(False)
        button_row.addWidget(self.mask_btn)
        button_row.addStretch()

        self.help_btn = QPushButton("Help")
        self.help_btn.clicked.connect(self.ShowHelp)
        button_row.addWidget(self.help_btn)
        button_row.addStretch()

        layout.addLayout(button_row)

    def OnCreateMask(self):
        """Open the interactive mask painter so the user can paint a mask."""
        if not self.siril.is_image_loaded():
            QMessageBox.warning(self, "No Image", "No image is currently loaded in Siril.")
            return

        try:
            with self.siril.image_lock():
                image_data = self.siril.get_image_pixeldata()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not read image data from Siril:\n{e}")
            return

        dlg = MaskPainterDialog(self, image_data)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.saved_path:
            self.mask_file_path = dlg.saved_path
            self.mask_line.setText(os.path.basename(dlg.saved_path))
            self.mask_btn.setEnabled(True)
            self.siril.log(f"Mask saved: {dlg.saved_path}", s.LogColor.GREEN)
    def OnSelectMask(self):
        """Open file dialog to select mask file"""
        # prefer tiff because that's what I use for masking
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select mask file", 
            "", 
            "TIFF files (*.tiff *.tif);;FITS files (*.fits);;All files (*.*)"
        )
        if file_path:
            self.mask_line.setText(os.path.basename(file_path))
            self.mask_file_path = file_path
            self.mask_btn.setEnabled(True)

    def ShowHelp(self):
        """Show help message box"""
        help_text = (
            "This utility allows you to apply a mask to blend the current image with the previous state from the undo stack.\n\n"
            "1. Load an image in Siril and make some adjustments, e.g. denoise, curves, etc.\n"
            "2. Click 'Create' to create a mask from the existing image.\n"
            "3. Click 'Select' to choose an existing mask file (FITS or TIFF format).\n"
            "4. Optionally invert the mask if desired.\n"
            "5. Click 'Mask' to apply the blending operation.\n\n"
            "The result will be a blend of the current and previous images based on the mask, and will be added to the undo stack "
            "for further adjustments if needed.\n\n"
            "Note: Plate solved images may be flipped in Siril, resulting in an incorrect orientation of the mask when exported "
            "as anything other than FITS. If you export as TIFF and edit in another application this orientation information is lost, "
            "so you may need to experiment with flipping it in an external editor if the result looks wrong."
        )
        QMessageBox.information(self, "Help - Image Masking Utility", help_text)

    def OnMask(self):
        """Apply masking operation"""
        if not self.mask_file_path or not os.path.exists(self.mask_file_path):
            QMessageBox.warning(self, "Error", "No mask file selected or file does not exist")
            return

        self.mask_btn.setEnabled(False)
        threading.Thread(target=self.RunMaskThread, daemon=True).start()

    def OnMaskComplete(self, status):
        """Handle mask operation completion in main thread"""
        self.mask_btn.setEnabled(self.mask_file_path != "")

    def OnError(self, error_msg):
        """Handle error in main thread"""
        QMessageBox.critical(self, "Error", error_msg)
        self.mask_btn.setEnabled(self.mask_file_path != "")

    def OnProgressUpdate(self, message: str, progress: float):
        """Handle progress update in main thread"""
        self.siril.update_progress(message, progress)

    def closeEvent(self, event):
        """Method cverrride for our custom cleanup"""
        self.siril.disconnect()
        super().closeEvent(event)


    def RunMaskThread(self):
        """Background thread to apply mask"""
        try:
            # Load mask file
            mask_data = self.LoadMask(self.mask_file_path)
            if mask_data is None:
                raise ValueError("Failed to load mask file")
            
            # We do the undo first, and outside the lock, because siril won't update the pixel data on an undo
            # with lock held. So we undo, lock, grab pixel data, redo and grab pixel data again, then apply the 
            # mask blend and set the result. *phew*
            self.siril.undo()

            with self.siril.image_lock():
                # Get previous image data
                previous_data = self.siril.get_image_pixeldata()

                # Call redo to get the current image data
                self.siril.redo()

                # Get the current image data
                current_data = self.siril.get_image_pixeldata()

                # sanity check to see if we really got two different pixel maps
                if np.array_equal(current_data, previous_data):
                    self.siril.log("Warning: Undo did not change image data - cannot apply mask", s.LogColor.SALMON)
                    self.signals.error_occurred.emit("Undo did not change image data - cannot apply mask")
                    self.siril.reset_progress()
                    return

                # Apply mask blend operation
                result = self.ApplyMask(current_data, previous_data, mask_data)

                self.signals.progress_update.emit("Setting result image...", 0.8)

                # Save the state for undo/redo
                self.siril.undo_save_state("Mask blend")

                # Set the result
                self.siril.set_image_pixeldata(result)

            self.siril.log("Mask applied successfully", s.LogColor.GREEN)
            self.signals.mask_complete.emit("success")

        except Exception as e:
            self.siril.log(f"Error applying mask: {e}", s.LogColor.SALMON)
            self.signals.error_occurred.emit(f"Error applying mask: {e}")

        finally:
            self.siril.reset_progress()


    def LoadMask(self, file_path: str) -> np.ndarray:
        """
        Load mask from FITS or TIFF file.
        
        Returns
        -------
        float32 numpy array normalized to [0, 1], shape (H, W)
        """
        try:
            if file_path.lower().endswith(('.tif', '.tiff')):
                mask = self.LoadTiffMask(file_path)
            else:
                # Assume FITS file
                with fits.open(file_path) as hdul:
                    mask = hdul[0].data
                    if mask is None:
                        return None

                    mask = np.array(mask)
                    mask = np.squeeze(mask)
                    # TODO: This is a hack, maybe extract luminance or something??
                    if mask.ndim == 3:
                        mask = mask[0]

                    # Normalize to [0, 1], handling special values first.
                    original_dtype = mask.dtype
                    mask = np.nan_to_num(mask, nan=0.0, posinf=1.0, neginf=0.0)
                    mask = NormalizeMask(mask, original_dtype)

            if mask.ndim != 2:
                raise ValueError(f"Mask must be 2D after loading; got shape {mask.shape}")
            
            return mask
        
        except Exception as e:
            self.siril.log(f"Error loading mask file: {e}", s.LogColor.SALMON)
            return None


    def LoadTiffMask(self, file_path: str) -> np.ndarray:
        """Load TIFF mask with metadata-aware channel and polarity handling."""
        # ugh - so this is really complicated due to the ways that applications can save tiff files.
        # Specifically, photo editing apps (ahem, photoshop) often save masks as RGB or RGBA tiffs, 
        # where the actual mask data is in the alpha channel, and the RGB channels are just a preview. 
        # Other apps may save as grayscale, but with photometric metadata that indicates whether white 
        # or black is the "1" value. Contrary to what the help says, all these file formats should 
        # mostly work. Mostly...
        # 
        # We started with imread and we got to here... The problem is, I really like creating my 
        # custom masks in other apps, but this code may have gotten away from me.
        try:
            tifffile_module = importlib.import_module("tifffile")

            with tifffile_module.TiffFile(file_path) as tif:
                if len(tif.pages) == 0:
                    return None

                # Use the largest page to avoid preview/thumbnail pages.
                best_page = None
                best_area = -1
                for page in tif.pages:
                    try:
                        shape = tuple(int(v) for v in page.shape)
                    except Exception:
                        continue

                    if len(shape) == 0:
                        continue

                    if len(shape) == 2:
                        h, w = shape
                    elif len(shape) == 3:
                        if shape[-1] in (1, 2, 3, 4):
                            h, w = shape[0], shape[1]
                        elif shape[0] in (1, 2, 3, 4):
                            h, w = shape[1], shape[2]
                        else:
                            h, w = shape[0], shape[1]
                    else:
                        h, w = shape[-2], shape[-1]

                    area = int(h) * int(w)
                    if area > best_area:
                        best_area = area
                        best_page = page

                if best_page is None:
                    return None

                mask = np.array(best_page.asarray())
                mask = np.squeeze(mask)
                photometric = str(getattr(best_page, "photometric", "")).upper()

                extrasamples = []
                try:
                    extrasamples = [str(v).lower() for v in best_page.extrasamples]
                except Exception:
                    extrasamples = []

            if mask.ndim == 3:
                channel_axis = None
                if mask.shape[-1] in (1, 2, 3, 4):
                    channel_axis = -1
                elif mask.shape[0] in (1, 2, 3, 4):
                    channel_axis = 0

                if channel_axis is None:
                    raise ValueError(f"Unsupported TIFF mask shape {mask.shape}")

                mask_channels_last = np.moveaxis(mask, channel_axis, -1)
                use_alpha = any("alpha" in name for name in extrasamples) and mask_channels_last.shape[-1] >= 2

                if use_alpha:
                    # Many tools store matte in alpha while RGB channels are for preview.
                    mask = mask_channels_last[:, :, -1]
                    self.siril.log("TIFF mask: using alpha channel", s.LogColor.BLUE)
                elif mask_channels_last.shape[-1] >= 3:
                    # Convert RGB-like TIFF to grayscale luminance - barf, this is overkill!
                    rgb = mask_channels_last[:, :, :3].astype(np.float32)
                    mask = 0.114 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.299 * rgb[:, :, 2]
                else:
                    mask = np.mean(mask_channels_last.astype(np.float32), axis=2)

            if mask.ndim != 2:
                raise ValueError(f"TIFF mask must be 2D after conversion; got shape {mask.shape}")

            original_dtype = mask.dtype
            mask = np.nan_to_num(mask, nan=0.0, posinf=1.0, neginf=0.0)
            mask = NormalizeMask(mask, original_dtype)

            # TIFF photometric WhiteIsZero means white pixels are numerically low.
            if "MINISWHITE" in photometric or photometric.endswith(".0") or photometric == "0":
                mask = 1.0 - mask
                self.siril.log("TIFF mask: detected MINISWHITE, auto-inverted", s.LogColor.BLUE)

            return mask.astype(np.float32)

        except Exception as e:
            self.siril.log(f"TIFF metadata load failed ({e}), falling back to OpenCV", s.LogColor.BLUE)

            # Fallback path for uncommon TIFF variants not decoded by tifffile.
            mask = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
            if mask is None:
                return None

            if mask.ndim == 3:
                if mask.shape[2] == 4:
                    mask = cv2.cvtColor(mask, cv2.COLOR_BGRA2GRAY)
                else:
                    mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)

            original_dtype = mask.dtype
            mask = np.nan_to_num(mask, nan=0.0, posinf=1.0, neginf=0.0)
            mask = NormalizeMask(mask, original_dtype)
            return mask.astype(np.float32)
        

    def ApplyMask(self, current: np.ndarray, previous: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """
        Blend the current and previous images together using the mask.
        
        Parameters
        ----------
        current : float32 numpy array
            Current image data in Siril planes-first layout: (channels, height, width) or (height, width)
        previous : float32 numpy array
            Previous image data (from undo) in same layout
        mask : float32 numpy array
            Mask data in range [0, 1], shape (height, width)
        
        Returns
        -------
        float32 numpy array
            Blended result in same layout as input
        """
        current = current.astype(np.float32)
        previous = previous.astype(np.float32)
        mask = mask.astype(np.float32)
        
        # Handle both planes-first (C, H, W) and 2D (H, W) formats
        if current.ndim == 3:
            # Planes-first: expand mask to match channels dimension
            # mask is (H, W), expand to (1, H, W)
            mask_expanded = mask[np.newaxis, :, :]
            if not self.invert_checkbox.isChecked():
                mask_expanded = 1.0 - mask_expanded
            result = current * mask_expanded + previous * (1 - mask_expanded)
        else:
            # 2D case
            if not self.invert_checkbox.isChecked():
                mask = 1.0 - mask
            result = current * mask + previous * (1 - mask)
        
        return result.astype(np.float32)


def NormalizeMask(mask_array: np.ndarray, original_dtype: np.dtype) -> np.ndarray:
    """Normalize mask values to [0, 1] while preserving bright=1 semantics."""
    # ugh - a lot of gunk in here. We handle multiple tiff bit depths. We basically
    # need to ensure that we get a normalized float32 in [0..1]. We also nuke nan-data.
    # This should never happen, but paranoia and all that.
    mask_array = mask_array.astype(np.float32)
    if original_dtype == np.uint8:
        mask_array = mask_array / 255.0
    elif original_dtype == np.uint16:
        mask_array = mask_array / 65535.0
    else:
        # assumes 32bit flaot
        mask_min = np.nanmin(mask_array)
        mask_max = np.nanmax(mask_array)
        if mask_max > mask_min:
            mask_array = (mask_array - mask_min) / (mask_max - mask_min)
        else:
            mask_array = np.zeros_like(mask_array, dtype=np.float32)

    return np.clip(mask_array, 0.0, 1.0).astype(np.float32)


def main():
    try:
        app = QApplication(sys.argv)
        window = MaskWindow()
        window.show()
        sys.exit(app.exec())

    except Exception as e:
        print(f"Error initializing application: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
