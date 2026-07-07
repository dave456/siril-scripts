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
| Copy_Header.py | Copies FITS headers from one file to another. Useful when creating new images from pixelmath, etc. |
| Darks.ssf | Create darks |
| DB_Extract.py | Dual band extraction and stacking for OSC cameras |
| Flats.ssh | Create flats using computed bias based on offset derived from Sony 183 sensor |
| GraXpert.py | GUI front-end script for GraXpert background extraction and denoise. Simplified UI |
| Histogram.py | Histogram utility that creates a nice histogram for current image. |
| Luminance.py | Extracts luminance channel from current image, also allows recombination of modified luminance data |
| Mask.py | Provides masking functionality for siril. Leverages siril undo stack to allow user to provide mask for the most recent operation. | 
| NarrowBandMixer.py | Narrowband channel mixer script for blending colors for Ha/OIII extractions, works on both linear and non-linear data. |
| Pedestal.py | Simple pedestal remover. Useful when input image normalization increases min values. Must be run before color calibration. |
| Remove_Banding.py | Provides three different methods to remove banding noise from images. |
| Stacking.py | Stacks images from single and multiple sessions. Provides simple UI for many stacking options that I use. |
| Star_Reducer.py | Star reduction script using Bill Blanshans pixelmath expressions (translated to python) |
| Starnet.py | This script wraps the new Starnet v2.5.1 starnet. The existing starnet is built into Siril |
