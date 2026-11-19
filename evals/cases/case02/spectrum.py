"""Blackbody spectrum of the T = 5800 K source model, and the location of its peak."""
import json
import numpy as np

h, c, kB = 6.62607015e-34, 2.99792458e8, 1.380649e-23
T = 5800.0

nu = np.linspace(1e13, 3e15, 20000)                              # frequency grid [Hz]
B = (2 * h * nu**3 / c**2) / np.expm1(h * nu / (kB * T))         # Planck spectral radiance [W m^-2 sr^-1 Hz^-1]
lam = c / nu                                                      # wavelength of each sample [m]

i = int(np.argmax(B))
lam_peak_nm = float(lam[i] * 1e9)
wien_nm = float(2.897771955e-3 / T * 1e9)                        # Wien displacement law

np.savez("spectrum.npz", wavelength_m=lam, radiance=B)
json.dump({"T_K": T, "peak_wavelength_nm": lam_peak_nm, "wien_prediction_nm": wien_nm,
           "ratio": lam_peak_nm / wien_nm}, open("peak.json", "w"), indent=2)
print(json.load(open("peak.json")))
