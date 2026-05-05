# Siril Scripts
## Overview
A custom set of scripts for Siril.

The pre-processing scripts assume master darks and master flats have already been created and placed in the masters directory. There are also preprocessing scripts for creating master flats and master darks using a computed bias.

| File | Description |
|------|-------------|
| Align_Images.py | Image alignment utility that leverages siril star registration functionality. Select any number of files and align. Newly aligned files are created using existing filenames with _aligned suffix. Great for narrowband processing.|
| CC_Denoise.py | GUI front-end script for Cosmic Clarity denoising. Simplifies existing UI and adds pre-stretch for linear data. |
| CC_Sharpen.py | GUI front-end script for Cosmic Clarity sharpening. Simplifies existing UI and adds pre-stretch for linear data. |
| CLAHE.py | Contrast local adaptive histogram equalization with simple luma masking (light and dark) as well as strength. |
| ContinuumSubtraction.py | Continuum subtraction script for narrowband processing. |
| Darks.ssf | Create darks |
| Drizzle.ssf | Stack using drizzle and my preferred settings (deprecated see Stacking.py) |
| Flats.ssh | Create flats using computed bias based on offset derived from Sony 183 sensor |
| GraXpert_BGE.py | GUI front-end script for GraXpert background extraction. Simplified UI |
| GraXpert_Denoise.py | GUI script for GraXpert denoising. Simplfied UI |
| Ha_OII_Extract.ssf | Extraction and stacking for OSC cameras using dual-band filters. |
| Histogram.py | Histogram utility that creates a nice histogram for current image. Provides small button that can be left running. |
| Interpolate.ssf | Stack using lancosz4 interpolation (deprecated see Stacking.py)  |
| Luminance.py | Extracts luminance channel from current image, also allows recombination of modified luminance data |
| Mask.py | Provides masking functionality for siril. Leverages siril undo stack to allow user to provide mask for the most recent operation. Supports 8bit/16bit tiff as well as fits files for masking | 
| NarrowBandMixer.py | Narrowband channel mixer script for blending colors for Ha/OIII extractions, works on both linear and non-linear data. |
| Stacking.py | Stacks images from single and multiple sessions. Provides simple UI for many stacking options that I use. |
| Star_Reducer.py | Star reduction script using Bill Blanshans pixelmath expressions (translated to python) |
