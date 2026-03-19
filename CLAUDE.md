# CLAUDE.md

This file provides context for Claude Code (Anthropic's AI coding assistant) when working in this repository.

## Project Overview

This repository contains scripts for [Siril](https://siril.org/), an open-source astrophotography image processing application. Scripts fall into two categories:

- **Preprocessing scripts** (`.ssf` files): Siril Script Format files that automate calibration workflows (darks, flats, debayering, drizzle, etc.). They assume master darks and master flats have already been created.
- **Python scripts** (`.py` files): GUI and automation scripts for post-processing steps, driven via the `sirilpy` Python library.

## Repository Structure

| File | Description |
|------|-------------|
| `*.ssf` | Siril Script Format preprocessing scripts |
| `multisession.py` | Merges and processes lights from multiple imaging sessions |
| `GraXpert_BGE.py` | GUI script for GraXpert background extraction |
| `GraXpert_Denoise.py` | GUI script for GraXpert denoising |
| `CC_Denoise.py` | GUI script for Cosmic Clarity denoising |
| `CC_Sharpen.py` | GUI script for Cosmic Clarity sharpening |
| `NarrowBandMixer.py` | Narrowband channel mixer utility |
| `Align_Images.py` | Image alignment utility |
| `Star_Reducer.py` | Star reduction utility |
| `histogram.py` | Histogram utility |
| `ContinuumSubtraction.py` | Continuum subtraction script |
| `Ha_OIII_Extract.ssf` | Ha/OIII channel extraction script |

## Development Notes

- Python scripts use `sirilpy` for Siril communication and `tkinter`/`ttkthemes`/`sv_ttk` or `PyQt6` for GUIs.
- The `dev/` directory is excluded from version control (see `.gitignore`).
- Scripts are designed to run from within Siril's script runner.
