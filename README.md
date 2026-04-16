# Siril Scripts
## Overview
A custom set of scripts for Siril.

The pre-processing scripts assume master darks and master flats have already been created and placed in the masters directory. There are also preprocessing scripts for creating master flats and master darks using a computed bias.

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
