import sirilpy as s
s.ensure_installed("astropy")
s.ensure_installed("numpy")
s.ensure_installed("matplotlib")

histogramTemp = "histogram-temp.fits"

import os

from matplotlib import pyplot as plt # type: ignore
from matplotlib.image import imread # type: ignore
import numpy as np # type: ignore
from numpy import mean # type: ignore
from astropy.io import fits # type: ignore

def main():
    siril = s.SirilInterface()
    try:
        siril.connect()
        print("Connected successfully")
    except s.SirilConnectionError as e:
        print(f"Connection failed: {e}")
        return
    
    if not siril.is_image_loaded():
        print("No image loaded")
        siril.disconnect()
        return
    
    with siril.image_lock():
        if os.path.exists(histogramTemp):
            os.remove(histogramTemp)
        siril.cmd("save", histogramTemp)
        
        hdu_list = fits.open(histogramTemp)
        image = hdu_list[0].data
        image_data = np.moveaxis(image, 0, -1)

        R = image_data[:, :, 0]
        G = image_data[:, :, 1]
        B = image_data[:, :, 2]
        plt.imshow(R)
        plt.show()




        print(type(image_data.flatten()))
        print(image_data.flatten().shape)

        B_flat = B.flatten()
        total_pixels = B_flat.size
        print(f"Total pixels: {total_pixels}")
        sample_size = min(100_000, total_pixels)
        if sample_size < total_pixels:
            sample_indices = np.random.choice(total_pixels, sample_size, replace=False)
            B_sample = B_flat[sample_indices]
        else:
            B_sample = B_flat

        #plt.imshow(image_data)
        #plt.show()
        histogram = plt.hist(B_sample, bins="auto")
        plt.show()
        #hdu_list.close()
        #os.remove(histogramTemp)

    siril.disconnect()

if __name__ == "__main__":
    main()
