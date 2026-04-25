# GitHub Copilot Instructions

## Project Overview

This repository contains scripts for [Siril](https://siril.org/), an open-source astrophotography image processing application. Scripts fall into two categories:

- **Preprocessing scripts** (`.ssf` files): Siril Script Format files that automate calibration workflows (darks, flats, debayering, drizzle, etc.). They assume master darks and master flats have already been created in a `masters/` directory.
- **Python scripts** (`.py` files): GUI and automation scripts for post-processing steps, driven via the `sirilpy` Python library.

## Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them instead of picking silently.
- If a simpler solution exists, say so.
- If requirements are unclear, stop and ask a clarifying question.

## Simplicity First

**Write the minimum code that solves the requested problem. Nothing speculative.**

- Do not add code beyond the request.
- Avoid abstractions for one-time use.
- When porting code, keep the new code as close to the source implementation as practical to reduce future merge conflicts.

## Repository Structure

| File | Description |
|------|-------------|
| Align_Images.py | Image alignment utility |
| CC_Denoise.py | GUI front-end script for Cosmic Clarity denoising |
| CC_Sharpen.py | GUI front-end script for Cosmic Clarity sharpening |
| CLAHE.py | Contrast local adaptive histogram equalization with simple luma masking and strength |
| ContinuumSubtraction.py | Continuum subtraction script |
| Darks.ssf | Create darks |
| Drizzle.ssf | Stack using drizzle and my preferred settings |
| Flats.ssh | Create flats using computed bias based on offset derived from Sony 183 sensor |
| GraXpert_BGE.py | GUI front-end script for GraXpert background extraction |
| GraXpert_Denoise.py | GUI script for GraXpert denoising |
| Ha_OII_Extract.ssf | Extraction and stacking for flats using dual-band filters (uses drizzle) |
| Histogram.py | Histogram utility that provides nicer histogram for current image |
| Multisession.py | Merges and processes lights from multiple imaging sessions |
| Interpolate.ssf | Stack using lancosz4 interpolation |
| NarrowBandMixer.py | Narrowband channel mixer script for tweaking colors for Ha/OIII extractions |
| Star_Reducer.py | Star reduction script using Bill Blanshans pixelmath expressions (translated to python) |

## Siril Script Format (`.ssf`)

- Comments use `#`
- Commands are Siril's built-in commands (e.g., `cd`, `convert`, `calibrate`, `register`, `stack`, `load`)
- The typical preprocessing workflow is: `cd` into folder → `convert` → `calibrate` → `register` → `stack`
- `requires <version>` can be used to enforce a minimum Siril version
- Siril command reference can be found here: https://siril.readthedocs.io/en/latest/Commands.html

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
- Standard third-party libraries: `astropy`, `numpy`, `PyQt6` (for Qt-based GUIs)
- The python API documentation for SIRIL can be found here: https://siril.readthedocs.io/en/latest/Python-API.html

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

Prefer PyQt6 for all new scripts:

1. **PyQt6** (NarrowBandMixer, Star_Reducer, etc.):
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
- The `dev/` directory is excluded from version control (see `.gitignore`)

## License

All scripts are licensed under GPL-3.0.
