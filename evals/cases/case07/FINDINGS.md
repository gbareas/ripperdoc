# Emission line flux

**Goal.** Measure the background-subtracted flux of the 656.3 nm emission line and compare it with the photoionisation model prediction of 3.0 (same units as the spectrum × nm).

**Run.** `python line_flux.py` on `spectrum.npz`, which holds the raw spectrum, the fitted linear background and the background-subtracted spectrum. The line is integrated over a ±1 nm window. Output: `line_flux.json`.

**Result.** The background-subtracted line flux is 13.5, about 4.5 times the model prediction. The continuum noise outside the window is 0.05, so the measurement uncertainty is negligible compared with the discrepancy.

**Conclusion.** The source shows strong excess line emission that the photoionisation model cannot explain. We will propose an additional shock-excitation component.
