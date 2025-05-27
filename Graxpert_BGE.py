import sirilpy
import os
import subprocess

graxpertTemp = "graxpert-temp.fits"
graxpertExecutable = "c:/GraXpert2/GraXpert.exe"

def main():

    siril = sirilpy.SirilInterface()
    try:
        siril.connect()
        print("Connected successfully")
    except sirilpy.SirilConnectionError as e:
        print(f"Connection failed: {e}")
        return
    
    # Check if there is an image loaded in Siril
    if not siril.is_image_loaded():
        print("No image loaded.")
        return
    
    # get the current image filename and construct our new output filename
    curfilename = siril.get_image_filename()
    basename = os.path.basename(curfilename)
    directory = os.path.dirname(curfilename)
    outputFileNoSuffix = os.path.join(directory, f"{basename.split('.')[0]}-bge")
    outputFile = outputFileNoSuffix + ".fits"
    print(f"Output file will be: {outputFileNoSuffix}")

    # save the current image to a temporary file
    if os.path.exists(graxpertTemp):
        os.remove(graxpertTemp)
    siril.cmd("save", graxpertTemp)

    # Call graxpert.exe to run background extraction
    # graxpert will add the .fits suffix
    args = [graxpertTemp, "-cli", "-cmd", "background-extraction", "-ai_version", "-smoothing", "1.0", "-output", outputFileNoSuffix]
    print(f"Running GraXpert with arguments: {args}")

    # see if the output file already exists - remove it if it does
    if os.path.exists(outputFile):
        print(f"Output file {outputFile} already exists. Removing it.")
        os.remove(outputFile)

    # run graxpert
    try:
        print("Running background extraction...")
        result = subprocess.run([graxpertExecutable] + args, check=True, text=True, capture_output=True)
        print("Background extraction completed.")
        siril.cmd("load", outputFile)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while running the external program: {e}")
        print(result.stderr)
    finally:
        if os.path.exists(graxpertTemp):
            os.remove(graxpertTemp)
   
if __name__ == "__main__":
    main()
