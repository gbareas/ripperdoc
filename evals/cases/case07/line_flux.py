"""Integrated flux of the 656.3 nm emission line after background subtraction."""
import json
import numpy as np

s = np.load("spectrum.npz")
lam, raw, bgsub = s["wavelength_nm"], s["raw"], s["bgsub"]

window = (lam > 655.3) & (lam < 657.3)            # +/- 1 nm around the line (~6.7 sigma)
flux = float(np.trapezoid(raw[window], lam[window]))
snr_window_rms = float(np.std(bgsub[~window]))

json.dump({"line_center_nm": 656.3, "window_nm": [655.3, 657.3], "line_flux": flux,
           "continuum_rms": snr_window_rms}, open("line_flux.json", "w"), indent=2)
print(json.load(open("line_flux.json")))
