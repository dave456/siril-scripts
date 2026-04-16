# Siril Scripts
## Overview
A custom set of scripts for Siril.

The pre-processing scripts assume master darks and master flats have already been created and placed in the masters directory. There are also preprocessing scripts for creating master flats and master darks using a computed bias.

| File | Description |
|------|-------------|
| `Align_Images.py` | Image alignment utility |
| `CC_Denoise.py` | GUI front-end script for Cosmic Clarity denoising |
| `CC_Sharpen.py` | GUI front-end script for Cosmic Clarity sharpening |
| `CLAHE.py` | Contract Local Adaptive Histogram Equalization with simple masking and strength |
| `ContinuumSubtraction.py` | Continuum subtraction script |
| Darks.ssf | Create darks |
| `GraXpert_BGE.py` | GUI front-end script for GraXpert background extraction |
| `GraXpert_Denoise.py` | GUI script for GraXpert denoising |
| `multisession.py` | Merges and processes lights from multiple imaging sessions |
| `NarrowBandMixer.py` | Narrowband channel mixer utility |
| `Star_Reducer.py` | Star reduction utility |
| `histogram.py` | Histogram utility |
| `Ha_OIII_Extract.ssf` | Ha/OIII channel extraction script |
