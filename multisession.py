import sirilpy
import os

prefix = "session"
base_path = "."

def main():
    siril = sirilpy.SirilInterface()
    try:
        siril.connect()
        print("Connected successfully")
    except sirilpy.SirilConnectionError as e:
        print(f"Connection failed: {e}")
        return
    
    # make our working directory
    if not os.path.exists("process"):
        os.makedirs("process")
    
    mergeDirs = []
    
    # iterate through our session directories for each night
    for entry in os.listdir(base_path):
        full_path = os.path.join(base_path, entry)
        if os.path.isdir(full_path) and entry.startswith(prefix):
            print(f"Found session: {entry}")

            mergeDirs.append("../" + entry + "/process/pp_light")

            # process lights
            siril.cmd("cd", os.path.join(entry, "lights"))
            siril.cmd("convert", "light", "-out=../process")

            # calibrate lights
            siril.cmd("cd", "../process")
            siril.cmd("calibrate", "light", "-dark=../masters/dark_stacked", "-flat=../masters/flat_stacked", 
                      "-cc=dark", "-cfa", "-equalize_cfa")

            siril.cmd("cd", "../..")

    # merge all the processed directories
    mergeDirs.append("pp_merge")
    siril.cmd("cd", "process")
    siril.cmd("merge", *mergeDirs)

    # register lights
    siril.cmd("register", "pp_merge", "-drizzle",  "-scale=1.0", "-pixfrac=1.0", "-kernel=square")

    # stack the merged results
    siril.cmd("stack", "r_pp_merge", "rej", "3", "3", "-norm=addscale", "-output_norm", "-rgb_equal", "-32b", "-out=../result")
    siril.cmd("cd", "..")
    siril.cmd("load", "result")
    siril.cmd("platesolve")
    siril.cmd("save", "result")
    siril.disconnect()

if __name__ == "__main__":
    main()
