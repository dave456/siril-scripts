# GitHub Copilot Instructions

## Project Overview

This repository contains scripts for [Siril](https://siril.org/), an open-source astrophotography image processing application. Scripts fall into two categories:

- **Preprocessing scripts** (`.ssf` files): Siril Script Format files that automate calibration workflows (darks, flats, debayering, drizzle, etc.). They assume master darks and master flats have already been created in a `masters/` directory.
- **Python scripts** (`.py` files): GUI and automation scripts for post-processing steps, driven via the `sirilpy` Python library.

## Repository Structure

| File | Description |
|------|-------------|
| `Darks.ssf` | Stacks dark frames into a master dark |
| `Flats.ssf` | Stacks flat frames into a master flat |
| `Debayer.ssf` | Calibrates, debayers, registers, and stacks light frames |
| `Drizzle.ssf` | Like Debayer.ssf but uses drizzle integration |
| `Ha_OIII_Extract.ssf` | Ha/OIII channel extraction script |
| `multisession.py` | Merges and processes lights from multiple imaging sessions |
| `GraXpert_BGE.py` | GUI script for GraXpert background extraction |
| `GraXpert_Denoise.py` | GUI script for GraXpert denoising |
| `CC_Denoise.py` | GUI script for Cosmic Clarity denoising |
| `CC_Sharpen.py` | GUI script for Cosmic Clarity sharpening |
| `NarrowBandMixer.py` | Narrowband channel mixer utility (Ha + OIII -> RGB) |
| `Align_Images.py` | Image alignment utility |
| `Star_Reducer.py` | Star reduction utility |
| `histogram.py` | Histogram utility |
| `ContinuumSubtraction.py` | Continuum subtraction script |

## Siril Script Format (`.ssf`)

- Comments use `#`
- Commands are Siril's built-in commands (e.g., `cd`, `convert`, `calibrate`, `register`, `stack`, `load`)
- The typical preprocessing workflow is: `cd` into folder → `convert` → `calibrate` → `register` → `stack`
- `requires <version>` can be used to enforce a minimum Siril version

Example snippet:
```
cd lights
convert light -out=../process
cd ../process
calibrate light -dark=../masters/dark_stacked -flat=../masters/flat_stacked -cc=dark -cfa -equalize_cfa
register pp_light -interp=lanczos4
stack r_pp_light rej 3 3 -norm=addscale -32b -out=../results
```

## Python Script Conventions

### Imports and Dependencies

- Always import `sirilpy` — either as the full name (`import sirilpy`) or aliased as `s` (`import sirilpy as s`). Both forms are used in the codebase.
- Call `sirilpy.ensure_installed("<package>")` (or `s.ensure_installed(...)` when using the alias) at the top for any third-party dependencies before importing them
- Standard third-party libraries: `astropy`, `numpy`, `PyQt6` (for Qt-based GUIs), `tkinter`/`ttkthemes`/`sv_ttk` (for Tk-based GUIs)

### Connecting to Siril

```python
siril = s.SirilInterface()
try:
    siril.connect()
except s.SirilConnectionError:
    # handle connection failure
```

- Always wrap `siril.connect()` in a try/except for `SirilConnectionError`
- Call `siril.disconnect()` on shutdown (or it will disconnect automatically)

### Siril Version Requirements

```python
siril.cmd("requires", "1.3.6")
```

Wrap in try/except for `s.CommandError` if the version requirement needs to be enforced.

### Image Data

- Use `siril.get_image_pixeldata()` to get the current image as a numpy array
- Use `siril.set_image_pixeldata(data)` to set the image data back in Siril
- Use `siril.undo_save_state("description")` before modifying image data to enable undo
- Image data should be `numpy.float32` arrays in planes-first format `(channels, height, width)`
- Use `siril.image_lock()` as a context manager when reading/writing image data to prevent conflicts

### GUI Style

Scripts use one of two GUI frameworks:

1. **Tkinter + sv_ttk/ttkthemes** (most scripts):
   - Create root with `ThemedTk()`, set theme with `sv_ttk.set_theme("dark")`
   - Use `tksiril.standard_style()` for consistent styling
   - Use `ttk.LabelFrame`, `ttk.Frame`, `ttk.Scale`, `ttk.Button`, `ttk.Label` for widgets
   - Update GUI widgets from the main thread only: use `root.after(0, callback)` to schedule UI updates from background threads

2. **PyQt6** (NarrowBandMixer, Star_Reducer, etc.):
   - Subclass `QWidget` for the main window
   - Set `Qt.WindowType.WindowStaysOnTopHint` to keep the window on top
   - Use `QMessageBox` for error/info dialogs

### Threading

- Long-running operations (image processing, external CLI tools) must run in a background thread to keep the GUI responsive
- Pattern used: `threading.Thread(target=lambda: asyncio.run(self.ApplyChanges()), daemon=True).start()`
- Disable UI controls before starting background work and re-enable in the `finally` block

### External Tools Integration

When calling external CLI tools (GraXpert, Cosmic Clarity):
- Save the current Siril image to a temp FITS file using `astropy.io.fits`
- Call the external tool via `subprocess.run()` or `asyncio.create_subprocess_exec()`
- Load the output FITS file back and set it in Siril with `siril.set_image_pixeldata()`
- Always clean up temp files in a `finally` block
- Use `siril.update_progress("message", fraction)` to report progress and `siril.reset_progress()` on completion

### Logging

```python
siril.log("message")                          # default color
siril.log("success", s.LogColor.GREEN)        # green
siril.log("error", s.LogColor.SALMON)         # salmon/red
siril.log("info", s.LogColor.BLUE)            # blue
```

### Script Entry Point

All Python scripts follow this pattern:

```python
def main():
    # ... setup and run ...

if __name__ == "__main__":
    main()
```

## File and Directory Conventions

- Lights are stored in a `lights/` subdirectory
- Calibration frames (darks, flats) are in a `darks/` or `flats/` subdirectory
- Master calibration files go in `masters/` (e.g., `masters/dark_stacked`, `masters/flat_stacked`)
- Intermediate processed files go in `process/`
- Final results go in `results/`
- The `dev/` directory is excluded from version control (see `.gitignore`)

## License

All scripts are licensed under GPL-3.0.
