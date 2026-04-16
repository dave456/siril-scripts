# CLAUDE.md

This file provides context for Claude Code (Anthropic's AI coding assistant) when working in this repository.

## Project Overview

This repository contains scripts for [Siril](https://siril.org/), an open-source astrophotography image processing application. Scripts fall into two categories:

- **Preprocessing scripts** (`.ssf` files): Siril Script Format files that automate calibration workflows (darks, flats, debayering, drizzle, etc.). They assume master darks and master flats have already been created.
- **Python scripts** (`.py` files): GUI and automation scripts for post-processing steps, driven via the `sirilpy` Python library.

## Development Notes

- Python scripts use `sirilpy` for Siril communication and `tkinter`/`ttkthemes`/`sv_ttk` or `PyQt6` for GUIs.
- Prefer PyQt6 for new implementations.
- The `dev/` directory is excluded from version control (see `.gitignore`).
- Scripts are designed to run from within Siril's script runner.

## Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler solution exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No code beyond what was asked.
- No abstractions for single use code.
- When porting code, keep new code as close to base source code as possible to avoid conflicts in the future.