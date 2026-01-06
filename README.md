# Siril Scripts
## Overview
A custom set of scripts for Siril. 

The preprocessing scripts generally do all of the preprocessing except for stacking, allowing the user to filter final images for stacking. These scripts also assume master darks and master flats have already been created and placed in the masters directory. There are also preprocessing scripts for creating master flats and master darks using a computed bias.

The python scripts are for various processing steps and are described below.

### cc-denoise
A lightweight script for driving cosmic clarity denoise CLI.

### cc-sharpen
A lightweight script for driving cosmic clarity sharpening CLI.