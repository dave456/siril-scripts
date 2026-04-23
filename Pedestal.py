#
# Remove a common RGB pedestal from the currently loaded image
#
# SPDX-License-Identifier: GPL-3.0
# Author: Dave Lindner (c) 2026 lindner234 <AT> gmail
#

import sirilpy as s
s.ensure_installed("numpy")

import numpy as np


class PedestalScript:
    """Non-GUI pedestal remover"""

    def __init__(self):
        self.siril = s.SirilInterface()

    def run(self):
        try:
            self.siril.connect()
        except s.SirilConnectionError:
            print("Failed to connect to Siril")
            return 1

        try:
            if not self.siril.is_image_loaded():
                self.siril.log("No image loaded", s.LogColor.SALMON)
                return 1

            with self.siril.image_lock():
                data = self.siril.get_image_pixeldata()

                if data.ndim != 3 or data.shape[0] < 3:
                    self.siril.log("Expected RGB image data in (channels, height, width) format", s.LogColor.SALMON)
                    return 1

                rgb = data[:3]
                channel_mins = np.min(rgb, axis=(1, 2)).astype(np.float32)

                if np.any(channel_mins < 0):
                    self.siril.log(
                        f"Pedestal skipped: at least one channel minimum is below zero (R={channel_mins[0]:.6g}, G={channel_mins[1]:.6g}, B={channel_mins[2]:.6g})",
                        s.LogColor.BLUE,
                    )
                    return 0

                pedestal = float(np.min(channel_mins))

                corrected = np.array(data, copy=True)
                corrected[:3] = corrected[:3] - pedestal

                self.siril.undo_save_state(
                    f"Pedestal removal: mins R={channel_mins[0]:.6g}, G={channel_mins[1]:.6g}, B={channel_mins[2]:.6g}, sub={pedestal:.6g}"
                )

                # Some environments may expose either API name.
                if hasattr(self.siril, "set_image_pixel_data"):
                    self.siril.set_image_pixel_data(corrected)
                else:
                    self.siril.set_image_pixeldata(corrected)

            self.siril.log(f"Pedestal removed: {pedestal:.6g}", s.LogColor.GREEN)
            return 0

        except Exception as e:
            self.siril.log(f"Pedestal script failed: {str(e)}", s.LogColor.SALMON)
            return 1

        finally:
            try:
                self.siril.disconnect()
            except Exception:
                pass


def main():
    script = PedestalScript()
    return script.run()


if __name__ == "__main__":
    raise SystemExit(main())